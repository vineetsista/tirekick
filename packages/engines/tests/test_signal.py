"""Signal processing, checked against a waveform whose contents we know exactly.

The fixture clip is synthesised by `scripts/make_fixture_media.py` with three
impulses at times the script itself declares. That makes it ground truth by
construction, which is the only kind of ground truth available before real
recordings exist - and it is enough to prove the detector detects, which the
previous two-sine-tone fixture could not do at all.

These numbers are not accuracy claims and never appear on docs/ACCURACY.md. They
are unit tests of deterministic arithmetic, in the same family as the IoU tests.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

from tirekick_engines import signal

REPO_ROOT = Path(__file__).resolve().parents[3]
CLIP = REPO_ROOT / "fixtures" / "demo-01" / "media" / "audio_01.wav"

#: Mirrors IMPULSE_TIMES in scripts/make_fixture_media.py.
IMPULSE_TIMES = (5.0, 11.5, 17.25)

#: The window is 93ms, so an onset cannot be located more precisely than this.
TIMING_TOLERANCE_SEC = 0.05


def require_ffmpeg() -> None:
    """Skip the decode tests without ffmpeg - except in CI, where that is red.

    This used to be a module-wide skipif, which silently vanished every test in
    the file, including the pure-arithmetic ones that never touch ffmpeg. Now
    only the tests that decode the fixture clip depend on it, the skip names
    itself in the summary, and in CI - which installs ffmpeg explicitly - its
    absence fails, because a gate that quietly passes when it never ran is the
    failure this project keeps finding. gates.sh preflights ffmpeg for the same
    reason, so a local ALL GATES GREEN cannot mean less than CI's.
    """
    if signal.ffmpeg_available():
        return
    if os.environ.get("CI"):
        pytest.fail(
            "ffmpeg is missing in CI. ci.yml installs it explicitly; if this "
            "fires, the install step was removed, and these tests must go red "
            "rather than quietly not run."
        )
    pytest.skip("ffmpeg is not installed - install it to run the decode tests")


@pytest.fixture(scope="module")
def samples() -> np.ndarray:
    require_ffmpeg()
    return signal.decode(CLIP)


@pytest.fixture(scope="module")
def measured(samples: np.ndarray) -> signal.AudioFeatures:
    return signal.features(samples)


def test_decode_returns_mono_float_audio(samples: np.ndarray) -> None:
    assert samples.dtype == np.float32
    assert samples.ndim == 1
    assert abs(samples.size / signal.TARGET_SAMPLE_RATE - 22.0) < 0.1
    assert np.max(np.abs(samples)) <= 1.0


def test_every_known_impulse_is_found(measured: signal.AudioFeatures) -> None:
    """The test the old fixture could not support.

    Two mixed sine tones have no onsets, so the detector ran against them and
    returned nothing, forever, indistinguishably from being broken.
    """
    assert measured.transients, "no transients found in a clip built with three"
    for truth in IMPULSE_TIMES:
        nearest = min(measured.transients, key=lambda t: abs(t.at_sec - truth))
        assert (
            abs(nearest.at_sec - truth) <= TIMING_TOLERANCE_SEC
        ), f"impulse at {truth}s was located at {nearest.at_sec}s"


def test_the_real_impulses_stand_clearly_above_the_noise(
    measured: signal.AudioFeatures,
) -> None:
    """Separation, not just detection.

    A detector that fires on everything also "finds" all three. What makes the
    marker floor in audio.py defensible is that the planted impulses score around
    57 and the strongest spurious peak scores under 10.
    """
    planted = [
        min(measured.transients, key=lambda t: abs(t.at_sec - truth)) for truth in IMPULSE_TIMES
    ]
    others = [t for t in measured.transients if t not in planted]

    assert min(t.prominence for t in planted) > 20.0
    if others:
        assert max(t.prominence for t in others) < min(t.prominence for t in planted) / 3


def _clip_with_clicks(
    click_times: tuple[float, ...], *, click_amp: float, bg_amp: float, seed: int
) -> np.ndarray:
    """Twelve seconds of engine-like 30Hz hum with 2ms clicks at known instants."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(12.0 * signal.TARGET_SAMPLE_RATE)) / signal.TARGET_SAMPLE_RATE
    clip = bg_amp * np.sin(2 * np.pi * 30.0 * t)
    clip += 0.005 * rng.standard_normal(t.size)
    width = int(0.002 * signal.TARGET_SAMPLE_RATE)
    for click in click_times:
        start = int(click * signal.TARGET_SAMPLE_RATE)
        clip[start : start + width] += click_amp
    return clip.astype(np.float32)


