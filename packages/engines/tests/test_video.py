"""Frame selection, against a video whose bad segments we placed ourselves.

`scripts/make_fixture_media.py` declares BLURRED_WINDOW and PAUSED_WINDOW, so the
frames that should be rejected as motion blur and the frames that should be
rejected as duplicates are both known by construction rather than by inspection.

The measure that matters here is not "does it pick good frames" - that needs real
footage. It is "does it reject the two things it exists to reject", and that is
answerable now.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tirekick_engines import video

REPO_ROOT = Path(__file__).resolve().parents[3]
CLIP = REPO_ROOT / "fixtures" / "demo-01" / "media" / "video_01.mp4"

#: Mirrors scripts/make_fixture_media.py.
BLURRED_WINDOW = (4.0, 6.0)
PAUSED_WINDOW = (8.0, 10.5)
VIDEO_SECONDS = 14.0

pytestmark = pytest.mark.skipif(
    not video.ffmpeg_available(), reason="ffmpeg/ffprobe are not installed"
)


@pytest.fixture(scope="module")
def frames(tmp_path_factory) -> list[Path]:  # type: ignore[no-untyped-def]
    work = tmp_path_factory.mktemp("frames")
    extracted = video.extract_frames(CLIP, work)
    yield extracted
    shutil.rmtree(work, ignore_errors=True)


@pytest.fixture(scope="module")
def selection(frames: list[Path]) -> video.Selection:
    return video.select_frames(frames, duration_sec=VIDEO_SECONDS)


def test_the_clip_is_the_length_it_claims() -> None:
    assert abs(video.probe_duration(CLIP) - VIDEO_SECONDS) < 0.5


def test_extraction_samples_on_a_fixed_grid(frames: list[Path]) -> None:
    """Even coverage, rather than clustering wherever the walker slowed down."""
    assert len(frames) == pytest.approx(VIDEO_SECONDS * video.SAMPLE_FPS, abs=2)


def test_blurred_frames_score_far_below_sharp_ones(frames: list[Path]) -> None:
    """The measure has to actually separate them, not merely differ."""
    scores = [(i / video.SAMPLE_FPS, video.sharpness(f)) for i, f in enumerate(frames)]
    blurred = [s for t, s in scores if BLURRED_WINDOW[0] <= t < BLURRED_WINDOW[1]]
    sharp = [s for t, s in scores if not BLURRED_WINDOW[0] <= t < BLURRED_WINDOW[1]]

    assert blurred and sharp
    assert max(blurred) < min(sharp), "blur and focus overlap - the measure is useless"


def test_every_deliberately_blurred_frame_is_rejected(selection: video.Selection) -> None:
    """A blurred frame is worse than no frame: it is the input most likely to
    turn a shadow into a dent."""
    for candidate in selection.kept:
        assert not (
            BLURRED_WINDOW[0] <= candidate.at_sec < BLURRED_WINDOW[1]
        ), f"kept a frame at {candidate.at_sec}s, inside the blurred window"
    assert selection.dropped_blurred >= 3


def test_the_camera_pause_yields_at_most_one_frame(selection: video.Selection) -> None:
    """Someone stops at the front bumper for two seconds. Paying four times to
    be told about the same scratch is not thoroughness."""
    during_pause = [
        c for c in selection.kept if PAUSED_WINDOW[0] <= c.at_sec < PAUSED_WINDOW[1]
    ]
    assert len(during_pause) <= 1
    assert selection.dropped_duplicate >= 2


def test_identical_frames_hash_identically(frames: list[Path]) -> None:
    assert video.perceptual_hash(frames[0]) == video.perceptual_hash(frames[0])
    assert video.hamming(0b1011, 0b1001) == 1


def test_the_dedupe_threshold_separates_pause_from_progress(frames: list[Path]) -> None:
    """The bug this pins.

    The first threshold was 8, chosen for no reason, and it merged frames two
    seconds and half a car apart. Frames from the deliberate pause hash within a
    bit or two of each other; frames from genuinely different parts of the sweep
    do not, and the threshold has to sit between those.
    """
    at = lambda t: frames[int(t * video.SAMPLE_FPS)]  # noqa: E731

    within_pause = video.hamming(
        video.perceptual_hash(at(PAUSED_WINDOW[0] + 0.5)),
        video.perceptual_hash(at(PAUSED_WINDOW[0] + 1.5)),
    )
    across_sweep = video.hamming(video.perceptual_hash(at(0.5)), video.perceptual_hash(at(2.5)))

    assert within_pause <= video.DUPLICATE_HASH_DISTANCE
    assert (
        across_sweep > video.DUPLICATE_HASH_DISTANCE
    ), "distinct views are being merged - the threshold is too permissive"


def test_selection_keeps_a_spread_across_the_walk(selection: video.Selection) -> None:
    """Coverage is the whole point. Frames bunched at the start are the front of
    the car and nothing else."""
    assert len(selection.kept) >= 3
    times = [c.at_sec for c in selection.kept]
    assert max(times) - min(times) > VIDEO_SECONDS / 2


def test_the_frame_cap_is_enforced_and_reported(frames: list[Path]) -> None:
    """LAW 5 is easiest to break by accident here: a 3-minute walkaround must not
    quietly cost six times a 30-second one."""
    capped = video.select_frames(frames, duration_sec=VIDEO_SECONDS, max_frames=2)
    assert len(capped.kept) == 2
    assert capped.dropped_over_cap > 0
    assert "not analysed" in capped.statement


def test_the_statement_reports_what_was_thrown_away(selection: video.Selection) -> None:
    """A report saying '5 frames analysed' without saying 23 were discarded
    invites the reader to assume the whole video was examined."""
    statement = selection.statement
    assert f"{len(selection.kept)} frame(s)" in statement
    if selection.dropped_blurred:
        assert "too blurred" in statement
    if selection.dropped_duplicate:
        assert "same view" in statement


def test_an_empty_frame_list_is_not_a_crash() -> None:
    empty = video.select_frames([], duration_sec=0.0)
    assert empty.kept == ()
    assert "0 frame(s)" in empty.statement


def test_an_unreadable_file_raises_rather_than_returning_nothing(tmp_path: Path) -> None:
    """Silence would be indistinguishable from a video with no usable frames."""
    broken = tmp_path / "broken.mp4"
    broken.write_bytes(b"not a video")
    with pytest.raises(video.VideoUnavailable):
        video.probe_duration(broken)
