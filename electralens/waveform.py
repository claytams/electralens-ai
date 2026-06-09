"""오실로스코프 파형 추정.

개선점(이전 버전 대비):
- 64.0/36.0 같은 임의 매직넘버 대신, 화면의 **격자선 주기를 자기상관으로 검출**해
  실제 px/div를 구한다. 검출에 실패하면 정직하게 'grid_detected=False'로 표시하고
  상대값만 제공한다.
- 트레이스 색을 초록/청록뿐 아니라 노랑/흰색까지 포함해 일반 스코프 사진에도 대응.

절대 주파수는 time/div가 있어야 산출되므로, 호출부에서 가정값(1 ms/div)임을 명시한다.
"""
from __future__ import annotations

from PIL import Image

from .models import GRID_MIN_DIV_PX, WAVEFORM_SIZE

try:  # pragma: no cover
    import numpy as np
except Exception:  # pragma: no cover
    np = None


def _empty() -> dict:
    return {
        "points": 0,
        "period_div": None,
        "vpp_div": None,
        "px_per_div_x": None,
        "px_per_div_y": None,
        "grid_detected": False,
    }


def _trace_mask(arr):
    """밝고 채도 높은 트레이스 픽셀 마스크. 초록/청록/노랑/흰 트레이스를 포괄."""
    r = arr[:, :, 0]
    g = arr[:, :, 1]
    b = arr[:, :, 2]
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    bright = mx > 140
    # 채도(밝은 단색 트레이스) 또는 매우 밝은 흰색 트레이스.
    colorful = (mx - mn) > 55
    very_bright = mx > 210
    classic = ((g > 140) & (b > 110) & (r < 130)) | ((g > 160) & (r < 90))  # 기존 초록/청록
    return (bright & (colorful | very_bright)) | classic


def _largest_band(density, frac=0.5):
    """1D 밀도 신호에서 임계 이상이 연속되는 가장 긴 구간 (start, end)."""
    if density.max() <= 0:
        return 0, len(density)
    above = density >= density.max() * frac
    best = (0, len(density))
    best_len = 0
    cur = None
    for i, v in enumerate(above):
        if v and cur is None:
            cur = i
        if cur is not None and (not v or i == len(above) - 1):
            end = i + 1 if v else i
            if end - cur > best_len:
                best, best_len = (cur, end), end - cur
            cur = None
    return best


def _screen_roi(gray):
    """어두운 스코프 화면 영역의 바운딩 박스를 찾는다. (x0, y0, x1, y1).

    배경/패널보다 훨씬 어두운 화면만 골라, 좌우·상하로 가장 긴 연속 어둠 구간을
    ROI로 삼는다(이상치 열/행에 의해 넓어지지 않도록). 화면이 뚜렷하지 않으면
    전체 이미지를 ROI로 본다(디지털 스코프 스크린샷 등).
    """
    h, w = gray.shape
    dark = gray < 25  # 스코프 화면(거의 검정)만; 일반 배경(어둑함)과 구분
    if dark.mean() < 0.03:
        return (0, 0, w, h)
    x0, x1 = _largest_band(dark.mean(axis=0))
    y0, y1 = _largest_band(dark.mean(axis=1))
    if (x1 - x0) < w * 0.1 or (y1 - y0) < h * 0.1:
        return (0, 0, w, h)
    return (x0, y0, x1, y1)


def _grid_spacing(profile):
    """1D 밝기 프로파일에서 균등 간격 피크(격자선) 간격의 중앙값과 규칙성을 반환.

    어두운 화면 위 밝은 격자선을 가정한다. 반환: (spacing_px | None, regularity 0~1).
    """
    s = profile.astype(np.float64)
    if s.max() - s.min() < 1e-6:
        return None, 0.0
    s = (s - s.min()) / (s.max() - s.min())
    thr = max(s.mean(), float(np.median(s))) + 0.10
    peaks = [
        i for i in range(1, len(s) - 1)
        if s[i] > thr and s[i] >= s[i - 1] and s[i] >= s[i + 1]
    ]
    if len(peaks) < 4:
        return None, 0.0
    diffs = np.diff(np.asarray(peaks))
    diffs = diffs[diffs >= GRID_MIN_DIV_PX]  # 인접 중복 피크 제거
    if len(diffs) < 3:
        return None, 0.0
    med = float(np.median(diffs))
    if med <= 0:
        return None, 0.0
    regularity = float(np.mean(np.abs(diffs - med) <= 0.25 * med))
    return med, regularity


def detect_grid(gray):
    """격자 한 칸의 px 크기를 (px_per_div_x, px_per_div_y, detected)로 검출.

    화면 ROI 안에서 밝은 격자선의 피크 간격 중앙값을 쓴다(임의 상수 없음).
    """
    x0, y0, x1, y1 = _screen_roi(gray)
    roi = gray[y0:y1, x0:x1]
    if roi.size == 0:
        return (None, None, False)
    col_profile = roi.mean(axis=0)  # 세로 격자선 → 열 방향 피크
    row_profile = roi.mean(axis=1)  # 가로 격자선 → 행 방향 피크
    px, reg_x = _grid_spacing(col_profile)
    py, reg_y = _grid_spacing(row_profile)
    detected = (
        px is not None and py is not None
        and reg_x >= 0.6 and reg_y >= 0.6
    )
    return (px, py, detected)


def estimate_waveform(image: Image.Image) -> dict:
    """파형 후보점 수와 (검출 시) 실측 주기/Vpp를 div 단위로 추정."""
    img = image.convert("RGB").resize(WAVEFORM_SIZE, Image.Resampling.BILINEAR)
    if np is None:
        return _empty()

    arr = np.asarray(img).astype(np.int16)
    gray = arr.mean(axis=2)
    mask = _trace_mask(arr)

    xs: list[int] = []
    ys: list[float] = []
    for x in range(mask.shape[1]):
        yy = np.where(mask[:, x])[0]
        if len(yy) >= 1:
            xs.append(x)
            ys.append(float(yy.mean()))
    points = len(xs)

    result = _empty()
    result["points"] = points

    px_x, px_y, grid_detected = detect_grid(gray)
    result["grid_detected"] = grid_detected
    if grid_detected:
        result["px_per_div_x"] = float(px_x)
        result["px_per_div_y"] = float(px_y)

    if points < 30:
        return result

    yarr = np.asarray(ys)
    xarr = np.asarray(xs)
    amplitude_px = float(np.percentile(yarr, 98) - np.percentile(yarr, 2))

    # 영점 교차(상승) 간격으로 한 주기의 픽셀 길이 추정.
    centered = yarr - yarr.mean()
    signs = np.sign(centered)
    crossings = [xarr[i] for i in range(1, len(signs)) if signs[i - 1] < 0 <= signs[i]]
    period_px = None
    if len(crossings) >= 2:
        diffs = [crossings[i] - crossings[i - 1] for i in range(1, len(crossings))]
        period_px = float(sum(diffs) / len(diffs))

    # 항상 제공하는 정직한 상대 측정(화면 대비 비율). 임의 div 상수를 쓰지 않는다.
    h, w = gray.shape
    result["amplitude_px"] = amplitude_px
    result["period_px"] = period_px
    result["vpp_ratio"] = amplitude_px / float(h)
    result["period_ratio"] = (period_px / float(w)) if period_px else None

    # 격자가 확실히 검출된 경우에만 절대 div로 환산(보너스).
    if grid_detected:
        if px_y:
            result["vpp_div"] = amplitude_px / float(px_y)
        if period_px and px_x:
            result["period_div"] = period_px / float(px_x)
    return result
