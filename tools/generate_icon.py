from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def font(size: int) -> ImageFont.ImageFont:
    for p in ["C:/Windows/Fonts/malgunbd.ttf", "C:/Windows/Fonts/arialbd.ttf"]:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()


def main() -> None:
    out = Path("electralens/assets/electralens.ico")
    out.parent.mkdir(parents=True, exist_ok=True)
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = []
    for s in sizes:
        img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((1, 1, s - 2, s - 2), radius=max(3, s // 6), fill="#14242e")
        d.ellipse((s * 0.18, s * 0.18, s * 0.82, s * 0.82), outline="#42ffd0", width=max(1, s // 12))
        d.line((s * 0.66, s * 0.66, s * 0.88, s * 0.88), fill="#42ffd0", width=max(1, s // 11))
        if s >= 48:
            d.text((s // 2, s // 2), "E", font=font(max(18, s // 2)), fill="white", anchor="mm")
        images.append(img)
    images[-1].save(out, sizes=[(s, s) for s in sizes])
    print(out)


if __name__ == "__main__":
    main()
