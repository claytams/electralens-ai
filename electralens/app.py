"""Tkinter 데스크톱 UI.

3분할 레이아웃(좌: 입력/샘플/모드/캡처, 중: 미리보기 캔버스, 우: 게이지+결과텍스트)과
드래그 스마트 프로브를 제공한다.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageGrab, ImageTk

from .analyzer import ElectraAnalyzer
from .models import (
    APP_NAME,
    APP_TAGLINE,
    AnalysisResult,
    MAX_IMAGE_PIXELS,
    MODE_LABELS,
    MODE_ORDER,
    WINDOW_H,
    WINDOW_W,
    severity_color,
)
from .probe import smart_probe_region
from .samples import generate_samples
from .util import extension_ok, fit_image, writable_runtime_dir
from .report import render_demo_screenshot

# 신뢰 불가 이미지 디코딩 폭탄 방어.
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


class ElectraLensApp:
    def __init__(self, root: tk.Tk, initial_path: str | None = None) -> None:
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry(f"{WINDOW_W}x{WINDOW_H}")
        self.root.minsize(1080, 680)
        self.analyzer = ElectraAnalyzer()
        self.samples = generate_samples()
        self.image: Image.Image | None = None
        self.image_path: str | None = None
        self.photo: ImageTk.PhotoImage | None = None
        self.display_box: tuple[int, int, int, int] | None = None
        self.probe_rect: tuple[int, int, int, int] | None = None
        self.drag_start: tuple[int, int] | None = None
        self.drag_preview_id: int | None = None
        self.probe_text: str | None = None
        self.mode = tk.StringVar(value="auto")
        self.status = tk.StringVar(value="이미지 열기, 클립보드, 샘플 버튼을 사용하세요.")
        self.result: AnalysisResult | None = None
        self._build_style()
        self._build_ui()
        self.root.bind("<Control-o>", lambda _e: self._shortcut(self.open_file))
        self.root.bind("<Control-O>", lambda _e: self._shortcut(self.open_file))
        self.root.bind("<Control-v>", lambda _e: self._shortcut(self.from_clipboard))
        self.root.bind("<Control-V>", lambda _e: self._shortcut(self.from_clipboard))
        if initial_path and extension_ok(initial_path):
            self.load_path(initial_path)
        else:
            self.load_path(str(self.samples["safety"]))

    def _shortcut(self, action) -> str:
        action()
        return "break"

    def _reset_probe(self) -> None:
        self.probe_rect = None
        self.drag_start = None
        self.probe_text = None

    def _build_style(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TFrame", background="#edf2f4")
        style.configure("Panel.TFrame", background="#ffffff")
        style.configure("Title.TLabel", font=("Malgun Gothic", 20, "bold"), background="#edf2f4", foreground="#12242e")
        style.configure("Sub.TLabel", font=("Malgun Gothic", 10), background="#edf2f4", foreground="#53646c")
        style.configure("PanelTitle.TLabel", font=("Malgun Gothic", 13, "bold"), background="#ffffff", foreground="#12242e")
        style.configure("TButton", font=("Malgun Gothic", 10), padding=(10, 8))
        style.configure("Mode.TButton", font=("Malgun Gothic", 10, "bold"), padding=(10, 10))
        style.configure("Status.TLabel", font=("Malgun Gothic", 9), background="#dfe8eb", foreground="#33454e")

    def _build_ui(self) -> None:
        root = self.root
        header = ttk.Frame(root, padding=(18, 14, 18, 10))
        header.pack(fill="x")
        ttk.Label(header, text=APP_NAME, style="Title.TLabel").pack(side="left")
        ttk.Label(header, text=APP_TAGLINE, style="Sub.TLabel").pack(side="left", padx=(16, 0), pady=(8, 0))

        body = ttk.Frame(root, padding=(14, 0, 14, 12))
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body, style="Panel.TFrame", padding=14)
        left.pack(side="left", fill="y", padx=(0, 10))
        left.configure(width=250)
        left.pack_propagate(False)

        center = ttk.Frame(body, style="Panel.TFrame", padding=14)
        center.pack(side="left", fill="both", expand=True, padx=(0, 10))

        right = ttk.Frame(body, style="Panel.TFrame", padding=14)
        right.pack(side="right", fill="both")
        right.configure(width=360)
        right.pack_propagate(False)

        ttk.Label(left, text="이미지 투입", style="PanelTitle.TLabel").pack(anchor="w")
        drop = tk.Canvas(left, width=214, height=150, bg="#f5fafb", highlightthickness=1, highlightbackground="#b8c7cd", cursor="hand2")
        drop.pack(fill="x", pady=(10, 10))
        drop.create_text(107, 46, text="사진/스크린샷", font=("Malgun Gothic", 15, "bold"), fill="#19323d")
        drop.create_text(107, 84, text="클릭해서 이미지 열기", font=("Malgun Gothic", 10), fill="#5c6d74")
        drop.create_text(107, 114, text="텍스트 입력 없음", font=("Malgun Gothic", 10, "bold"), fill="#2a8d68")
        drop.bind("<Button-1>", lambda _e: self.open_file())
        ttk.Button(left, text="이미지 열기", command=self.open_file).pack(fill="x", pady=3)
        ttk.Button(left, text="클립보드에서 가져오기", command=self.from_clipboard).pack(fill="x", pady=3)

        ttk.Label(left, text="샘플 원클릭", style="PanelTitle.TLabel").pack(anchor="w", pady=(18, 6))
        sample_buttons = [("멀티탭 안전", "safety"), ("LED 회로", "circuit"), ("스코프 파형", "scope"), ("어댑터 라벨", "label")]
        for label, key in sample_buttons:
            ttk.Button(left, text=label, command=lambda k=key: self.load_path(str(self.samples[k]))).pack(fill="x", pady=3)

        ttk.Label(left, text="분석 모드", style="PanelTitle.TLabel").pack(anchor="w", pady=(18, 6))
        for value in MODE_ORDER:
            rb = ttk.Radiobutton(left, text=MODE_LABELS[value], value=value, variable=self.mode, command=self.run_analysis)
            rb.pack(anchor="w", pady=2)

        ttk.Button(left, text="결과 캡처 저장", command=self.save_capture).pack(fill="x", pady=(22, 3))

        ttk.Label(center, text="이미지 미리보기", style="PanelTitle.TLabel").pack(anchor="w")
        self.canvas = tk.Canvas(center, bg="#17242b", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, pady=(10, 0))
        self.canvas.bind("<Configure>", lambda _e: self.refresh_image())
        self.canvas.bind("<ButtonPress-1>", self.start_probe_drag)
        self.canvas.bind("<B1-Motion>", self.update_probe_drag)
        self.canvas.bind("<ButtonRelease-1>", self.finish_probe_drag)

        ttk.Label(right, text="AI 분석 결과", style="PanelTitle.TLabel").pack(anchor="w")
        self.gauge = tk.Canvas(right, height=70, bg="#ffffff", highlightthickness=0)
        self.gauge.pack(fill="x", pady=(8, 8))
        self.result_text = tk.Text(right, wrap="word", font=("Malgun Gothic", 10), bg="#fbfcfb",
                                   fg="#1b2c34", relief="flat", padx=12, pady=12, height=26)
        self.result_text.pack(fill="both", expand=True)
        self.result_text.configure(state="disabled")

        status = ttk.Label(root, textvariable=self.status, style="Status.TLabel", padding=(14, 5))
        status.pack(fill="x", side="bottom")

    def open_file(self) -> None:
        file_path = filedialog.askopenfilename(
            title="분석할 이미지 선택",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"), ("All files", "*.*")],
        )
        if file_path:
            self.load_path(file_path)

    def from_clipboard(self) -> None:
        try:
            data = ImageGrab.grabclipboard()
            if isinstance(data, Image.Image):
                self.image = data.convert("RGB")
                self.image_path = None
                self._reset_probe()
                self.status.set("클립보드 이미지를 가져왔습니다.")
                self.run_analysis()
                return
            if isinstance(data, list) and data:
                for item in data:
                    if extension_ok(item):
                        self.load_path(item)
                        return
            messagebox.showinfo(APP_NAME, "클립보드에서 이미지를 찾지 못했습니다.")
        except Exception:
            messagebox.showerror(APP_NAME, "클립보드 이미지를 읽지 못했습니다. 지원되는 이미지인지 확인하세요.")

    def load_path(self, file_path: str) -> None:
        if not extension_ok(file_path):
            self.status.set("이미지 파일만 분석할 수 있습니다.")
            return
        try:
            image = Image.open(file_path)
            image.load()
            image = image.convert("RGB")
        except Image.DecompressionBombError:
            messagebox.showerror(APP_NAME, "이미지가 너무 큽니다. 더 작은 이미지를 사용하세요.")
            return
        except Exception:
            messagebox.showerror(APP_NAME, f"이미지를 열 수 없습니다: {Path(file_path).name}")
            return
        self.image = image
        self.image_path = file_path
        self._reset_probe()
        self.status.set(f"불러옴: {Path(file_path).name}")
        self.run_analysis()

    def run_analysis(self) -> None:
        if self.image is None:
            return
        self.result = self.analyzer.analyze(self.image, self.image_path, self.mode.get())
        self.refresh_image()
        self.render_result()

    def refresh_image(self) -> None:
        if self.image is None:
            self.canvas.delete("all")
            return
        cw = max(200, self.canvas.winfo_width())
        ch = max(200, self.canvas.winfo_height())
        img = fit_image(self.image, cw - 30, ch - 30)
        self.photo = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(cw // 2, ch // 2, image=self.photo, anchor="center")
        x0 = (cw - img.width) // 2
        y0 = (ch - img.height) // 2
        self.display_box = (x0, y0, img.width, img.height)
        if self.result:
            color = severity_color(self.result.severity)
            self.canvas.create_rectangle(x0, y0, x0 + img.width, y0 + img.height, outline=color, width=4)
            self.canvas.create_rectangle(x0 + 14, y0 + 14, x0 + 250, y0 + 58, fill=color, outline="")
            self.canvas.create_text(x0 + 28, y0 + 36, text=self.result.title, anchor="w", fill="white", font=("Malgun Gothic", 11, "bold"))
        if self.probe_rect and self.display_box:
            rx0, ry0, rx1, ry1 = self.probe_rect
            cx0 = x0 + int(rx0 / self.image.width * img.width)
            cy0 = y0 + int(ry0 / self.image.height * img.height)
            cx1 = x0 + int(rx1 / self.image.width * img.width)
            cy1 = y0 + int(ry1 / self.image.height * img.height)
            self.canvas.create_rectangle(cx0, cy0, cx1, cy1, outline="#42ffd0", width=3)
            self.canvas.create_rectangle(cx0, max(y0, cy0 - 34), min(cx0 + 240, x0 + img.width), max(y0 + 30, cy0 - 4), fill="#10252c", outline="#42ffd0")
            self.canvas.create_text(cx0 + 10, max(y0 + 15, cy0 - 19), text="드래그 구역 프로브", anchor="w", fill="#d5fff5", font=("Malgun Gothic", 10, "bold"))

    def canvas_to_image_point(self, x: int, y: int) -> tuple[int, int] | None:
        if self.image is None or self.display_box is None:
            return None
        x0, y0, w, h = self.display_box
        if not (x0 <= x <= x0 + w and y0 <= y <= y0 + h):
            return None
        img_x = int((x - x0) / max(1, w) * self.image.width)
        img_y = int((y - y0) / max(1, h) * self.image.height)
        return (max(0, min(self.image.width - 1, img_x)), max(0, min(self.image.height - 1, img_y)))

    def start_probe_drag(self, event: tk.Event) -> None:
        if self.canvas_to_image_point(event.x, event.y) is None:
            return
        self.drag_start = (event.x, event.y)
        if self.drag_preview_id is not None:
            self.canvas.delete(self.drag_preview_id)
            self.drag_preview_id = None

    def update_probe_drag(self, event: tk.Event) -> None:
        if not self.drag_start:
            return
        if self.drag_preview_id is not None:
            self.canvas.delete(self.drag_preview_id)
        x0, y0 = self.drag_start
        self.drag_preview_id = self.canvas.create_rectangle(x0, y0, event.x, event.y, outline="#42ffd0", width=2, dash=(6, 3))

    def finish_probe_drag(self, event: tk.Event) -> None:
        if self.image is None or self.drag_start is None:
            return
        start = self.canvas_to_image_point(*self.drag_start)
        end = self.canvas_to_image_point(event.x, event.y)
        if self.drag_preview_id is not None:
            self.canvas.delete(self.drag_preview_id)
            self.drag_preview_id = None
        self.drag_start = None
        if start is None or end is None:
            return
        x0, y0 = start
        x1, y1 = end
        if abs(x1 - x0) < 18 or abs(y1 - y0) < 18:
            pad = max(36, min(self.image.width, self.image.height) // 14)
            cx, cy = x1, y1
            x0, y0, x1, y1 = cx - pad, cy - pad, cx + pad, cy + pad
        rect = (
            max(0, min(x0, x1)),
            max(0, min(y0, y1)),
            min(self.image.width - 1, max(x0, x1)),
            min(self.image.height - 1, max(y0, y1)),
        )
        if rect[2] - rect[0] < 8 or rect[3] - rect[1] < 8:
            return
        self.probe_rect = rect
        self.probe_text = smart_probe_region(self.image, rect, self.mode.get(), self.image_path)
        self.status.set(f"스마트 프로브 구역: {rect[2] - rect[0]} x {rect[3] - rect[1]} px")
        self.refresh_image()
        self.render_result()

    def render_result(self) -> None:
        if not self.result:
            return
        r = self.result
        self._draw_gauge(r)
        self.result_text.configure(state="normal")
        self.result_text.delete("1.0", "end")
        parts = [f"{r.title}\n", f"{r.summary}\n", "핵심 수치"]
        for key, value in r.metrics:
            parts.append(f"  - {key}: {value}")
        for heading, bullets in r.sections:
            parts.append(f"\n{heading}")
            for item in bullets:
                parts.append(f"  - {item}")
        parts.append("\n마우스로 바로 할 일")
        for item in r.actions:
            parts.append(f"  - {item}")
        if self.probe_text:
            parts.append("\n드래그 구역 스마트 프로브")
            for line in self.probe_text.splitlines():
                parts.append(f"  - {line}")
        parts.append("\n공대생 포인트")
        parts.append(f"  - {r.student_note}")
        self.result_text.insert("1.0", "\n".join(parts))
        self.result_text.configure(state="disabled")

    def _draw_gauge(self, r: AnalysisResult) -> None:
        c = self.gauge
        c.delete("all")
        w = max(280, c.winfo_width())
        color = severity_color(r.severity)
        bg = "#e8eef0"
        c.create_text(8, 12, text="주의 점수", anchor="w", fill="#41535c", font=("Malgun Gothic", 10, "bold"))
        c.create_rectangle(8, 34, w - 8, 52, fill=bg, outline="")
        fill_w = int((w - 16) * min(100, max(0, r.score)) / 100)
        c.create_rectangle(8, 34, 8 + fill_w, 52, fill=color, outline="")
        c.create_text(w - 12, 12, text=f"{r.score}/100", anchor="e", fill=color, font=("Malgun Gothic", 12, "bold"))

    def save_capture(self) -> None:
        out_dir = writable_runtime_dir() / "captures"
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / f"electralens_capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        render_demo_screenshot(target, self.result)
        self.status.set(f"캡처 저장: {target}")
        messagebox.showinfo(APP_NAME, f"캡처를 저장했습니다.\n{target}")
