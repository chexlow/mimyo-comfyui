"""Regenerates placeholder images for the _example/ directory.

Run:
    python3 datasets/faces/synth_aria/v1/_example/_generate_placeholders.py

Each placeholder is a flat-color PNG at the actual bucket size with a label
that says which file slot it represents. They are intentionally synthetic and
small (PNG-optimized flat color compresses to a few KB).
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

BASE = Path(__file__).resolve().parent

SAMPLES = [
    # (relative path, bucket_size, label, fill_color)
    ("raw/0001_session-a.png",                  1536, "RAW 0001 session-a (frontal)",        (235, 220, 210)),
    ("raw/0002_session-a.png",                  1536, "RAW 0002 session-a (cafe 3/4)",       (220, 215, 200)),
    ("curated/1280/0001_frontal-portrait.png",  1280, "1280 / 0001 frontal-portrait",        (240, 230, 220)),
    ("curated/1280/0002_cafe-threequarter.png", 1280, "1280 / 0002 cafe-threequarter",       (228, 215, 196)),
    ("curated/1024/0003_park-fullbody.png",     1024, "1024 / 0003 park-fullbody",           (210, 220, 215)),
    ("curated/1280/0004_bookstore-laugh.png",   1280, "1280 / 0004 bookstore-laugh",         (200, 185, 170)),
    ("curated/1536/0005_studio-neutral.png",    1536, "1536 / 0005 studio-neutral",          (215, 215, 215)),
    ("curated/1280/0006_kitchen-cooking.png",   1280, "1280 / 0006 kitchen-cooking",         (220, 230, 215)),
]


def load_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for c in candidates:
        try:
            return ImageFont.truetype(c, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main() -> None:
    big = load_font(48)
    small = load_font(32)
    for rel, bucket, label, color in SAMPLES:
        path = BASE / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        img = Image.new("RGB", (bucket, bucket), color)
        d = ImageDraw.Draw(img)
        d.text((48, 48),  "PLACEHOLDER  synth_aria v1", fill=(60, 60, 60), font=big)
        d.text((48, 120), label,                         fill=(60, 60, 60), font=big)
        d.text((48, bucket - 80), f"{bucket} x {bucket}", fill=(60, 60, 60), font=small)
        img.save(path, optimize=True)
        print(f"wrote {rel}  ({bucket}x{bucket})")


if __name__ == "__main__":
    main()
