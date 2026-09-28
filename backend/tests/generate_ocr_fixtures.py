"""Create synthetic OCR fixtures (the handwritten sample uses a script font)."""
from io import BytesIO
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

FIXTURES = Path(__file__).resolve().parent / "fixtures"
TEXT = [
    "SYNTHETIC CLINICAL NOTE",
    "Patient Example 042 reports mild fever and cough.",
    "Temperature 101 F. Pulse 88 bpm. Review the source.",
]


def _font(size: int, handwriting: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (["C:/Windows/Fonts/Inkfree.ttf"] if handwriting else []) + [
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _note(handwriting: bool = False) -> Image.Image:
    image = Image.new("RGB", (1600, 720), (252, 251, 247))
    draw = ImageDraw.Draw(image)
    top = 56
    for index, line in enumerate(TEXT):
        draw.text((78, top), line, font=_font(58 if index == 0 else 48, handwriting), fill=(30, 38, 43))
        top += 158
    return image


def generate() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    typed = _note()
    typed.save(FIXTURES / "typed_note.png")
    _note(handwriting=True).save(FIXTURES / "handwritten_note.png")

    stream = BytesIO()
    typed.save(stream, format="PNG")
    document = pymupdf.open()
    document.new_page(width=800, height=360).insert_image(pymupdf.Rect(0, 0, 800, 360), stream=stream.getvalue())
    document.save(FIXTURES / "scanned_note.pdf")
    document.close()

    tiny = Image.new("RGB", (380, 120), (215, 215, 215))
    ImageDraw.Draw(tiny).text((8, 28), "Patient reports fever and cough", font=_font(16), fill=(128, 128, 128))
    tiny = tiny.filter(ImageFilter.GaussianBlur(radius=2.6)).resize((152, 48), Image.Resampling.BILINEAR)
    tiny = ImageEnhance.Contrast(tiny).enhance(0.55).resize((760, 240), Image.Resampling.BICUBIC)
    tiny.save(FIXTURES / "poor_quality_note.png")


if __name__ == "__main__":
    generate()
