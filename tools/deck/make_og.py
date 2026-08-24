#!/usr/bin/env python3
"""Generate the 1200x630 OpenGraph card for verdict-bench.pages.dev."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent.parent / "ui" / "public" / "og.png"
W, H = 1200, 630
img = Image.new("RGB", (W, H), (8, 9, 12))
d = ImageDraw.Draw(img)


def font(size, bold=True):
    for name in (
        "/usr/share/fonts/truetype/inter/Inter-Bold.ttf" if bold else "/usr/share/fonts/truetype/inter/Inter-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


# checkmark-gavel mark, top left
d.line([(80, 120), (150, 120)], fill=(130, 143, 255), width=10)
d.line([(150, 120), (238, 218)], fill=(130, 143, 255), width=10)
d.line([(118, 165), (166, 165)], fill=(130, 143, 255), width=10)
d.ellipse([(238, 210), (268, 240)], fill=(207, 224, 255))

d.text((80, 290), "verdict-bench", font=font(96), fill=(232, 236, 244))
d.text((84, 420), "AN ACCOUNT-REVIEW DECISIONING-PROMPT STUDY",
       font=font(28, bold=False), fill=(138, 147, 163))
d.text((84, 470), "gated matrix  ·  prompt ladder  ·  adjudication queue  ·  notebook",
       font=font(24, bold=False), fill=(92, 102, 120))
d.rectangle([(0, H - 14), (W, H)], fill=(130, 143, 255))
img.save(OUT)
print(OUT, img.size)
