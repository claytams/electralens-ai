"""ElectraLens AI — 사진 한 장으로 전기전자 상황을 읽는 오프라인 데스크톱 AI 조교."""
from __future__ import annotations

from .models import APP_NAME, APP_VERSION, AnalysisResult

__version__ = APP_VERSION
__all__ = ["APP_NAME", "APP_VERSION", "AnalysisResult"]
