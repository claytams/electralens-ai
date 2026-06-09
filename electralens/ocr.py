"""선택적 오프라인 OCR 래퍼.

pytesseract + Tesseract 바이너리가 설치돼 있으면 라벨/안전 모드에서 실제 텍스트를
읽어 정격 수치를 산출한다. 없으면 조용히 None을 반환해, 앱은 정직한 체크리스트
모드로 자동 폴백한다. 단일 exe·오프라인 기본 동작에는 전혀 영향을 주지 않는다.
"""
from __future__ import annotations

import re
from functools import lru_cache

from PIL import Image


@lru_cache(maxsize=1)
def _engine():
    try:
        import pytesseract  # type: ignore

        pytesseract.get_tesseract_version()  # 바이너리 존재 확인
        return pytesseract
    except Exception:
        return None


def available() -> bool:
    return _engine() is not None


def read_text(image: Image.Image) -> str | None:
    """이미지에서 영문/숫자 텍스트를 추출. OCR 불가 시 None."""
    eng = _engine()
    if eng is None:
        return None
    try:
        return eng.image_to_string(image.convert("RGB"), lang="eng")
    except Exception:
        return None


# --- 파서: OCR 텍스트에서 전기적 수치 추출 -------------------------------
_VOLT = re.compile(r"(\d+(?:\.\d+)?)\s*V", re.IGNORECASE)
_AMP = re.compile(r"(\d+(?:\.\d+)?)\s*A\b", re.IGNORECASE)
_WATT = re.compile(r"(\d+(?:\.\d+)?)\s*W\b", re.IGNORECASE)


def parse_adapter_label(text: str) -> dict:
    """어댑터 라벨 텍스트에서 입력/출력 전압·전류·전력을 파싱한다."""
    info: dict[str, object] = {}
    for line in text.splitlines():
        up = line.upper()
        if "OUTPUT" in up:
            v = _VOLT.search(line)
            a = _AMP.search(line)
            if v:
                info["out_v"] = float(v.group(1))
            if a:
                info["out_a"] = float(a.group(1))
        if "INPUT" in up:
            info["input_raw"] = line.strip()
    if "out_v" in info and "out_a" in info:
        info["out_w"] = round(float(info["out_v"]) * float(info["out_a"]), 1)
    return info


def find_watt_values(text: str) -> list[float]:
    """텍스트에 등장하는 모든 W 수치를 반환(안전 모드의 부하 합산용)."""
    return [float(m) for m in _WATT.findall(text)]
