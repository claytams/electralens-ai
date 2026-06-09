"""데모용 샘플 이미지를 절차적으로 합성한다.

별도 에셋을 배포하지 않아도 첫 실행부터 4종(멀티탭/회로/스코프/어댑터) 데모가
가능하도록 Pillow로 그려 생성한다.
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from .util import safe_font, writable_runtime_dir

try:  # pragma: no cover
    import numpy as np
except Exception:  # pragma: no cover
    np = None


def generate_samples(out_dir: Path | None = None) -> dict[str, Path]:
    root = out_dir or (writable_runtime_dir() / "samples")
    root.mkdir(parents=True, exist_ok=True)
    paths = {
        "safety": root / "sample_power_strip.png",
        "circuit": root / "sample_circuit.png",
        "scope": root / "sample_scope.png",
        "label": root / "sample_adapter.png",
    }
    make_power_strip(paths["safety"])
    make_circuit(paths["circuit"])
    make_scope(paths["scope"])
    make_adapter(paths["label"])
    return paths


def add_paper_noise(img: Image.Image, strength: int = 10) -> Image.Image:
    if np is None:
        return img
    arr = np.asarray(img).astype(np.int16)
    noise = np.random.default_rng(42).normal(0, strength, arr.shape).astype(np.int16)
    return Image.fromarray(np.clip(arr + noise, 0, 255).astype(np.uint8), "RGB")


def soft_shadow(base, box, radius=24, offset=(10, 12), alpha=70) -> None:
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x0, y0, x1, y1 = box
    ox, oy = offset
    d.rounded_rectangle((x0 + ox, y0 + oy, x1 + ox, y1 + oy), radius=radius, fill=(0, 0, 0, alpha))
    base.alpha_composite(layer.filter(ImageFilter.GaussianBlur(14)))


def draw_cable(d, points, color="#252b30", width=14) -> None:
    d.line(points, fill=color, width=width, joint="curve")
    d.line(points, fill="#58636a", width=max(2, width // 4), joint="curve")


def make_power_strip(path: Path) -> None:
    img = Image.new("RGBA", (1280, 820), "#dfe8ea")
    d = ImageDraw.Draw(img)
    for y in range(820):
        tone = 226 + int(16 * y / 820)
        d.line((0, y, 1280, y), fill=(tone, tone + 4, tone + 6, 255))
    img = add_paper_noise(img.convert("RGB"), 5).convert("RGBA")
    d = ImageDraw.Draw(img)
    title = safe_font(42, True)
    body = safe_font(25)
    small = safe_font(18)
    tiny = safe_font(14)

    strip = (160, 280, 1120, 565)
    soft_shadow(img, strip, radius=62, offset=(18, 22), alpha=85)
    d.rounded_rectangle(strip, radius=62, fill="#f6fafb", outline="#92a5ad", width=5)
    d.rounded_rectangle((190, 310, 1090, 535), radius=48, fill="#fbfdfe", outline="#d7e2e6", width=2)
    d.rounded_rectangle((935, 328, 1045, 388), radius=18, fill="#dfe9e9", outline="#9eb0b6", width=3)
    d.ellipse((965, 342, 1002, 379), fill="#e95546", outline="#b2352b", width=2)
    d.text((990, 405), "16A MAX", font=tiny, fill="#596970", anchor="mm")

    socket_xs = [280, 450, 620, 790]
    for x in socket_xs:
        d.ellipse((x - 58, 370, x + 58, 486), fill="#e7eff2", outline="#8ca0aa", width=4)
        d.ellipse((x - 42, 386, x + 42, 470), fill="#f9fbfc", outline="#c0ccd2", width=2)
        d.rounded_rectangle((x - 24, 406, x - 11, 452), radius=4, fill="#3e4a50")
        d.rounded_rectangle((x + 11, 406, x + 24, 452), radius=4, fill="#3e4a50")
        d.ellipse((x - 8, 455, x + 8, 471), fill="#63747c")

    draw_cable(d, [(185, 550), (130, 665), (56, 760)], "#303940", 20)
    devices = [
        ("HEATER", "1800W", 280, "#e85443", [(280, 272), (260, 205), (235, 155)]),
        ("DRYER", "1500W", 450, "#e85443", [(450, 272), (438, 190), (470, 122)]),
        ("LAPTOP", "90W", 620, "#2f946e", [(620, 272), (640, 190), (720, 150)]),
        ("CHARGER", "65W", 790, "#2f946e", [(790, 272), (825, 200), (900, 162)]),
    ]
    for label, watts, x, color, cable in devices:
        draw_cable(d, cable, color, 10)
        d.rounded_rectangle((x - 66, 205, x + 66, 270), radius=14, fill=color)
        d.text((x, 224), label, font=tiny, fill="white", anchor="mm")
        d.text((x, 250), watts, font=small, fill="white", anchor="mm")
        d.rounded_rectangle((x - 38, 270, x + 38, 308), radius=8, fill="#2f3d43")

    d.text((72, 62), "Realistic Power Strip Safety Sample", font=title, fill="#16323f")
    d.rounded_rectangle((72, 625, 1160, 735), radius=22, fill="#ffffffcc", outline="#c5d1d6")
    d.text((102, 650), "Scenario: two high-power appliances share one 16A power strip.", font=body, fill="#16323f")
    d.text((102, 690), "ElectraLens estimates total load, current, and heat-risk checklist without typing.", font=small, fill="#526770")
    img.convert("RGB").save(path)


def make_circuit(path: Path) -> None:
    img = Image.new("RGBA", (1280, 820), "#eef2f4")
    img = add_paper_noise(img.convert("RGB"), 4).convert("RGBA")
    d = ImageDraw.Draw(img)
    title = safe_font(42, True)
    body = safe_font(24)
    small = safe_font(18)
    tiny = safe_font(12)
    d.text((72, 54), "Breadboard LED Circuit Sample", font=title, fill="#16323f")
    board = (115, 185, 1045, 645)
    soft_shadow(img, board, radius=22, offset=(16, 22), alpha=70)
    d.rounded_rectangle(board, radius=20, fill="#f7f3df", outline="#c2b98f", width=4)
    d.rectangle((155, 230, 1005, 285), fill="#f1ead2")
    d.rectangle((155, 535, 1005, 590), fill="#f1ead2")
    d.line((170, 248, 990, 248), fill="#cc4742", width=3)
    d.line((170, 568, 990, 568), fill="#2f78c4", width=3)
    for x in range(180, 990, 28):
        for y in list(range(330, 505, 28)) + [248, 568]:
            d.ellipse((x - 3, y - 3, x + 3, y + 3), fill="#6d6757")
        if x % 140 == 12:
            d.text((x, 610), str((x - 180) // 28 + 1), font=tiny, fill="#7c7563", anchor="mm")
    d.rectangle((560, 310, 580, 522), fill="#ebe3c8")

    # 9V battery
    soft_shadow(img, (930, 400, 1145, 625), radius=20, offset=(10, 12), alpha=80)
    d.rounded_rectangle((930, 400, 1145, 625), radius=22, fill="#161b20", outline="#111", width=3)
    d.rectangle((970, 445, 1085, 595), fill="#d2a64a")
    d.rectangle((1005, 425, 1115, 512), fill="#1f4e8c")
    d.text((1058, 465), "9V", font=safe_font(42, True), fill="#f8d55c", anchor="mm")
    d.text((1030, 545), "BATTERY", font=small, fill="white", anchor="mm")

    # Wires
    d.line([(1000, 405), (920, 315), (720, 335), (545, 340)], fill="#d94a50", width=10, joint="curve")
    d.line([(1095, 405), (1055, 320), (840, 250), (490, 250), (310, 340)], fill="#22282d", width=10, joint="curve")
    d.line([(255, 380), (260, 520), (450, 520), (450, 475)], fill="#d94a50", width=8, joint="curve")
    d.line([(365, 385), (365, 535), (520, 535)], fill="#22282d", width=8, joint="curve")

    # Resistor with bands
    d.line((545, 340, 640, 340), fill="#242b30", width=5)
    d.rounded_rectangle((640, 318, 760, 362), radius=20, fill="#d6bd8d", outline="#8a7654", width=2)
    for x, color in [(664, "#f06b34"), (690, "#f06b34"), (716, "#5b2b16"), (744, "#d8b64c")]:
        d.rectangle((x, 319, x + 10, 361), fill=color)
    d.line((760, 340, 850, 340), fill="#242b30", width=5)
    d.text((700, 300), "330 ohm", font=small, fill="#17303b", anchor="mm")

    # 단일 LED (해석 문구가 'LED 1개 기준'이므로 그림도 1개로 맞춤)
    x, y, color = 305, 398, "#31c67a"
    d.line((x - 12, y + 42, x - 12, y + 96), fill="#a6a6a6", width=4)
    d.line((x + 14, y + 42, x + 14, y + 96), fill="#a6a6a6", width=4)
    d.ellipse((x - 24, y - 8, x + 30, y + 52), fill=color, outline="#6b6b6b", width=2)
    d.ellipse((x - 10, y + 2, x + 9, y + 22), fill="#ffffff88")
    d.rounded_rectangle((125, 675, 1160, 745), radius=18, fill="#eef6f2", outline="#bfd5ca")
    d.text((155, 694), "Detected demo: 9V battery + 330 ohm resistor + one LED on a solderless breadboard.", font=body, fill="#1d5e48")
    img.convert("RGB").save(path)


def make_scope(path: Path) -> None:
    img = Image.new("RGBA", (1280, 820), "#1b2229")
    d = ImageDraw.Draw(img)
    title = safe_font(40, True)
    body = safe_font(20)
    tiny = safe_font(14)
    d.text((70, 44), "Digital Oscilloscope Waveform Sample", font=title, fill="#d5fff5")
    body_box = (90, 125, 1190, 735)
    soft_shadow(img, body_box, radius=32, offset=(18, 24), alpha=100)
    d.rounded_rectangle(body_box, radius=32, fill="#2b343c", outline="#56636b", width=4)
    screen = (145, 185, 890, 645)
    d.rounded_rectangle(screen, radius=16, fill="#071018", outline="#536b74", width=4)
    left, top, right, bottom = screen
    for i in range(11):
        x = left + i * (right - left) / 10
        d.line((x, top, x, bottom), fill="#1c3740", width=1 if i != 5 else 3)
    for j in range(9):
        y = top + j * (bottom - top) / 8
        d.line((left, y, right, y), fill="#1c3740", width=1 if j != 4 else 3)
    # 가로 10 div × 1.00 ms/div = 10 ms 화면. 2.8주기 → 280 Hz (라벨과 일치).
    cycles = 2.8
    pts = []
    for x in range(left + 8, right - 8):
        t = (x - left) / (right - left)
        y = (top + bottom) / 2 + math.sin(t * math.tau * cycles) * 82 + math.sin(t * math.tau * 8.4) * 8
        pts.append((x, y))
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.line(pts, fill=(66, 255, 208, 120), width=11, joint="curve")
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(4)))
    d = ImageDraw.Draw(img)
    d.line(pts, fill="#42ffd0", width=4, joint="curve")
    d.text((165, 660), "CH1  1.00V/div    TIME  1.00ms/div    AUTO", font=body, fill="#9ed7cd")
    for i, label in enumerate(["VOLTS", "TIME", "TRIG", "CURSOR"]):
        cx = 990 + (i % 2) * 95
        cy = 240 + (i // 2) * 160
        d.ellipse((cx - 45, cy - 45, cx + 45, cy + 45), fill="#44515a", outline="#8aa0a8", width=3)
        d.ellipse((cx - 16, cy - 16, cx + 16, cy + 16), fill="#252d33")
        d.line((cx, cy, cx + 25, cy - 25), fill="#c3d2d7", width=4)
        d.text((cx, cy + 65), label, font=tiny, fill="#c6d4d9", anchor="mm")
    d.rounded_rectangle((960, 560, 1155, 625), radius=12, fill="#1e272e", outline="#596a72")
    d.text((1058, 592), "f ≈ 280 Hz", font=body, fill="#42ffd0", anchor="mm")
    img.convert("RGB").save(path)


def make_adapter(path: Path) -> None:
    img = Image.new("RGBA", (1280, 820), "#e8eceb")
    img = add_paper_noise(img.convert("RGB"), 5).convert("RGBA")
    d = ImageDraw.Draw(img)
    title = safe_font(42, True)
    body = safe_font(24)
    mono = safe_font(22)
    small = safe_font(16)
    d.text((72, 54), "Power Adapter Label Sample", font=title, fill="#16323f")
    adapter = (235, 160, 995, 590)
    soft_shadow(img, adapter, radius=38, offset=(22, 26), alpha=95)
    d.rounded_rectangle(adapter, radius=38, fill="#f9f9f4", outline="#8b9695", width=4)
    d.rectangle((302, 224, 928, 496), fill="#ffffff", outline="#222e34", width=3)
    d.rounded_rectangle((1000, 278, 1130, 350), radius=12, fill="#cdd4d6", outline="#7f8a8f", width=3)
    d.rectangle((1088, 292, 1220, 310), fill="#c5b07a", outline="#88723a")
    d.rectangle((1088, 320, 1220, 338), fill="#c5b07a", outline="#88723a")
    draw_cable(d, [(235, 405), (150, 455), (70, 560)], "#272f35", 20)
    lines = [
        ("AC/DC POWER ADAPTER", 30, True),
        ("MODEL: EL-USB-0502", 28, False),
        ("INPUT: 100-240V~ 50/60Hz 0.5A", 28, False),
        ("OUTPUT: 5V 2A", 28, True),
        ("POWER: 10W MAX     POLARITY: +", 28, False),
        ("EFFICIENCY LEVEL VI", 28, False),
    ]
    y = 244
    for line, step, bold in lines:
        d.text((335, y), line, font=body if bold else mono, fill="#11191d")
        y += step + 10
    d.rounded_rectangle((322, 512, 908, 558), radius=12, fill="#eef6f2", outline="#c7d9d0")
    d.text((340, 535), "P = V x I = 5V x 2A = 10W", font=body, fill="#1d5e48", anchor="lm")
    d.rounded_rectangle((118, 650, 1160, 725), radius=18, fill="#ffffffcc", outline="#c5d1d6")
    d.text((150, 674), "The app explains input range, output rating, power, and polarity without manual typing.", font=body, fill="#526770")
    d.text((150, 706), "Drag a rectangle around the OUTPUT line to inspect only that label area.", font=small, fill="#526770")
    img.convert("RGB").save(path)
