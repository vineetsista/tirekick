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

import sys
import subprocess
import wave
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
    img.paste(
        Image.alpha_composite(img.convert("RGBA"), rotated).convert("RGB"), (0, 0)
    )


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


#: Impulse times burned into the synthetic clip, in seconds. Ground truth for
#: the onset detector - see tests/test_signal.py.
IMPULSE_TIMES = (5.0, 11.5, 17.25)


def make_audio() -> None:
    """A synthesized signal with engine-like structure. Still not an engine.

    The previous fixture was two mixed sine tones. It was honest about being
    synthetic and it was useless as a test: a pure tone has no transients, so the
    onset detector in signal.py ran against it and found nothing, forever, without
    that ever being distinguishable from the detector being broken.

    This builds something with the shape of engine audio - a low firing
    fundamental, a stack of harmonics, amplitude modulation, and broadband noise -
    and then places three impulses at KNOWN times. Those times are ground truth by
    construction, which is what lets `test_signal.py` assert the detector finds
    them rather than merely running.

    It still does not sound like a car and no accuracy claim will ever cite it.
    See fixtures/PROVENANCE.md and DECISIONS.md D-010.
    """
    import numpy as np

    sample_rate = 22050
    duration = 22.0
    t = np.arange(int(sample_rate * duration), dtype=np.float64) / sample_rate

    # ~31.5Hz fundamental: roughly a 4-cylinder four-stroke at a 945rpm idle.
    fundamental = 31.5
    signal = np.zeros_like(t)
    for harmonic, gain in enumerate((1.0, 0.55, 0.32, 0.2, 0.12, 0.08), start=1):
        signal += gain * np.sin(2 * np.pi * fundamental * harmonic * t)

    # Idle wander, so the tone is not perfectly stationary.
    signal *= 1.0 + 0.06 * np.sin(2 * np.pi * 0.7 * t)

    rng = np.random.default_rng(20260726)
    signal += 0.12 * rng.standard_normal(t.size)

    # Three impulses at known times. IMPULSE_TIMES is the ground truth.
    for at in IMPULSE_TIMES:
        index = int(at * sample_rate)
        length = int(0.012 * sample_rate)
        envelope = np.exp(-np.linspace(0, 9, length))
        tick = envelope * rng.standard_normal(length) * 3.2
        signal[index : index + length] += tick

    signal *= 0.35 / np.max(np.abs(signal))
    pcm = (signal * 32767).astype("<i2")

    out = MEDIA / "audio_01.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())
    print(f"  wrote {out.relative_to(ROOT)}  (impulses at {IMPULSE_TIMES})")


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
    make_video()
    print(
        "\n  All fixture media is synthetic and watermarked. See fixtures/PROVENANCE.md"
    )
    return 0


#: Seconds of the synthetic walkaround that are deliberately motion-blurred, and
#: seconds where the camera deliberately stops. Ground truth for test_video.py.
BLURRED_WINDOW = (4.0, 6.0)
PAUSED_WINDOW = (8.0, 10.5)
VIDEO_SECONDS = 14.0
VIDEO_FPS = 15


def make_video() -> None:
    """A synthetic walkaround. Still not a car.

    Pans a window across a wide painted strip so consecutive frames show
    different regions, exactly as walking round a vehicle does. Two segments are
    deliberate: a blurred stretch, because a phone in motion produces one
    constantly, and a stationary stretch, because people stop to look at things.

    Both windows are declared above, which makes them ground truth - the frame
    selector is measured against them in test_video.py rather than against a
    guess about what it probably did.
    """
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter

    width, height = 640, 400
    strip_width = 2400

    strip = Image.new("RGB", (strip_width, height), (26, 30, 36))
    draw = ImageDraw.Draw(strip)
    rng = np.random.default_rng(4242)
    # Distinct blocks so that panning genuinely changes the view, and so the
    # perceptual hash of one region differs from the next.
    for i in range(24):
        x = i * 100
        shade = 40 + int(rng.integers(0, 120))
        draw.rectangle([x, 120, x + 88, 300], fill=(shade, shade + 12, shade + 20))
        draw.text((x + 8, 320), f"{i:02d}", fill=(210, 210, 210))
    draw.text((20, 20), "SYNTHETIC WALKAROUND - NOT A VEHICLE", fill=(235, 200, 90))

    frames_dir = MEDIA / "_video_build"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for stale in frames_dir.glob("*.png"):
        stale.unlink()

    total = int(VIDEO_SECONDS * VIDEO_FPS)
    travel = strip_width - width
    for n in range(total):
        t = n / VIDEO_FPS
        if t < PAUSED_WINDOW[0]:
            progress = t / PAUSED_WINDOW[0] * 0.6
        elif t < PAUSED_WINDOW[1]:
            progress = 0.6  # stationary: consecutive frames are near-identical
        else:
            span = VIDEO_SECONDS - PAUSED_WINDOW[1]
            progress = 0.6 + (t - PAUSED_WINDOW[1]) / span * 0.4

        left = int(progress * travel)
        frame = strip.crop((left, 0, left + width, height))
        if BLURRED_WINDOW[0] <= t < BLURRED_WINDOW[1]:
            frame = frame.filter(ImageFilter.GaussianBlur(radius=6))
        frame.save(frames_dir / f"f_{n:04d}.png")

    out = MEDIA / "video_01.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-framerate",
            str(VIDEO_FPS),
            "-i",
            str(frames_dir / "f_%04d.png"),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-crf",
            "26",
            str(out),
        ],
        check=True,
    )
    for stale in frames_dir.glob("*.png"):
        stale.unlink()
    frames_dir.rmdir()
    print(
        f"  wrote {out.relative_to(ROOT)}  "
        f"(blurred {BLURRED_WINDOW[0]}-{BLURRED_WINDOW[1]}s, "
        f"paused {PAUSED_WINDOW[0]}-{PAUSED_WINDOW[1]}s)"
    )


if __name__ == "__main__":
    sys.exit(main())
