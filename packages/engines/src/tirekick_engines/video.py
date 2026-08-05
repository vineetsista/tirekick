"""Walkaround video: choosing which frames are worth looking at.

A walkaround is the highest-value input this product can take. A seller's listing
photographs show the side of the car they want shown; a buyer walking round it
with a phone sweeps every panel, including the one nobody photographed. That is
exactly the coverage gap the report keeps having to report.

It is also the input most likely to waste money. A 45-second walkaround at 30fps
is 1,350 frames. Sending all of them costs about $30 in image tokens, most of it
spent on motion blur and on the same rear quarter panel from four angles.

So this module is a selection problem, and it is the whole of the engineering
here. Three passes, cheapest first:

1. **Sample** on a fixed grid, so coverage is even rather than clustered wherever
   the walker moved slowly.
2. **Score sharpness** and keep the best frame in each time bucket. A phone
   walking round a car produces motion blur constantly, and a blurred frame is
   worse than no frame - it is the input most likely to turn a shadow into a dent.
3. **Deduplicate perceptually**, because someone who pauses at the front bumper
   yields eight near-identical frames, and paying four times to be told about the
   same scratch is not thoroughness.

What comes out is a handful of stills that then go through exactly the same vision
path as uploaded photographs - same classifier, same passes, same clamp. A frame
is an asset, and the report cites it the way it cites any other image, so a
finding from a video is a finding with a picture behind it (LAW 1).

Nothing here calls a model. Selection is arithmetic on pixels, which means it is
testable, free, and cannot hallucinate a frame that is not in the file.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

#: Frames pulled per second of source before scoring. Two is enough to catch a
#: sharp moment inside any half-second of walking, and cheap - decoding is local.
SAMPLE_FPS = 2.0

#: Frames are bucketed into windows this wide and the sharpest in each survives.
#: About the time it takes to walk past one panel.
BUCKET_SECONDS = 1.5

#: Long edge of an extracted frame. Matches the vision path's limit so the frame
#: is never resampled twice.
FRAME_LONG_EDGE = 1568


def scale_filter(long_edge: int = FRAME_LONG_EDGE) -> str:
    """The ffmpeg scale filter that actually caps the long edge.

    It read `scale='min(N,iw)':-2` - a ceiling on width and nothing at all on
    height. Landscape footage obeyed it and portrait footage, which is how a
    phone held normally records a walkaround, came out at full height: larger
    files, a second resample in the vision path, and a frame that is not the
    size this constant says it is.

    `force_original_aspect_ratio=decrease` makes the pair a box to fit inside
    rather than a size to stretch to, and `force_divisible_by=2` keeps both
    axes even, which the encoder requires.
    """
    return (
        f"scale='min(iw,{long_edge})':'min(ih,{long_edge})'"
        f":force_original_aspect_ratio=decrease:force_divisible_by=2"
    )


#: Hamming distance between 64-bit perceptual hashes at or below which two frames
#: are treated as the same view.
#:
#: 5 of 64 bits, which is the conventional near-duplicate threshold for an average
#: hash. The first version of this used 8, chosen for no reason, and on the
#: fixture that merged frames two seconds and half a car apart - genuinely
#: different views scored 7, while the frames from the deliberate camera pause
#: scored 0. A threshold that cannot separate those is not doing the job.
#:
#: **This value is unvalidated on real footage.** A synthetic panning strip has
#: far less texture than a car in daylight, so the distances it produces are
#: compressed, and tuning against it would be overfitting to a drawing. It needs
#: a real walkaround before it can be called correct - see the P7 gaps.
DUPLICATE_HASH_DISTANCE = 5

#: Hard ceiling on frames handed to the vision engine, whatever the video length.
#: A 3-minute walkaround must not quietly cost six times a 30-second one - LAW 5
#: is easiest to break by accident here.
MAX_FRAMES = 12

#: Below this sharpness score relative to the video's own best frame, a frame is
#: motion blur. Relative rather than absolute because a dusk video is dimmer and
#: softer everywhere, and an absolute floor would reject all of it.
MIN_RELATIVE_SHARPNESS = 0.25


class VideoUnavailable(RuntimeError):
    """The video could not be read."""


@dataclass(frozen=True)
class FrameCandidate:
    index: int
    at_sec: float
    sharpness: float
    phash: int


@dataclass(frozen=True)
class Selection:
    """What was chosen, and - just as importantly - what was thrown away."""

    kept: tuple[FrameCandidate, ...]
    duration_sec: float
    sampled: int
    dropped_blurred: int
    dropped_duplicate: int
    dropped_over_cap: int

    @property
    def statement(self) -> str:
        """Buyer-facing account of the selection. Coverage honesty, LAW 1."""
        parts = [
            f"{len(self.kept)} frame(s) were taken from {self.duration_sec:.0f} "
            f"seconds of video and analysed as photographs."
        ]
        if self.dropped_blurred:
            parts.append(
                f"{self.dropped_blurred} were too blurred to read - a blurred frame "
                f"is worse than no frame, because it is the input most likely to "
                f"turn a shadow into a dent."
            )
        if self.dropped_duplicate:
            parts.append(
                f"{self.dropped_duplicate} showed the same view as a frame already " f"chosen."
            )
        if self.dropped_over_cap:
            parts.append(
                f"{self.dropped_over_cap} further usable frame(s) were not analysed "
                f"because this report caps video at {MAX_FRAMES} frames to keep its "
                f"cost bounded. Nothing in them was examined."
            )
        return " ".join(parts)


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def probe_duration(path: Path) -> float:
    if not ffmpeg_available():
        raise VideoUnavailable("ffmpeg/ffprobe are not installed.")
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise VideoUnavailable(f"ffprobe could not read {path.name}")
    try:
        return float(json.loads(result.stdout)["format"]["duration"])
    except (KeyError, ValueError) as exc:
        raise VideoUnavailable(f"{path.name} reports no duration") from exc


def extract_frames(path: Path, out_dir: Path, *, fps: float = SAMPLE_FPS) -> list[Path]:
    """Decode the video to stills on a fixed grid."""
    if not ffmpeg_available():
        raise VideoUnavailable("ffmpeg is not installed.")
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("raw_*.jpg"):
        stale.unlink()

    result = subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-loglevel",
            "error",
            "-i",
            str(path),
            "-vf",
            f"fps={fps},{scale_filter()}",
            "-q:v",
            "3",
            str(out_dir / "raw_%04d.jpg"),
        ],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise VideoUnavailable(
            f"ffmpeg could not extract frames from {path.name}: "
            f"{result.stderr.decode('utf-8', 'replace').strip()[:200]}"
        )
    return sorted(out_dir.glob("raw_*.jpg"))


def sharpness(image_path: Path) -> float:
    """Variance of the Laplacian - the standard blur measure.

    A sharp edge has a large second derivative; motion blur smears it away. The
    number is meaningless in isolation and meaningful compared against other
    frames of the same video, which is how it is used.
    """
    from PIL import Image

    with Image.open(image_path) as image:
        grey = np.asarray(image.convert("L"), dtype=np.float32)

    # 4-neighbour Laplacian, computed directly rather than via a convolution
    # dependency. Interior pixels only, so the border does not inflate it.
    laplacian = (
        grey[:-2, 1:-1]
        + grey[2:, 1:-1]
        + grey[1:-1, :-2]
        + grey[1:-1, 2:]
        - 4.0 * grey[1:-1, 1:-1]
    )
    return float(laplacian.var())


def perceptual_hash(image_path: Path, *, size: int = 8) -> int:
    """64-bit average hash: is this the same view as that one?

    Downscale hard, compare each pixel to the mean, pack the bits. Crude by
    modern standards and exactly right here - it is insensitive to the small
    exposure and framing changes between consecutive walking frames, which is the
    thing being detected.
    """
    from PIL import Image

    with Image.open(image_path) as image:
        small = image.convert("L").resize((size, size), Image.Resampling.BILINEAR)

    pixels = np.asarray(small, dtype=np.float32)
    bits = (pixels > pixels.mean()).flatten()
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return value


def hamming(a: int, b: int) -> int:
    return int((a ^ b).bit_count())


def select_frames(
    frames: list[Path],
    *,
    duration_sec: float,
    fps: float = SAMPLE_FPS,
    max_frames: int = MAX_FRAMES,
) -> Selection:
    """Sharpest frame per time bucket, deduplicated, capped."""
    if not frames:
        return Selection((), duration_sec, 0, 0, 0, 0)

    candidates = [
        FrameCandidate(
            index=i,
            at_sec=round(i / fps, 2),
            sharpness=sharpness(path),
            phash=perceptual_hash(path),
        )
        for i, path in enumerate(frames)
    ]

    best_sharpness = max(c.sharpness for c in candidates) or 1.0
    floor = best_sharpness * MIN_RELATIVE_SHARPNESS
    sharp = [c for c in candidates if c.sharpness >= floor]
    dropped_blurred = len(candidates) - len(sharp)

    # One winner per time bucket, so the selection covers the walk rather than
    # clustering wherever the phone happened to be steadiest.
    buckets: dict[int, FrameCandidate] = {}
    for candidate in sharp:
        key = int(candidate.at_sec // BUCKET_SECONDS)
        current = buckets.get(key)
        if current is None or candidate.sharpness > current.sharpness:
            buckets[key] = candidate
    per_bucket = sorted(buckets.values(), key=lambda c: c.at_sec)

    kept: list[FrameCandidate] = []
    dropped_duplicate = 0
    for candidate in per_bucket:
        if any(hamming(candidate.phash, k.phash) <= DUPLICATE_HASH_DISTANCE for k in kept):
            dropped_duplicate += 1
            continue
        kept.append(candidate)

    dropped_over_cap = max(0, len(kept) - max_frames)
    if dropped_over_cap:
        # Keep an even spread across the walk rather than the first N, which
        # would be the front of the car and nothing else.
        step = len(kept) / max_frames
        kept = [kept[int(i * step)] for i in range(max_frames)]

    return Selection(
        kept=tuple(kept),
        duration_sec=duration_sec,
        sampled=len(candidates),
        dropped_blurred=dropped_blurred,
        dropped_duplicate=dropped_duplicate,
        dropped_over_cap=dropped_over_cap,
    )
