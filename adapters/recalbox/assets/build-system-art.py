#!/usr/bin/env python3
"""Build the static tracker QR and combined system-view artwork.

Build-time dependencies: Pillow and qrcode.
"""
from pathlib import Path

import qrcode
from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
URL = "http://recalbox.local:8080/itemtracker.html"
INK = (20, 20, 22, 255)
PAPER = (239, 235, 222, 255)


def main():
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=7,
        border=3,
    )
    qr.add_data(URL)
    qr.make(fit=True)
    qr_image = qr.make_image(fill_color=INK, back_color=PAPER).convert("RGBA")
    qr_image.save(HERE / "alttpr-tracker-url-qr.png", optimize=True)

    sprites = Image.open(HERE / "alttpr-sprite-montage.png").convert("RGBA")
    bbox = sprites.getbbox()
    sprites = sprites.crop(bbox) if bbox else sprites

    gap = 170
    width = sprites.width + gap + qr_image.width
    height = max(sprites.height, qr_image.height)
    combined = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    combined.alpha_composite(sprites, (0, (height - sprites.height) // 2))
    qr_x = sprites.width + gap
    qr_y = (height - qr_image.height) // 2
    combined.alpha_composite(qr_image, (qr_x, qr_y))

    draw = ImageDraw.Draw(combined)
    try:
        font = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 34)
    except OSError:
        font = ImageFont.load_default()
    label = "AUTOTRACKER"
    label_box = draw.textbbox((0, 0), label, font=font)
    label_width = label_box[2] - label_box[0]
    label_x = qr_x + (qr_image.width - label_width) // 2
    label_y = qr_y - 92
    draw.text((label_x, label_y), label, font=font, fill=PAPER)

    combined.save(HERE / "alttpr-consolegame.png", optimize=True)
    print("QR:", qr_image.size, "Combined:", combined.size)


if __name__ == "__main__":
    main()
