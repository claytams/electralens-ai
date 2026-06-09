"""이미지 1차 특징 추출.

색상·에지·밝기 비율을 계산해 모드 분류와 휴리스틱 분석의 입력으로 쓴다.
NumPy가 없으면 Pillow의 ImageStat/histogram만으로 동등한 키 집합을 채우는
폴백 경로를 제공한다(이전 버전은 import 누락으로 이 경로가 NameError로 깨져
있었다).
"""
from __future__ import annotations

from PIL import Image, ImageOps, ImageStat

from .models import (
    DARK_LEVEL,
    EDGE_THRESHOLD,
    FEATURE_SIZE,
    WHITE_LEVEL,
)

try:  # pragma: no cover - 환경에 따라 분기
    import numpy as np
except Exception:  # pragma: no cover - 패키징 폴백
    np = None


# 두 경로가 항상 동일한 키 집합을 반환하도록 기본값을 한곳에 정의한다.
_FEATURE_KEYS = (
    "brightness",
    "edge_density",
    "dark_ratio",
    "white_ratio",
    "red_ratio",
    "green_ratio",
    "cyan_ratio",
    "line_like",
)


def _empty_features() -> dict[str, float]:
    return {key: 0.0 for key in _FEATURE_KEYS}


def image_features(image: Image.Image) -> dict[str, float]:
    """이미지의 색/에지/밝기 통계를 0~1 비율(밝기는 0~255)로 반환한다."""
    img = image.convert("RGB").resize(FEATURE_SIZE, Image.Resampling.BILINEAR)

    if np is None:
        return _features_without_numpy(img)

    arr = np.asarray(img).astype(np.float32)
    gray = arr.mean(axis=2)
    dx = np.abs(gray[:, 1:] - gray[:, :-1])
    dy = np.abs(gray[1:, :] - gray[:-1, :])
    edge_density = float(((dx > EDGE_THRESHOLD).mean() + (dy > EDGE_THRESHOLD).mean()) / 2)
    brightness = float(gray.mean())
    dark_ratio = float((gray < DARK_LEVEL).mean())
    white_ratio = float((gray > WHITE_LEVEL).mean())
    red_ratio = float(((arr[:, :, 0] > 150) & (arr[:, :, 1] < 100) & (arr[:, :, 2] < 100)).mean())
    green_ratio = float(((arr[:, :, 1] > 145) & (arr[:, :, 0] < 120) & (arr[:, :, 2] < 140)).mean())
    cyan_ratio = float(((arr[:, :, 1] > 145) & (arr[:, :, 2] > 145) & (arr[:, :, 0] < 110)).mean())
    line_like = float((edge_density * 0.65) + (white_ratio * 0.2) + ((green_ratio + cyan_ratio) * 1.8))

    features = _empty_features()
    features.update(
        brightness=brightness,
        edge_density=edge_density,
        dark_ratio=dark_ratio,
        white_ratio=white_ratio,
        red_ratio=red_ratio,
        green_ratio=green_ratio,
        cyan_ratio=cyan_ratio,
        line_like=line_like,
    )
    return features


def _features_without_numpy(img: Image.Image) -> dict[str, float]:
    """NumPy 없는 환경용 폴백. 밝기/명암 비율은 히스토그램으로 실제 계산한다."""
    gray = ImageOps.grayscale(img)
    stat = ImageStat.Stat(gray)
    brightness = float(stat.mean[0])

    hist = gray.histogram()  # 길이 256
    total = float(sum(hist)) or 1.0
    dark_ratio = sum(hist[:DARK_LEVEL]) / total
    white_ratio = sum(hist[WHITE_LEVEL + 1:]) / total

    features = _empty_features()
    features.update(
        brightness=brightness,
        dark_ratio=float(dark_ratio),
        white_ratio=float(white_ratio),
    )
    # edge_density/색상 비율은 NumPy 없이는 신뢰도가 낮아 0으로 둔다.
    # (호출부는 모두 .get(key, 0)로 방어하므로 KeyError는 없으며, 키 집합도 일치한다.)
    return features