def test_onset_markers_hold_the_promised_twelve_milliseconds() -> None:
    """The module header claims onset timing accurate to ~12ms. Hold it there.

    The clicks are placed off the hop grid on purpose, and the check runs at
    several signal-to-noise ratios. The window-centre formula this replaces put
    every marker 19-36ms early - always early, never late - which is exactly
    the wrong-on-a-buyer's-timeline failure its own comment warned about.
    """
    clicks = (5.0, 8.003)
    for click_amp, bg_amp, seed in [
        (0.8, 0.2, 0),
        (0.3, 0.2, 1),
        (0.8, 0.05, 2),
        (0.8, 0.5, 3),
    ]:
        clip = _clip_with_clicks(clicks, click_amp=click_amp, bg_amp=bg_amp, seed=seed)
        measured = signal.features(clip)
        assert measured.transients, f"no transients at amp={click_amp} bg={bg_amp}"
        for truth in clicks:
            nearest = min(measured.transients, key=lambda t: abs(t.at_sec - truth))
            error_ms = (nearest.at_sec - truth) * 1000
            assert abs(error_ms) <= 12.0, (
                f"click at {truth}s marked at {nearest.at_sec}s "
                f"({error_ms:+.1f}ms) with amp={click_amp} bg={bg_amp}"
            )


def test_the_firing_fundamental_is_recovered(measured: signal.AudioFeatures) -> None:
    """The clip is built at 31.5Hz; the analysis has to find it within one bin."""
    assert measured.dominant_hz is not None
    bin_width = signal.TARGET_SAMPLE_RATE / signal.N_FFT
    assert abs(measured.dominant_hz - 31.5) <= bin_width
    assert measured.dominant_prominence_db > 6.0


def test_implied_rpm_is_arithmetic_not_a_guess() -> None:
    # A 4-cylinder four-stroke firing at 31.5Hz is idling near 945rpm.
    assert signal.implied_rpm(31.5, 4) == pytest.approx(945.0)
    # Six cylinders at the same firing rate means a slower crank, not a faster one.
    assert signal.implied_rpm(31.5, 6) == pytest.approx(630.0)
    with pytest.raises(ValueError):
        signal.implied_rpm(31.5, 0)


def test_a_guessed_cylinder_count_is_wrong_by_a_clean_factor() -> None:
    """Why audio.py refuses to report RPM without the VIN.

    The failure is not noisy, it is exactly 2x - a number that looks completely
    plausible on a dashboard.
    """
    assert signal.implied_rpm(31.5, 4) / signal.implied_rpm(31.5, 8) == pytest.approx(2.0)


def test_quality_accepts_the_fixture_clip(measured: signal.AudioFeatures) -> None:
    quality = signal.assess_quality(measured)
    assert quality.usable
    assert quality.problems == ()


def test_a_short_clip_is_rejected_with_a_reason() -> None:
    short = np.random.default_rng(1).standard_normal(signal.TARGET_SAMPLE_RATE) * 0.2
    quality = signal.assess_quality(signal.features(short.astype(np.float32)))
    assert not quality.usable
    assert any("seconds long" in p for p in quality.problems)


def test_a_clipped_clip_is_rejected_with_a_reason() -> None:
    loud = np.ones(signal.TARGET_SAMPLE_RATE * 10, dtype=np.float32)
    quality = signal.assess_quality(signal.features(loud))
    assert not quality.usable
    assert any("clipped" in p for p in quality.problems)


def test_a_silent_clip_is_rejected_and_says_nothing_about_the_engine() -> None:
    """Silence is a fact about the file. It is never reassurance."""
    silence = np.zeros(signal.TARGET_SAMPLE_RATE * 10, dtype=np.float32)
    quality = signal.assess_quality(signal.features(silence))
    assert not quality.usable
    assert "about the audio file, not about the engine" in quality.statement


def test_the_spectrogram_has_the_expected_shape(samples: np.ndarray) -> None:
    spec = signal.spectrogram(samples)
    assert spec.shape[0] == signal.N_FFT // 2 + 1
    assert spec.shape[1] > 1000
    assert np.isfinite(spec).all(), "a log of zero would poison the render"


def test_the_rendered_image_is_the_documented_size(samples: np.ndarray) -> None:
    image = signal.spectrogram_image(signal.spectrogram(samples))
    assert image.size == (1200, 360)
    assert image.mode == "RGB"


def test_an_impulse_survives_being_squeezed_into_the_image(samples: np.ndarray) -> None:
    """Max-pooling in time, not sampling.

    A 12ms tick occupies about one frame of nearly 1900. Picking every Nth column
    would drop it four times out of five, and the marker on the report would point
    at an empty stripe.
    """
    image = signal.spectrogram_image(signal.spectrogram(samples))
    pixels = np.asarray(image).astype(np.float32).mean(axis=2)

    # Measure the upper half only. A broadband tick is visible because it lights
    # up frequencies where there is otherwise nothing; the bottom of the image is
    # a permanent bright harmonic stack that swamps it in a whole-column mean.
    upper = pixels[: pixels.shape[0] // 2]
    column_energy = upper.mean(axis=0)
    baseline = float(np.median(column_energy))

    for truth in IMPULSE_TIMES:
        column = int(truth / 22.0 * image.size[0])
        window = column_energy[max(0, column - 6) : column + 7]
        assert (
            window.max() > baseline * 1.2
        ), f"the impulse at {truth}s is not visible in the rendered image"
