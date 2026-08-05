"""The frame scale filter, checkable without ffmpeg installed.

test_video.py proves the behaviour on real video but is skipped wherever
ffmpeg is absent. The bug this pins - `scale=min(N,iw):-2`, a cap on width
only, so portrait phone footage came out at full height - is visible in the
filter string itself, and the string can be held to account everywhere.
"""

from __future__ import annotations

from tirekick_engines import video


def test_the_filter_caps_both_axes_of_the_frame() -> None:
    filt = video.scale_filter(1568)
    assert "min(iw,1568)" in filt
    assert "min(ih,1568)" in filt, "height unconstrained - portrait frames exceed the long edge"
    # The box is a ceiling, not a target: aspect is preserved by shrinking.
    assert "force_original_aspect_ratio=decrease" in filt


def test_the_filter_keeps_dimensions_even_for_the_encoder() -> None:
    assert "force_divisible_by=2" in video.scale_filter()


def test_the_default_is_the_documented_long_edge() -> None:
    assert f"min(iw,{video.FRAME_LONG_EDGE})" in video.scale_filter()
