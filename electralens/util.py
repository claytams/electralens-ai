"""작은 공유 유틸리티: 경로, 폰트, 이미지 크기 조정, 확장자 검사."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageFont

from .models import IMAGE_TYPES


def resource_dir() -> Path:
    """패키징(frozen) 여부에 따라 리소스 기준 디렉터리를 반환."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def writable_runtime_dir() -> Path:
    """쓰기 가능한 런타임 폴더를 찾는다.

    LOCALAPPDATA → 임시폴더 → 사용자 홈 순으로 시도한다. (이전 버전은 최종 폴백이
    cwd였는데, 실행 위치에 따라 공유 폴더에 쓸 수 있어 사용자 홈 하위로 바꿨다.)
    """
    candidates = [
        Path(os.getenv("LOCALAPPDATA", "")) / "ElectraLensAI",
        Path(tempfile.gettempdir()) / "ElectraLensAI",
        Path.home() / ".electralens",
    ]
    for root in candidates:
        try:
            if str(root).strip() in {"", "."}:
                continue
            root.mkdir(parents=True, exist_ok=True)
            probe = root / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return root
        except Exception:
            continue
    return Path.home()


def safe_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """맑은 고딕 → Arial → Pillow 기본 폰트 순으로 폴백."""
    candidates = [
        "C:/Windows/Fonts/malgunbd.ttf" if bold else "C:/Windows/Fonts/malgun.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def fit_image(image: Image.Image, max_w: int, max_h: int) -> Image.Image:
    copy = image.copy()
    copy.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
    return copy


def extension_ok(path: str | Path) -> bool:
    return Path(path).suffix.lower() in IMAGE_TYPES
