"""스마트 프로브: 드래그한 사각 영역만 따로 해석해 국소 힌트를 생성한다.

(이전 버전의 점-기반 smart_probe와 self.probe_point는 어디서도 호출되지 않는
죽은 코드여서 제거했다. UI는 영역 기반 프로브만 사용한다.)
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from .features import image_features
from .models import mode_label
from .waveform import estimate_waveform


def smart_probe_region(
    image: Image.Image,
    rect: tuple[int, int, int, int],
    mode: str,
    path: str | None = None,
) -> str:
    x0, y0, x1, y1 = rect
    crop = image.crop((x0, y0, x1, y1))
    features = image_features(crop)
    area_pct = ((x1 - x0) * (y1 - y0)) / max(1, image.width * image.height) * 100
    label = mode_label(mode)
    hints = [f"{label} 모드 기준 선택 구역 {x1 - x0} x {y1 - y0}px, 전체 이미지의 {area_pct:.1f}%"]

    name = Path(path).stem.lower() if path else ""
    wave = estimate_waveform(crop) if mode in {"auto", "scope"} or "scope" in name else {"points": 0}
    if wave.get("points", 0) and int(wave["points"]) > 24:
        hints.append(f"파형 후보점 {wave['points']}개가 잡혔습니다. 이 영역은 주기/Vpp를 읽기 좋은 구간입니다.")
    if features.get("edge_density", 0) > 0.16:
        hints.append("에지 밀도가 높아 문자, 부품 경계, 배선, 핀 배열처럼 정보가 많은 영역입니다.")
    if features.get("white_ratio", 0) > 0.42:
        hints.append("밝은 배경 비율이 높아 회로도/라벨/브레드보드 영역일 가능성이 큽니다.")
    if features.get("dark_ratio", 0) > 0.34:
        hints.append("어두운 영역이 많습니다. 스코프 화면/어댑터 본체/그림자라면 주변 밝은 선이나 라벨을 함께 선택하세요.")
    if features.get("red_ratio", 0) > 0.015:
        hints.append("빨간색 성분이 강합니다. +전원 레일, 경고 표시, 고출력 부하 후보로 우선 확인할 만합니다.")
    if features.get("green_ratio", 0) + features.get("cyan_ratio", 0) > 0.012:
        hints.append("초록/청록 성분이 감지됩니다. LED, 신호선, 오실로스코프 파형 후보일 수 있습니다.")

    mode_hint = {
        "safety": "안전 관점에서는 이 구역의 플러그/케이블 굵기, 접점 흔들림, 정격 표시를 함께 확인해야 합니다.",
        "circuit": "회로 관점에서는 이 구역이 전원에서 GND로 돌아가는 폐루프의 일부인지 추적하면 좋습니다.",
        "scope": "파형 관점에서는 선택 구역 안에서 가로 한 주기 칸 수와 세로 피크-피크 칸 수를 비교합니다.",
        "label": "라벨 관점에서는 INPUT, OUTPUT, V, A, W, 극성 기호가 선택 구역 안에 있는지 확인합니다.",
    }.get(mode)
    if mode_hint:
        hints.append(mode_hint)

    return "\n".join(hints[:6])
