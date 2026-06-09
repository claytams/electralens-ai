"""명령행 진입점과 헤드리스 유틸리티.

GUI 외에 --smoke-test / --make-screenshots / --render-analysis-screenshot 헤드리스
모드를 제공한다. 이미지 경로를 인자로 주면(또는 exe에 드래그하면) 그 이미지로 시작한다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image

from .analyzer import ElectraAnalyzer
from .samples import generate_samples
from .util import extension_ok, writable_runtime_dir


def run_smoke_test() -> int:
    """샘플 4종을 분석하고 결과 불변식을 어설션으로 검증한다."""
    samples = generate_samples()
    analyzer = ElectraAnalyzer()
    results = []
    for key, p in samples.items():
        img = Image.open(p).convert("RGB")
        r = analyzer.analyze(img, str(p), "auto")
        assert r.severity in {"ok", "warning", "danger"}, f"bad severity: {r.severity}"
        assert 0 <= r.score <= 100, f"score out of range: {r.score}"
        assert r.title and r.summary, "empty title/summary"
        results.append({"sample": key, "mode": r.mode, "title": r.title,
                        "severity": r.severity, "score": r.score, "measured": r.measured})
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


def make_screenshots(out_dir: str) -> int:
    from .report import render_demo_screenshot

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    render_demo_screenshot(out / "electralens_main.png")
    samples = generate_samples(out / "samples")
    analyzer = ElectraAnalyzer()
    for key, p in samples.items():
        img = Image.open(p).convert("RGB")
        result = analyzer.analyze(img, str(p), "auto")
        render_demo_screenshot(out / f"electralens_{key}.png", result)
    print(str(out))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    args = argv[1:]

    if "--smoke-test" in args:
        return run_smoke_test()
    if "--make-screenshots" in args:
        idx = args.index("--make-screenshots")
        out_dir = args[idx + 1] if idx + 1 < len(args) else str(writable_runtime_dir() / "screenshots")
        return make_screenshots(out_dir)
    if "--render-analysis-screenshot" in args:
        from .report import render_analysis_screenshot

        idx = args.index("--render-analysis-screenshot")
        input_path = Path(args[idx + 1])
        output_path = Path(args[idx + 2])
        mode = args[idx + 3] if idx + 3 < len(args) else "auto"
        render_analysis_screenshot(input_path, output_path, mode)
        return 0

    # GUI 모드 (tkinter는 헤드리스 환경에서 실패할 수 있으므로 여기서 import)
    import tkinter as tk

    from .app import ElectraLensApp

    initial_path = next((arg for arg in args if extension_ok(arg)), None)
    root = tk.Tk()
    ElectraLensApp(root, initial_path=initial_path)
    root.mainloop()
    return 0
