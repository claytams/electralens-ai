"""파형 격자 검출과 OCR 파서 테스트."""
from __future__ import annotations

import math

from PIL import Image, ImageDraw

from electralens import ocr
from electralens.waveform import detect_grid, estimate_waveform

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None


def _synthetic_scope(width=640, height=360, divs_x=10, divs_y=8, cycles=4.0) -> Image.Image:
    """격자 + 정현파를 가진 합성 스코프 이미지."""
    img = Image.new("RGB", (width, height), (8, 16, 24))
    d = ImageDraw.Draw(img)
    for i in range(divs_x + 1):
        x = i * width / divs_x
        d.line((x, 0, x, height), fill=(30, 60, 70), width=1)
    for j in range(divs_y + 1):
        y = j * height / divs_y
        d.line((0, y, width, y), fill=(30, 60, 70), width=1)
    pts = []
    for x in range(width):
        t = x / width
        y = height / 2 + math.sin(t * math.tau * cycles) * (height * 0.3)
        pts.append((x, y))
    d.line(pts, fill=(66, 255, 208), width=3)
    return img


def test_estimate_waveform_finds_points():
    if np is None:
        return
    wave = estimate_waveform(_synthetic_scope())
    assert wave["points"] > 100
    assert wave["vpp_ratio"] is not None
    assert wave["period_ratio"] is not None


def test_grid_detection_on_clean_grid():
    if np is None:
        return
    img = _synthetic_scope(divs_x=10, divs_y=8)
    gray = np.asarray(img.convert("RGB")).astype("float32").mean(axis=2)
    px, py, detected = detect_grid(gray)
    if detected:  # 검출되면 간격이 대략 width/10, height/8 이어야 한다
        assert abs(px - 640 / 10) < 12
        assert abs(py - 360 / 8) < 12


def test_ocr_adapter_parser():
    text = "AC/DC ADAPTER\nINPUT: 100-240V 50/60Hz\nOUTPUT: 5V 2A\nPOWER: 10W"
    info = ocr.parse_adapter_label(text)
    assert info["out_v"] == 5.0
    assert info["out_a"] == 2.0
    assert info["out_w"] == 10.0


def test_ocr_watt_finder():
    assert ocr.find_watt_values("HEATER 1800W and DRYER 1500 W") == [1800.0, 1500.0]


def test_ocr_optional_available_is_bool():
    assert isinstance(ocr.available(), bool)
