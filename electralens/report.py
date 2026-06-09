"""GUI 없이 분석 결과를 캔버스에 합성해 보고서/캡처용 PNG를 생성한다.

(이전 버전의 render_demo_screenshot / render_analysis_screenshot는 우측 결과 패널과
폰트 로딩 코드가 거의 통째로 중복돼 있었다. 공통 부분을 _load_fonts /
_draw_result_panel 헬퍼로 추출했다.)
"""
from __future__ import annotations

import textwrap
from pathlib import Path

from PIL import Image, ImageDraw

from .analyzer import ElectraAnalyzer
from .models import APP_NAME, APP_TAGLINE, AnalysisResult, severity_color, severity_fill
from .samples import generate_samples
from .util import fit_image, safe_font


def _load_fonts() -> dict:
    return {
        "title": safe_font(34, True),
        "h2": safe_font(24, True),
        "body": safe_font(20),
        "small": safe_font(16),
    }


def _draw_result_panel(d: ImageDraw.ImageDraw, result: AnalysisResult, fonts: dict,
                       x: int = 966, wrap_summary: int | None = None) -> None:
    """우측 'AI 분석 결과' 패널을 그린다(두 렌더러가 공유)."""
    h2, body, small = fonts["h2"], fonts["body"], fonts["small"]
    color = severity_color(result.severity)
    d.text((x, 122), "AI 분석 결과", font=h2, fill="#12242e")
    d.rounded_rectangle((x, 172, x + 418, 240), radius=12, fill=severity_fill(result.severity))
    d.text((x + 24, 194), f"주의 점수  {result.score}/100", font=h2, fill=color)

    y = 274
    if wrap_summary:
        for line in textwrap.wrap(result.summary, width=wrap_summary):
            d.text((x, y), line, font=body, fill="#1b2c34")
            y += 30
    else:
        d.text((x, y), result.summary, font=body, fill="#1b2c34")
        y += 30
    y += 28

    d.text((x, y), "핵심 수치", font=h2, fill="#12242e")
    y += 38
    for key, value in result.metrics[:4]:
        d.text((x + 18, y), f"- {key}: {value}", font=body, fill="#1b2c34")
        y += 34
    y += 18

    d.text((x, y), "마우스로 바로 할 일", font=h2, fill="#12242e")
    y += 38
    for item in result.actions[:3]:
        d.rounded_rectangle((x + 18, y - 6, x + 400, y + 32), radius=12, fill="#eef6f2")
        d.text((x + 38, y + 12), item, font=body, fill="#1d5e48", anchor="lm")
        y += 48
    y += 18

    d.text((x, y), "공대생 포인트", font=h2, fill="#12242e")
    y += 38
    for line in textwrap.wrap(result.student_note, width=31)[:4]:
        d.text((x + 18, y), line, font=small, fill="#1b2c34")
        y += 26


def render_demo_screenshot(path: Path, result: AnalysisResult | None = None) -> None:
    samples = generate_samples(path.parent / "samples")
    image = Image.open(samples["safety"]).convert("RGB")
    analyzer = ElectraAnalyzer()
    r = result or analyzer.analyze(image, str(samples["safety"]), "auto")
    fonts = _load_fonts()

    canvas = Image.new("RGB", (1440, 920), "#edf2f4")
    d = ImageDraw.Draw(canvas)
    d.text((34, 26), APP_NAME, font=fonts["title"], fill="#12242e")
    d.text((320, 38), APP_TAGLINE, font=fonts["small"], fill="#53646c")
    d.rounded_rectangle((28, 92, 312, 860), radius=18, fill="#ffffff")
    d.rounded_rectangle((336, 92, 916, 860), radius=18, fill="#ffffff")
    d.rounded_rectangle((940, 92, 1410, 860), radius=18, fill="#ffffff")

    d.text((54, 122), "마우스 전용 입력", font=fonts["h2"], fill="#12242e")
    for i, label in enumerate(["이미지 열기", "클립보드", "멀티탭 안전", "LED 회로", "스코프 파형", "어댑터 라벨"]):
        y = 180 + i * 72
        d.rounded_rectangle((54, y, 286, y + 48), radius=12, fill="#f4f8f9", outline="#c4d1d6")
        d.text((170, y + 24), label, font=fonts["body"], fill="#263941", anchor="mm")

    d.text((362, 122), "이미지 미리보기", font=fonts["h2"], fill="#12242e")
    preview = fit_image(image, 520, 560)
    px, py = 366, 184
    d.rounded_rectangle((362, 168, 890, 744), radius=16, fill="#17242b")
    canvas.paste(preview, (px + (520 - preview.width) // 2, py + (540 - preview.height) // 2))
    d.rectangle((px + 16, py + 16, px + 300, py + 72), fill=severity_color(r.severity))
    d.text((px + 32, py + 44), r.title, font=fonts["small"], fill="white", anchor="lm")

    _draw_result_panel(d, r, fonts)
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path)


def render_analysis_screenshot(input_path: Path, output_path: Path, mode: str = "auto") -> None:
    image = Image.open(input_path).convert("RGB")
    analyzer = ElectraAnalyzer()
    result = analyzer.analyze(image, str(input_path), mode)
    fonts = _load_fonts()

    canvas = Image.new("RGB", (1440, 920), "#edf2f4")
    d = ImageDraw.Draw(canvas)
    d.text((34, 26), APP_NAME, font=fonts["title"], fill="#12242e")
    d.text((320, 38), "실제 웹 이미지 분석 결과", font=fonts["small"], fill="#53646c")
    d.rounded_rectangle((28, 92, 912, 860), radius=18, fill="#ffffff")
    d.rounded_rectangle((940, 92, 1410, 860), radius=18, fill="#ffffff")

    d.text((58, 122), "입력 이미지", font=fonts["h2"], fill="#12242e")
    preview = fit_image(image, 820, 620)
    px, py = 58, 180
    d.rounded_rectangle((54, 164, 886, 800), radius=16, fill="#17242b")
    canvas.paste(preview, (px + (820 - preview.width) // 2, py + (590 - preview.height) // 2))
    color = severity_color(result.severity)
    d.rectangle((74, 184, 380, 240), fill=color)
    d.text((94, 212), result.title, font=fonts["small"], fill="white", anchor="lm")
    d.text((58, 818), f"파일: {input_path.name}", font=fonts["small"], fill="#53646c")

    _draw_result_panel(d, result, fonts, wrap_summary=30)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)
