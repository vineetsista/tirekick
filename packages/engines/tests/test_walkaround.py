"""Frames and their timestamps, kept in lockstep through the degraded path.

load_frames explicitly tolerates a committed selection whose image files have
gone missing - it skips the frame rather than cite an asset that does not
resolve. The test here pins the part that is easy to get wrong: the timestamp
list must be filtered by the same rule as the frame list, or every surviving
frame after a gap scrubs the buyer to some other frame's moment.
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from tirekick_engines.cogs import CostMeter
from tirekick_engines.engines import walkaround
from tirekick_engines.models import Asset


def _video_asset() -> Asset:
    return Asset(
        id="video_01",
        kind="video",
        path="video_01.mp4",
        sha256="0" * 64,
        bytes=1,
        duration_sec=10.0,
    )


def _payload() -> dict[str, object]:
    return {
        "asset_id": "video_01",
        "duration_sec": 10.0,
        "sampled": 20,
        "dropped_blurred": 1,
        "dropped_duplicate": 0,
        "dropped_over_cap": 0,
        "statement": "3 frame(s) were taken from 10 seconds of video.",
        "frames": [
            {"id": "video_01_f01", "file": "video_01.frame_01.jpg", "at_sec": 0.5},
            {"id": "video_01_f02", "file": "video_01.frame_02.jpg", "at_sec": 3.0},
            {"id": "video_01_f03", "file": "video_01.frame_03.jpg", "at_sec": 7.5},
        ],
    }


def _write_setup(tmp_path: Path, *, present: list[str]) -> tuple[Path, Path]:
    media_root = tmp_path / "media"
    cache_dir = tmp_path / "cached"
    media_root.mkdir()
    cache_dir.mkdir()
    for name in present:
        Image.new("RGB", (32, 24), (40, 40, 40)).save(media_root / name, format="JPEG")
    cache_path = walkaround.cache_path(cache_dir, "video_01")
    cache_path.write_text(json.dumps(_payload()), encoding="utf-8")
    return media_root, cache_dir


def test_a_complete_selection_pairs_every_frame_with_its_time(tmp_path: Path) -> None:
    media_root, cache_dir = _write_setup(
        tmp_path,
        present=["video_01.frame_01.jpg", "video_01.frame_02.jpg", "video_01.frame_03.jpg"],
    )
    frames, track = walkaround.load_frames(
        [_video_asset()], media_root, cache_dir, CostMeter(mode="fixture")
    )
    assert track is not None
    assert [f.id for f in frames] == ["video_01_f01", "video_01_f02", "video_01_f03"]
    assert track.frame_times_sec == [0.5, 3.0, 7.5]


def test_a_missing_frame_takes_its_timestamp_with_it(tmp_path: Path) -> None:
    """The report says which frame and at what timestamp, so a buyer can scrub
    to it (module docstring). With the first image gone, the survivors must
    keep their own timestamps - not inherit their predecessors'."""
    media_root, cache_dir = _write_setup(
        tmp_path,
        present=["video_01.frame_02.jpg", "video_01.frame_03.jpg"],
    )
    frames, track = walkaround.load_frames(
        [_video_asset()], media_root, cache_dir, CostMeter(mode="fixture")
    )
    assert track is not None
    assert track.frame_asset_ids == ["video_01_f02", "video_01_f03"]
    assert track.frame_times_sec == [3.0, 7.5]
    assert len(frames) == 2
