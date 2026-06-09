"""image_features 테스트 — 정상 경로와 NumPy 미설치 폴백 경로 모두."""
from __future__ import annotations

import importlib

from PIL import Image

from electralens import features
from electralens.features import _FEATURE_KEYS, image_features


def _solid(color=(128, 128, 128), size=(64, 48)) -> Image.Image:
    return Image.new("RGB", size, color)


def test_features_have_all_keys():
    feats = image_features(_solid())
    assert set(feats) == set(_FEATURE_KEYS)
    assert all(isinstance(v, float) for v in feats.values())


def test_features_brightness_reasonable():
    dark = image_features(_solid((10, 10, 10)))
    bright = image_features(_solid((240, 240, 240)))
    assert dark["brightness"] < bright["brightness"]
    assert bright["white_ratio"] > 0.9
    assert dark["dark_ratio"] > 0.9


def test_numpy_absent_fallback_does_not_crash(monkeypatch):
    """이전 버전의 핵심 버그: np 폴백에서 ImageStat 미import로 NameError 크래시.

    np를 None으로 강제해도 동일 키 집합을 반환하고 예외가 없어야 한다.
    """
    monkeypatch.setattr(features, "np", None)
    feats = image_features(_solid((30, 30, 30)))
    assert set(feats) == set(_FEATURE_KEYS)
    assert feats["dark_ratio"] > 0.9  # 히스토그램 기반 실제 계산
    # 원상 복구
    importlib.reload(features)
