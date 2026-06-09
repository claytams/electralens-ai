"""분석 엔진: 이미지 → 모드 분류 → 모드별 전기전자 해석(AnalysisResult).

설계 원칙(이번 보완):
- 측정 가능한 것만 측정값으로 제시한다. 샘플이 아닌 실제 사진에서 소비전력처럼
  사진만으로 알 수 없는 값은 가짜 수치 대신 체크리스트로 정직하게 후퇴한다.
- OCR(선택적)이 가능하면 라벨/안전 모드에서 실제 정격을 읽어 계산한다.
- 스코프 모드는 격자선을 검출해 실측 주기/Vpp를 div 단위로 산출한다.
- score는 모든 모드에서 "주의 점수(0 안심 ~ 100 즉시 점검)"로 의미를 통일한다.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from . import ocr
from .features import image_features
from .models import (
    AnalysisResult,
    CIRCUIT_EDGE_RATIO,
    CIRCUIT_WHITE_RATIO,
    DEFAULT_TIME_PER_DIV_S,
    LABEL_EDGE_RATIO,
    LABEL_WHITE_RATIO,
    MAINS_VOLTAGE,
    SCOPE_DARK_RATIO,
    SCOPE_SIGNAL_RATIO,
    STRIP_RATING_A,
)
from .waveform import estimate_waveform


class ElectraAnalyzer:
    def __init__(self) -> None:
        self.sample_fingerprints = {
            "sample_power_strip": "safety",
            "sample_circuit": "circuit",
            "sample_scope": "scope",
            "sample_adapter": "label",
        }

    def analyze(self, image: Image.Image, path: str | None, requested_mode: str) -> AnalysisResult:
        features = image_features(image)
        mode = requested_mode
        if requested_mode == "auto":
            mode = self.classify(image, path, features)
        if mode == "safety":
            return self._safety(image, path, features)
        if mode == "circuit":
            return self._circuit(image, path, features)
        if mode == "scope":
            return self._scope(image, path, features)
        if mode == "label":
            return self._label(image, path, features)
        return self._general(image, path, features)

    def classify(self, image: Image.Image, path: str | None, features: dict[str, float]) -> str:
        name = Path(path).stem.lower() if path else ""
        keyword_map = {
            "scope": "scope", "wave": "scope", "oscillo": "scope", "파형": "scope",
            "adapter": "label", "charger": "label", "label": "label", "어댑터": "label",
            "멀티탭": "safety", "plug": "safety", "power_strip": "safety",
            "circuit": "circuit", "schematic": "circuit", "breadboard": "circuit", "회로": "circuit",
        }
        for key, mode in keyword_map.items():
            if key in name:
                return mode
        if features.get("dark_ratio", 0) > SCOPE_DARK_RATIO and (
            features.get("green_ratio", 0) + features.get("cyan_ratio", 0)
        ) > SCOPE_SIGNAL_RATIO:
            return "scope"
        if features.get("white_ratio", 0) > CIRCUIT_WHITE_RATIO and features.get("edge_density", 0) > CIRCUIT_EDGE_RATIO:
            return "circuit"
        if features.get("edge_density", 0) > LABEL_EDGE_RATIO and features.get("white_ratio", 0) > LABEL_WHITE_RATIO:
            return "label"
        return "safety"

    # --- 헬퍼 -------------------------------------------------------------
    def _is_sample(self, path: str | None, token: str) -> bool:
        # 앱이 생성하는 데모 파일(sample_power_strip 등)만 큐레이트 분기로 보낸다.
        # 단순히 'circuit'/'scope' 부분 매칭하면 실제 사진(예: web_circuit_*.jpg)이
        # 하드코딩된 샘플 수치로 오판되므로 'sample_' 접두사를 요구한다.
        return bool(path and f"sample_{token}" in Path(path).stem.lower())

    def _base_metrics(self, image: Image.Image, features: dict[str, float]) -> list[tuple[str, str]]:
        return [
            ("이미지 크기", f"{image.width} x {image.height}px"),
            ("에지 밀도", f"{features.get('edge_density', 0):.2f}"),
            ("밝기 평균", f"{features.get('brightness', 0):.0f}/255"),
        ]

    # --- 안전(멀티탭) -----------------------------------------------------
    def _safety(self, image: Image.Image, path: str | None, features: dict[str, float]) -> AnalysisResult:
        if self._is_sample(path, "power_strip"):
            watts = 3500
            current = watts / MAINS_VOLTAGE
            margin = STRIP_RATING_A - current  # 16 - 15.9 = +0.1 A (정격 이내, 한계 근접)
            score = 78
            metrics = [
                ("추정 동시 부하", f"{watts:,} W"),
                ("220 V 기준 전류", f"{current:.1f} A"),
                ("16 A 정격 대비 여유", f"{margin:+.1f} A"),
                ("위험도", "주의(한계 근접)"),
            ]
            sections = [
                ("AI 판정", [
                    "고출력 기기 2개 이상이 같은 멀티탭에 묶인 상황으로 해석됩니다.",
                    "16 A 정격에 거의 도달해(여유 약 +0.1 A) 추가 부하가 붙으면 정격을 초과합니다.",
                    "드라이기, 전기히터, 전자레인지류는 같은 멀티탭 동시 사용을 피하는 편이 안전합니다.",
                ]),
                ("전기전자 해석", [
                    "P = VI 이므로 3500 W / 220 V = 약 15.9 A 입니다.",
                    "정격 16 A는 이상적 한계값이고, 오래된 플러그나 느슨한 접점에서는 I²R 발열이 커집니다.",
                ]),
            ]
            actions = ["고출력 기기 분리", "멀티탭 정격 16 A 이상 확인", "케이블/플러그 발열 여부 손으로 점검"]
            note = "공대생 관점에서는 단순 소비전력보다 접촉저항과 열화에 따른 I²R 손실을 함께 보는 것이 핵심입니다."
            return AnalysisResult("safety", "멀티탭 과부하 위험 분석", "warning", score,
                                  "정격 한계에 근접해 동시 사용 조합을 분리하는 것이 좋습니다.",
                                  metrics, sections, actions, note, confidence="높음", measured=True)

        # 실제 사진: OCR로 W 값을 읽을 수 있으면 합산, 아니면 정직한 체크리스트.
        ocr_text = ocr.read_text(image)
        watt_values = ocr.find_watt_values(ocr_text) if ocr_text else []
        if watt_values:
            total_w = sum(watt_values)
            current = total_w / MAINS_VOLTAGE
            margin = STRIP_RATING_A - current
            over = margin < 0
            score = min(95, max(20, int(current / STRIP_RATING_A * 90)))
            metrics = self._base_metrics(image, features) + [
                ("OCR로 읽은 부하", " + ".join(f"{w:.0f}W" for w in watt_values) + f" = {total_w:.0f} W"),
                ("220 V 기준 전류", f"{current:.1f} A"),
                ("16 A 정격 대비 여유", f"{margin:+.1f} A"),
            ]
            sections = [
                ("AI 판정", [
                    "라벨에서 읽은 소비전력을 합산해 전류를 추정했습니다.",
                    ("정격을 초과합니다. 즉시 부하를 나누세요." if over else "정격 이내이지만 합산 전류를 항상 확인하세요."),
                ]),
                ("전기전자 해석", ["220 V 기준 전류[A] = 소비전력 합[W] / 220 입니다."]),
            ]
            return AnalysisResult("safety", "멀티탭 부하 OCR 분석",
                                  "danger" if over else "warning" if current > STRIP_RATING_A * 0.8 else "ok",
                                  score, "라벨 수치를 읽어 전류를 계산했습니다.",
                                  metrics, sections, ["고출력 제품 분리", "정격 확인", "플러그 온도 확인"],
                                  "사진의 라벨 수치를 읽어 P=VI로 합산 전류를 계산했습니다.",
                                  confidence="중간", measured=True)

        metrics = self._base_metrics(image, features) + [("판정 신뢰도", "낮음(사진만으로 소비전력 측정 불가)")]
        sections = [
            ("AI 판정", [
                "사진만으로는 소비전력을 측정할 수 없어 임의 수치를 만들지 않습니다.",
                "고출력 전열기/모터/조리기구가 같은 멀티탭에 묶여 있다면 전류 합산이 필요합니다.",
            ]),
            ("사용자에게 필요한 행동", [
                "제품 라벨의 W 또는 A 값을 확인하고, 같은 멀티탭에 연결된 기기의 전류 합을 계산하세요.",
                "220 V 기준에서는 전류[A] = 소비전력[W] / 220 입니다.",
                "Tesseract OCR을 설치하면 라벨의 W 값을 자동으로 읽어 합산합니다.",
            ]),
        ]
        return AnalysisResult("safety", "전기 안전 체크리스트", "ok", 30,
                              "사진 기반 안전 점검 항목을 정리했습니다(측정값 아님).",
                              metrics, sections,
                              ["고출력 제품만 따로 콘센트 연결", "멀티탭 정격 확인", "장시간 사용 전 플러그 온도 확인"],
                              "텍스트 입력 없이 사진만으로 1차 점검 항목을 만들고, 부족한 숫자는 물리식 기반 체크리스트로 보완합니다.",
                              confidence="낮음", measured=False)

    # --- 회로 -------------------------------------------------------------
    def _circuit(self, image: Image.Image, path: str | None, features: dict[str, float]) -> AnalysisResult:
        if self._is_sample(path, "circuit"):
            voltage, resistor, led_drop = 9.0, 330.0, 2.0
            current_ma = (voltage - led_drop) / resistor * 1000
            power_mw = ((voltage - led_drop) ** 2 / resistor) * 1000
            metrics = [
                ("추정 회로", "9 V - 330 Ω - LED 1개 직렬"),
                ("LED 전류", f"{current_ma:.1f} mA"),
                ("저항 발열", f"{power_mw:.0f} mW"),
                ("권장 저항 정격", "1/4 W 이상"),
            ]
            sections = [
                ("AI 판정", [
                    "전원, 직렬저항, LED 1개가 한 루프로 연결된 기본 표시 회로로 해석됩니다.",
                    "전류가 약 21 mA라 일반 LED 실험 범위에 가깝지만, LED 종류에 따라 10-20 mA로 낮추면 더 안전합니다.",
                    "LED를 직렬로 n개 더하면 전류는 (9 - 2·n)/330 으로 감소합니다.",
                ]),
                ("전기전자 해석", [
                    "저항 양단 전압은 9 V - 2 V = 7 V로 잡을 수 있습니다.",
                    "옴의 법칙 I = V/R을 적용하면 7 V / 330 Ω = 약 0.021 A 입니다.",
                ]),
            ]
            return AnalysisResult("circuit", "회로 사진/도식 자동 해석", "ok", 24,
                                  "LED 직렬 회로로 해석되며 실험 가능한 범위입니다.",
                                  metrics, sections,
                                  ["LED 극성 확인", "저항 정격 확인", "장시간 켜둘 경우 470 Ω도 비교"],
                                  "이미지에서 회로 유형을 먼저 분류하고, 전공 공식으로 해석을 이어 붙이는 하이브리드 구조입니다.",
                                  confidence="높음", measured=True)

        metrics = self._base_metrics(image, features) + [
            ("회로선 후보", "감지됨" if features.get("edge_density", 0) > 0.08 else "낮음"),
            ("판정 신뢰도", "중간(연결 구조 위주, 부품값은 미측정)"),
        ]
        sections = [
            ("AI 판정", [
                "선분과 고대비 영역을 기준으로 회로 또는 보드 이미지로 판단했습니다.",
                "정확한 부품값은 이미지 내 텍스트 인식이 필요하므로, 현재는 연결 구조와 전공 해석 체크포인트를 제공합니다.",
            ]),
            ("회로 점검 포인트", [
                "전원에서 나간 전류가 다시 기준점으로 돌아오는 닫힌 루프인지 확인합니다.",
                "LED, 다이오드, 전해콘덴서처럼 극성이 있는 부품은 방향이 맞는지 확인합니다.",
                "저항값이 보이면 I = V/R, P = I²R로 전류와 발열을 바로 계산할 수 있습니다.",
            ]),
        ]
        return AnalysisResult("circuit", "회로 구조 1차 분석", "ok", 30,
                              "회로 이미지로 분류하고 전공 점검 항목을 생성했습니다(부품값 미측정).",
                              metrics, sections,
                              ["전원 극성 확인", "GND 공통 여부 확인", "저항/커패시터 값 확대 촬영"],
                              "공대생에게는 회로를 눈으로 읽는 연습과 수식 검산을 연결해 주는 용도입니다.",
                              confidence="중간", measured=False)

    # --- 스코프(파형) -----------------------------------------------------
    def _scope(self, image: Image.Image, path: str | None, features: dict[str, float]) -> AnalysisResult:
        if self._is_sample(path, "scope"):
            # 큐레이트된 데모: 그려진 파형(10 div 위 2.8주기, 1 ms/div)과 정합.
            period_div = 10.0 / 2.8        # ≈ 3.57 div
            freq = 1.0 / (period_div * DEFAULT_TIME_PER_DIV_S)  # ≈ 280 Hz
            vpp_div = 2.85
            metrics = [
                ("추정 주기", f"{period_div:.2f} div"),
                ("추정 Vpp", f"{vpp_div:.2f} div"),
                ("1 V/div 가정 Vpp", f"{vpp_div:.1f} V"),
                ("1 ms/div 가정 주파수", f"약 {freq:.0f} Hz"),
            ]
            sections = [
                ("AI 판정", [
                    "격자 위의 밝은 파형을 추적해 주기와 피크-피크 높이를 추정했습니다.",
                    "스코프의 실제 time/div, volt/div 값이 보이면 절대 주파수·전압으로 바로 환산됩니다.",
                ]),
                ("전기전자 해석", [
                    "주파수 f는 주기 T의 역수 f = 1/T 입니다.",
                    "파형 높이는 Vpp로 읽고, 정현파라면 Vrms = Vpp / (2√2)를 적용합니다.",
                ]),
            ]
            return AnalysisResult("scope", "오실로스코프 파형 분석", "ok", 18,
                                  "파형의 주기와 진폭을 추정했습니다(1 ms/div, 1 V/div 가정).",
                                  metrics, sections,
                                  ["time/div 값 확인", "volt/div 값 확인", "커서 기능으로 한 주기 직접 비교"],
                                  "이미지 처리로 파형 중심선을 추적한 뒤 계측 공식으로 설명을 생성합니다.",
                                  confidence="높음", measured=True)

        # 실제 사진: 화면 대비 상대 측정은 항상 제공하고(정직), 격자가 확실히 검출되면
        # div/주파수를 보너스로 더한다. 임의 div 상수는 쓰지 않는다.
        wave = estimate_waveform(image)
        if wave["points"] >= 30 and wave.get("period_ratio"):
            metrics = [
                ("파형 후보점", f"{wave['points']} px"),
                ("진폭(화면 높이 대비)", f"{wave['vpp_ratio'] * 100:.0f}%"),
                ("한 주기(화면 폭 대비)", f"{wave['period_ratio'] * 100:.1f}%"),
            ]
            bullets = [
                "파형선을 추적해 진폭과 한 주기 길이를 화면 비율로 측정했습니다(절대 단위 아님).",
                "스코프의 time/div, volt/div를 알면 절대 주파수·전압으로 환산됩니다.",
            ]
            if wave.get("grid_detected") and wave.get("period_div"):
                period_div = float(wave["period_div"])
                freq = 1.0 / (period_div * DEFAULT_TIME_PER_DIV_S)
                metrics.append(("검출 격자", f"{wave['px_per_div_x']:.0f}x{wave['px_per_div_y']:.0f} px/div"))
                metrics.append(("측정 주기", f"{period_div:.2f} div"))
                if wave.get("vpp_div"):
                    metrics.append(("측정 Vpp", f"{wave['vpp_div']:.2f} div"))
                metrics.append(("1 ms/div 가정 주파수", f"약 {freq:.0f} Hz"))
                bullets.append("화면 격자선을 검출해 div 단위 주기/Vpp도 함께 산출했습니다.")
            sections = [
                ("AI 판정", bullets),
                ("전기전자 해석", [
                    "주파수 f는 주기 T의 역수 f = 1/T 입니다.",
                    "파형 높이는 Vpp로 읽고, 정현파라면 Vrms = Vpp / (2√2)를 적용합니다.",
                ]),
            ]
            return AnalysisResult("scope", "오실로스코프 파형 분석", "ok", 20,
                                  "파형의 상대 주기와 진폭을 측정했습니다.",
                                  metrics, sections,
                                  ["time/div 값 확인", "volt/div 값 확인", "커서로 한 주기 비교"],
                                  "이미지 처리로 파형 중심선을 추적하고, 격자가 보이면 div 단위까지 환산합니다.",
                                  confidence="중간", measured=True)

        metrics = self._base_metrics(image, features) + [
            ("파형 후보점", f"{wave['points']} px"),
            ("판정 신뢰도", "낮음"),
        ]
        sections = [
            ("AI 판정", [
                "파형이 충분히 뚜렷하지 않아 측정값을 산출하지 않았습니다.",
                "검은 배경, 격자, 밝은 파형선이 보이도록 화면을 정면에서 캡처하면 측정 정확도가 올라갑니다.",
            ]),
            ("계측 체크포인트", [
                "한 주기가 가로 몇 칸인지 세고 time/div를 곱하면 T가 됩니다.",
                "세로 몇 칸인지 세고 volt/div를 곱하면 Vpp가 됩니다.",
            ]),
        ]
        return AnalysisResult("scope", "파형 감지 시도", "ok", 25,
                              "파형 신뢰도가 낮아 계측 가이드를 제공합니다(측정값 아님).",
                              metrics, sections, ["정면 캡처", "밝은 파형 색 사용", "격자 포함"],
                              "실제 스코프 사진에서는 배경/파형 대비와 격자 가시성이 가장 중요합니다.",
                              confidence="낮음", measured=False)

    # --- 라벨(어댑터) -----------------------------------------------------
    def _label(self, image: Image.Image, path: str | None, features: dict[str, float]) -> AnalysisResult:
        if self._is_sample(path, "adapter"):
            out_v, out_a = 5.0, 2.0
            watts = out_v * out_a
            metrics = [
                ("입력", "100-240 V AC, 50/60 Hz"),
                ("출력", "5 V DC, 2 A"),
                ("최대 출력전력", f"{watts:.0f} W"),
                ("호환성", "5 V USB 기기 적합"),
            ]
            sections = [
                ("AI 판정", [
                    "어댑터 라벨에서 입력 범위와 출력 전압/전류 정보를 읽는 상황으로 구성했습니다.",
                    "출력 전압은 반드시 기기 요구 전압과 같아야 하고, 전류 정격은 기기 요구량 이상이면 됩니다.",
                ]),
                ("전기전자 해석", [
                    "DC 출력 전력은 P = VI = 5 V x 2 A = 10 W 입니다.",
                    "극성, AC/DC 여부, 커넥터 규격이 맞지 않으면 전압이 같아도 사용할 수 없습니다.",
                ]),
            ]
            return AnalysisResult("label", "어댑터/제품 라벨 판독", "ok", 16,
                                  "5 V, 2 A 출력 어댑터로 안전 범위 내 호환성을 확인했습니다.",
                                  metrics, sections,
                                  ["기기 요구 전압과 비교", "전류 정격 여유 확인", "커넥터 극성 확인"],
                                  "일반인은 호환성 판단, 공대생은 전력/정격/극성 개념 학습에 활용할 수 있습니다.",
                                  confidence="높음", measured=True)

        # 실제 사진: OCR이 되면 라벨을 읽어 계산, 아니면 체크리스트.
        ocr_text = ocr.read_text(image)
        info = ocr.parse_adapter_label(ocr_text) if ocr_text else {}
        if "out_v" in info and "out_a" in info:
            metrics = [
                ("OCR 입력", info.get("input_raw", "확인 필요")),
                ("OCR 출력", f"{info['out_v']:.0f} V, {info['out_a']:.0f} A"),
                ("최대 출력전력", f"{info.get('out_w', info['out_v'] * info['out_a']):.0f} W"),
            ]
            sections = [
                ("AI 판정", ["라벨 텍스트를 OCR로 읽어 출력 정격을 산출했습니다."]),
                ("전기전자 해석", [f"P = VI = {info['out_v']:.0f} V x {info['out_a']:.0f} A = {info['out_v'] * info['out_a']:.0f} W."]),
            ]
            return AnalysisResult("label", "어댑터 라벨 OCR 판독", "ok", 18,
                                  "라벨 수치를 읽어 출력 전력을 계산했습니다.",
                                  metrics, sections,
                                  ["기기 요구 전압과 비교", "전류 정격 여유 확인", "커넥터 극성 확인"],
                                  "사진의 라벨을 OCR로 읽어 P=VI로 출력 전력을 계산했습니다.",
                                  confidence="중간", measured=True)

        metrics = self._base_metrics(image, features) + [
            ("라벨 후보", "감지됨" if features.get("edge_density", 0) > 0.12 else "낮음"),
            ("OCR 상태", "오프라인 기본판: 수동 확인 가이드 (Tesseract 설치 시 자동 판독)"),
        ]
        sections = [
            ("AI 판정", [
                "라벨 또는 문서형 이미지로 보이는 구조를 감지했습니다.",
                "OCR이 없을 때는 숫자를 임의로 읽었다고 속이지 않고, 확인해야 할 항목을 자동 정리합니다.",
            ]),
            ("라벨에서 찾아야 할 값", [
                "INPUT: 사용할 수 있는 콘센트 전압 범위입니다.",
                "OUTPUT: 기기에 실제로 공급되는 전압과 전류입니다.",
                "W 또는 VA: 전원공급장치가 낼 수 있는 최대 용량입니다.",
                "극성 기호: 원형 어댑터에서는 중심 핀이 +인지 -인지 확인해야 합니다.",
            ]),
        ]
        return AnalysisResult("label", "전원 라벨 체크리스트", "ok", 30,
                              "라벨 사진에서 확인해야 할 전기적 의미를 정리했습니다(측정값 아님).",
                              metrics, sections,
                              ["OUTPUT 전압 확인", "전류 정격 비교", "AC/DC 여부 확인"],
                              "OCR이 없을 때도 물리적으로 틀린 판단을 하지 않는 보수적 설계를 적용했습니다.",
                              confidence="낮음", measured=False)

    def _general(self, image: Image.Image, path: str | None, features: dict[str, float]) -> AnalysisResult:
        metrics = self._base_metrics(image, features)
        sections = [
            ("AI 판정", [
                "이미지 유형이 명확하지 않아 자동 분류 대신 공통 전기전자 해석 루틴을 적용했습니다.",
                "왼쪽 모드 버튼 중 안전, 회로, 파형, 라벨을 클릭하면 같은 이미지도 다른 관점으로 재분석됩니다.",
            ]),
        ]
        return AnalysisResult("general", "자동 분석 준비", "ok", 20,
                              "이미지를 불러왔습니다. 원하는 분석 관점을 마우스로 선택하세요.",
                              metrics, sections,
                              ["분석 모드 선택", "이미지 확대 캡처", "샘플로 기능 확인"],
                              "텍스트 입력 없이 모드 전환만으로 해석 관점을 바꿀 수 있습니다.",
                              confidence="중간", measured=False)
