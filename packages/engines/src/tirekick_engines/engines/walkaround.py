"""Walkaround video, as an input to the vision engine.

The selection arithmetic lives in `video.py`. This is the part that turns chosen
frames into assets, so they flow through exactly the same path as an uploaded
photograph: classified into a view, sent only at the passes that view supports,
clamped by the safety law, and cited on the image they came from.

That sameness is the design. A frame is not a special kind of evidence with its
own rules - it is a photograph that happens to have arrived inside a video, and a
finding from one has a picture behind it like any other (LAW 1). The report says
which frame and at what timestamp, so a buyer can scrub to it.

The reason this matters more than it looks: a walkaround is the only input that
can fill a coverage gap. A seller photographs the side of the car they want shown,
and every report so far has had to say "the media provided did not include:
exterior side right". Someone walking round the car with a phone covers all of it.
So the frames are classified and counted toward coverage like any other view, and
a video can move a report from `cannot_determine` to an actual answer.

Like the audio features, the selection is cached and the chosen frames are
committed, because fixture mode must need nothing (D-026).
"""

from __future__ import annotations

import json
from pathlib import Path

from .. import video as video_module
from ..cogs import CostMeter
from ..models import Asset, WalkaroundTrack

#: Committed frames are named from the video asset they came from, so the
#: provenance of every image in the report is readable from its filename alone.
FRAME_STEM = "{asset_id}.frame_{index:02d}"


def has_video(assets: list[Asset]) -> bool:
    return any(a.kind == "video" for a in assets)


def cache_path(cache_dir: Path, asset_id: str) -> Path:
    return cache_dir / f"video.frames.{asset_id}.json"


def frame_name(asset_id: str, index: int) -> str:
    return FRAME_STEM.format(asset_id=asset_id, index=index) + ".jpg"


def load_frames(
    assets: list[Asset],
    media_root: Path,
    cache_dir: Path,
    meter: CostMeter,
) -> tuple[list[Asset], WalkaroundTrack | None]:
    """Derived photo assets from the walkaround, and the account of the selection.

    Returns an empty list rather than raising when there is no cached selection.
    A video we could not read produces no frames and no findings - inventing
    either would be worse than the gap, and the gap is reported in coverage.
    """
    clip = next((a for a in assets if a.kind == "video"), None)
    if clip is None:
        return [], None

    path = cache_path(cache_dir, clip.id)
    if not path.is_file():
        return [], None

    payload = json.loads(path.read_text(encoding="utf-8"))
    frames: list[Asset] = []

    for entry in payload.get("frames", []):
        name = entry["file"]
        frame_path = media_root / name
        if not frame_path.is_file():
            # Committed selection, missing image. Skip it rather than cite an
            # asset that does not resolve - Report._referential_integrity would
            # reject the report anyway, and loudly is better than late.
            continue
        from ..inputs import sha256_of

        frames.append(
            Asset(
                id=entry["id"],
                kind="photo",
                path=name,
                sha256=sha256_of(frame_path),
                bytes=frame_path.stat().st_size,
                view_class=None,
                view_confidence=None,
                duration_sec=None,
                synthetic=clip.synthetic,
            )
        )

    meter.record_video_seconds(float(payload.get("duration_sec") or 0.0))

    track = WalkaroundTrack(
        asset_id=clip.id,
        duration_sec=float(payload.get("duration_sec") or 0.0),
        frames_sampled=int(payload.get("sampled") or 0),
        frames_analysed=len(frames),
        dropped_blurred=int(payload.get("dropped_blurred") or 0),
        dropped_duplicate=int(payload.get("dropped_duplicate") or 0),
        dropped_over_cap=int(payload.get("dropped_over_cap") or 0),
        frame_asset_ids=[f.id for f in frames],
        frame_times_sec=[float(e["at_sec"]) for e in payload.get("frames", [])][: len(frames)],
        statement=payload.get("statement", ""),
    )
    return frames, track


def build_selection_payload(
    clip_id: str, selection: video_module.Selection, frame_files: list[str]
) -> dict[str, object]:
    """What the refresh script writes. Kept here so the shape has one owner."""
    return {
        "_note": (
            "Frame selection computed by scripts/refresh_video_cache.py. "
            "Deterministic arithmetic over the video - sharpness and perceptual "
            "hashing, no model, no claims."
        ),
        "asset_id": clip_id,
        "duration_sec": selection.duration_sec,
        "sampled": selection.sampled,
        "dropped_blurred": selection.dropped_blurred,
        "dropped_duplicate": selection.dropped_duplicate,
        "dropped_over_cap": selection.dropped_over_cap,
        "statement": selection.statement,
        "frames": [
            {
                "id": f"{clip_id}_f{index:02d}",
                "file": name,
                "at_sec": candidate.at_sec,
                "sharpness": round(candidate.sharpness, 2),
            }
            for index, (candidate, name) in enumerate(
                zip(selection.kept, frame_files, strict=True), start=1
            )
        ],
    }
