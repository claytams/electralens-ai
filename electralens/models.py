"""공유 데이터 모델과 상수.

UI·분석 엔진·렌더러가 함께 쓰는 값들을 한곳에 모은다. 이전 버전에서 여러
파일(메서드)에 흩어져 중복되던 색상/모드 라벨/임계값을 여기로 통합했다.
"""
from __future__ import annotations

from dataclasses import dataclass, field


# --- 앱 메타 ---------------------------------------------------------------
APP_NAME = "ElectraLens AI"
APP_TAGLINE = "사진 한 장으로 전기전자 상황을 읽는 오프라인 AI 조교"
APP_VERSION = "1.0.0"
WINDOW_W = 1220
WINDOW_H = 760

IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}

# 외부(신뢰 불가) 이미지 디코딩 시 메모리 폭탄을 막기 위한 픽셀 상한(50 MP).
MAX_IMAGE_PIXELS = 50_000_000


# --- 표시용 매핑 -----------------------------------------------------------
# severity는 "주의/위험도"를 뜻하며 게이지 색과 점수 색을 결정한다.
SEVERITY_COLORS = {
    "danger": "#f25b4b",
    "warning": "#f0b13d",
    "ok": "#47c78a",
}
DEFAULT_SEVERITY_COLOR = "#47c78a"

# 점수 박스 배경색(렌더러에서 사용).
SEVERITY_FILLS = {
    "danger": "#fff5f1",
    "warning": "#fff9e8",
    "ok": "#eef6f2",
}
DEFAULT_SEVERITY_FILL = "#eef6f2"

MODE_LABELS = {
    "auto": "자동",
    "safety": "안전",
    "circuit": "회로",
    "scope": "파형",
    "label": "라벨",
}
# UI 모드 버튼 순서(라벨은 MODE_LABELS에서 파생).
MODE_ORDER = ("auto", "safety", "circuit", "scope", "label")


def severity_color(severity: str) -> str:
    return SEVERITY_COLORS.get(severity, DEFAULT_SEVERITY_COLOR)


def severity_fill(severity: str) -> str:
    return SEVERITY_FILLS.get(severity, DEFAULT_SEVERITY_FILL)


def mode_label(mode: str) -> str:
    return MODE_LABELS.get(mode, mode)


# --- 이미지 특징 추출 파라미터 --------------------------------------------
FEATURE_SIZE = (320, 220)      # image_features 분석 해상도
EDGE_THRESHOLD = 32            # 인접 픽셀 밝기차 에지 판정 임계
DARK_LEVEL = 55                # 이 값 미만이면 어두운 픽셀
WHITE_LEVEL = 225              # 이 값 초과면 밝은 픽셀

# classify() 자동 분류 임계값(경험값이지만 의미를 드러내기 위해 명명).
SCOPE_DARK_RATIO = 0.42        # 어두운 배경 비율이 이보다 크면 스코프 후보
SCOPE_SIGNAL_RATIO = 0.012     # 초록+청록 신호 비율 하한
CIRCUIT_WHITE_RATIO = 0.48     # 밝은 배경 비율(회로도/브레드보드)
CIRCUIT_EDGE_RATIO = 0.13
LABEL_EDGE_RATIO = 0.18
LABEL_WHITE_RATIO = 0.22

# --- 파형(스코프) 파라미터 ------------------------------------------------
WAVEFORM_SIZE = (640, 360)     # estimate_waveform 분석 해상도
GRID_MIN_DIV_PX = 12           # 격자 한 칸의 최소 픽셀(피크 간격 하한)
DEFAULT_TIME_PER_DIV_S = 1e-3  # time/div 미상 시 가정값(1 ms/div)

# --- 전기전자 상수 ---------------------------------------------------------
MAINS_VOLTAGE = 220.0          # 국내 교류 전압(V)
STRIP_RATING_A = 16.0          # 일반 멀티탭 정격 전류(A)


@dataclass
class AnalysisResult:
    """모든 모드가 채워 반환하는 통일 결과 컨테이너.

    score: 0~100 "주의 점수". 클수록 점검/주의가 더 필요함을 뜻한다(모드 공통).
    severity: "ok" | "warning" | "danger". 게이지/테두리 색을 결정한다.
    confidence: 판정 신뢰도 텍스트("높음"/"중간"/"낮음"). 점수와 분리해 표기.
    """

    mode: str
    title: str
    severity: str
    score: int
    summary: str
    metrics: list[tuple[str, str]]
    sections: list[tuple[str, list[str]]]
    actions: list[str]
    student_note: str
    confidence: str = "중간"
    # 측정 기반 값인지(True) 가정/추정인지(False) 표시. 정직성 표기에 사용.
    measured: bool = False
    tags: list[str] = field(default_factory=list)
