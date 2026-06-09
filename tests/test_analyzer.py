"""분석 엔진/분류/샘플 결과 불변식 테스트."""
from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from electralens.analyzer import ElectraAnalyzer
from electralens.samples import generate_samples


@pytest.fixture(scope="module")
def samples(tmp_path_factory) -> dict[str, Path]:
    out = tmp_path_factory.mktemp("samples")
    return generate_samples(out)


@pytest.fixture(scope="module")
def analyzer() -> ElectraAnalyzer:
    return ElectraAnalyzer()


@pytest.mark.parametrize("key,expected_mode", [
    ("safety", "safety"),
    ("circuit", "circuit"),
    ("scope", "scope"),
    ("label", "label"),
])
def test_sample_classified_and_curated(analyzer, samples, key, expected_mode):
    img = Image.open(samples[key]).convert("RGB")
    r = analyzer.analyze(img, str(samples[key]), "auto")
    assert r.mode == expected_mode
    assert r.measured is True            # 샘플은 큐레이트된 측정 결과
    assert r.severity in {"ok", "warning", "danger"}
    assert 0 <= r.score <= 100
    assert r.title and r.summary


def test_real_image_filename_not_treated_as_sample(analyzer, tmp_path):
    """파일명에 'circuit'이 들어가도 sample_ 접두사가 없으면 실제 경로로 처리."""
    p = tmp_path / "web_circuit_real_photo.png"
    Image.new("RGB", (320, 240), (200, 200, 200)).save(p)
    r = analyzer.analyze(Image.open(p).convert("RGB"), str(p), "circuit")
    # 하드코딩 샘플 수치(21.2 mA)가 아니라 정직한 미측정 결과여야 한다.
    assert r.measured is False
    assert all("21.2 mA" not in v for _, v in r.metrics)


def test_safety_margin_sign_is_positive(analyzer, samples):
    """16 A 정격 대비 여유는 +0.1 A(정격 이내)여야 한다(이전 버전의 -0.1 부호 버그)."""
    img = Image.open(samples["safety"]).convert("RGB")
    r = analyzer.analyze(img, str(samples["safety"]), "auto")
    margin = dict(r.metrics)["16 A 정격 대비 여유"]
    assert margin.startswith("+"), f"여유는 양수여야 함: {margin}"


def test_classify_by_features_without_keyword(analyzer):
    # 어두운 배경(스코프 후보) 단색은 키워드 없이 분류기로 가야 한다.
    feats = {"dark_ratio": 0.6, "green_ratio": 0.02, "cyan_ratio": 0.0}
    assert analyzer.classify(Image.new("RGB", (10, 10)), None, feats) == "scope"
