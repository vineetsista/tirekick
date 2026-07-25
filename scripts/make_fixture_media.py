#!/usr/bin/env python3
"""Generate the synthetic fixture media for fixtures/demo-01.

These are drawings, not photographs. Every one carries a diagonal
"SYNTHETIC FIXTURE - NOT A PHOTOGRAPH" watermark so that a frame lifted out of the
repo and pasted somewhere else still says what it is. See DECISIONS.md D-010 and
fixtures/PROVENANCE.md.

Regions the cached fixture findings point at are drawn here at known coordinates,
so the overlay renderer has something real to box - the boxes in the fixture
responses match the shapes in these files, and the golden test hashes the bytes.

Run: packages/engines/.venv/bin/python scripts/make_fixture_media.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / "fixtures" / "demo-01" / "media"

W, H = 1600, 1200

BG = (16, 20, 24)
GRID = (30, 37, 44)
INK = (230, 237, 243)
MUTED = (139, 152, 165)
MARK = (56, 225, 176)

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
]


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def base_canvas(title: str, subtitle: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    for x in range(0, W, 40):
        d.line([(x, 0), (x, H)], fill=GRID, width=1)
    for y in range(0, H, 40):
        d.line([(0, y), (W, y)], fill=GRID, width=1)

    d.rectangle([40, 40, W - 40, H - 40], outline=(45, 55, 65), width=2)
    d.text((70, 70), title, font=load_font(56), fill=INK)
    d.text((70, 140), subtitle, font=load_font(28), fill=MUTED)
    return img, d


def watermark(img: Image.Image) -> None:
    """Diagonal, unmissable, and burned into the pixels."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    font = load_font(64)
    text = "SYNTHETIC FIXTURE - NOT A PHOTOGRAPH"
    for i in range(-2, 4):
        d.text((80, 300 + i * 260), text, font=font, fill=(255, 255, 255, 34))
    rotated = layer.rotate(18, resample=Image.BICUBIC)
    img.paste(Image.alpha_composite(img.convert("RGBA"), rotated).convert("RGB"), (0, 0))


def region(
    img: Image.Image,
    d: ImageDraw.ImageDraw,
    box: tuple[float, float, float, float],
    label: str,
    color: tuple[int, int, int],
) -> None:
    """Draw the shape a fixture finding points at. box is normalized x,y,w,h."""
    x, y, w, h = box
    x0, y0, x1, y1 = (int(v) for v in (x * W, y * H, (x + w) * W, (y + h) * H))

    # Hatch on its own tile, then paste - so the texture stops at the box edge
    # rather than running off across the panel.
    tile = Image.new("RGB", (x1 - x0, y1 - y0), BG)
    td = ImageDraw.Draw(tile)
    step = 14
    for offset in range(0, (x1 - x0) + (y1 - y0), step):
        td.line([(offset, 0), (0, offset)], fill=color, width=1)
    img.paste(tile, (x0, y0))

    d.rectangle((x0, y0, x1, y1), outline=color, width=4)
    d.text((x0 + 8, y1 + 10), label, font=load_font(26), fill=color)


def panel(
    name: str,
    title: str,
    subtitle: str,
    regions: list[tuple[tuple[float, float, float, float], str, tuple[int, int, int]]],
) -> None:
    img, d = base_canvas(title, subtitle)
    for box, label, color in regions:
        region(img, d, box, label, color)
    watermark(img)
    out = MEDIA / name
    img.save(out, "JPEG", quality=88)
    print(f"  wrote {out.relative_to(ROOT)}")


def make_audio() -> None:
    """A synthesized tone, not an engine.

    ffmpeg is a hard dependency of the video/audio pipeline anyway, so generating
    the clip here keeps the fixture reproducible from source rather than shipping
    an opaque binary blob nobody can regenerate.
    """
    out = MEDIA / "audio_01.wav"
    cmd = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=42:duration=22",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=126:duration=22",
        "-filter_complex",
        "[0:a][1:a]amix=inputs=2:duration=longest,volume=0.4",
        "-ar",
        "22050",
        "-ac",
        "1",
        str(out),
    ]
    subprocess.run(cmd, check=True)
    print(f"  wrote {out.relative_to(ROOT)}")


def main() -> int:
    MEDIA.mkdir(parents=True, exist_ok=True)

    rust = (224, 122, 40)
    dent = (232, 179, 65)
    lamp = (248, 81, 73)
    fluid = (163, 113, 247)
    neutral = MARK

    panel(
        "photo_01.jpg",
        "EXTERIOR / DRIVER SIDE",
        "synthetic panel diagram - the marked region is where the fixture finding points",
        [((0.08, 0.62, 0.34, 0.14), "region A: corrosion", rust)],
    )
    panel(
        "photo_02.jpg",
        "EXTERIOR / FRONT",
        "synthetic panel diagram - no marked regions",
        [],
    )
    panel(
        "photo_03.jpg",
        "EXTERIOR / REAR",
        "synthetic panel diagram - the marked region is where the fixture finding points",
        [((0.55, 0.40, 0.20, 0.18), "region B: deformation", dent)],
    )
    panel(
        "photo_04.jpg",
        "INTERIOR / FRONT",
        "synthetic cabin diagram - the marked region is where the fixture finding points",
        [((0.20, 0.45, 0.24, 0.22), "region C: seat wear", neutral)],
    )
    panel(
        "photo_05.jpg",
        "INSTRUMENT CLUSTER",
        "synthetic cluster diagram - the marked region is where the fixture finding points",
        [((0.62, 0.30, 0.10, 0.12), "region D: lamp lit", lamp)],
    )
    panel(
        "photo_06.jpg",
        "ODOMETER",
        "synthetic cluster diagram - the marked region is where the fixture finding points",
        [((0.34, 0.44, 0.30, 0.12), "region E: 128,540 mi", neutral)],
    )
    panel(
        "photo_07.jpg",
        "TIRE / FRONT LEFT",
        "synthetic tire diagram - the marked region is where the fixture finding points",
        [((0.30, 0.30, 0.36, 0.36), "region F: tread block", neutral)],
    )
    panel(
        "photo_08.jpg",
        "ENGINE BAY",
        "synthetic bay diagram - two marked regions; one is deliberately near a locked system",
        [
            ((0.16, 0.28, 0.22, 0.16), "region G: residue", neutral),
            ((0.60, 0.58, 0.24, 0.20), "region H: wet area near hub", fluid),
        ],
    )

    make_audio()
    print("\n  All fixture media is synthetic and watermarked. See fixtures/PROVENANCE.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
