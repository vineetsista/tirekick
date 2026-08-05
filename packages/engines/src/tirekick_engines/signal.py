"""Audio signal processing. Arithmetic only - no model, and no opinions.

Everything in this module is a measurement of a waveform: how loud it is, whether
it clipped, what its dominant frequency is, where the sharp transients are. None
of it is a claim about an engine. That distinction is the whole design.

The reason it matters is that engine audio is the single most seductive input in
this product. A recording of a knocking engine sounds diagnostic, and a model
asked "what is wrong with this engine" will always answer. `docs/EVAL.md` has
committed in advance to what happens while `audio_anomaly` is below its gate: the
engine ships as a spectrogram and a list of things to ask a mechanic, with no
anomaly claims attached at all. This module is the half of that which is honest
today - the picture and the numbers under it.

A transient at 4.2 seconds is a fact about the file. What it means about a piston
is not, and nothing here pretends otherwise.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

#: Everything is resampled to this before analysis, so a phone recording at 48kHz
#: and one at 44.1kHz produce comparable numbers. Engine fundamentals live well
#: below 1kHz, so this is generous.
TARGET_SAMPLE_RATE = 22050

#: STFT parameters, and a real tradeoff rather than a default.
#:
#: 2048 samples at 22050Hz gives 10.8Hz of frequency resolution, which is what it
#: takes to separate an idle firing fundamental near 30Hz from its neighbours -
#: at 1024 the whole idle band collapses into four bins and the spectrogram shows
#: slabs instead of lines. The cost is a 93ms window, which smears a sharp tick.
#: The hop is kept short so onset *timing* stays accurate to ~12ms even though
#: the window is long.
N_FFT = 2048
HOP = 256

#: A sample within this of full scale is treated as clipped.
CLIP_CEILING = 0.995

#: Engine firing fundamentals sit in this band at any plausible idle.
FIRING_BAND_HZ = (15.0, 250.0)

#: Below this the clip is too short for anything, including a spectrogram worth
#: looking at.
MIN_USABLE_SECONDS = 4.0


class AudioUnavailable(RuntimeError):
    """The audio could not be decoded."""


@dataclass(frozen=True)
class Transient:
    """A sharp onset. A fact about the file, not a diagnosis."""

    at_sec: float
    prominence: float


@dataclass(frozen=True)
class AudioFeatures:
    duration_sec: float
    sample_rate: int
    rms_dbfs: float
    peak_dbfs: float
    clipped_fraction: float
    #: Loudest frequency inside the engine firing band, or None if nothing stands out.
    dominant_hz: float | None
    #: How far the dominant peak stands above the band's median, in dB. Low values
    #: mean the clip is broadband noise rather than a running engine.
    dominant_prominence_db: float
    transients: tuple[Transient, ...]
    #: Fraction of frames whose energy is within 3dB of the clip median - a proxy
    #: for how steady the recording is. Wind and traffic drive it down.
    steadiness: float


@dataclass(frozen=True)
class AudioQuality:
    """Whether this recording could support analysis at all."""

    usable: bool
    #: Buyer-facing reasons, empty when usable.
    problems: tuple[str, ...]
    statement: str


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def decode(path: Path, *, sample_rate: int = TARGET_SAMPLE_RATE) -> np.ndarray:
    """Decode any audio file to mono float32 in [-1, 1] via ffmpeg.

    ffmpeg rather than a Python decoder because a buyer's clip is whatever their
    phone produced - m4a, 3gp, aac in a mov container - and ffmpeg is the only
    thing that reliably reads all of it.
    """
    if not ffmpeg_available():
        raise AudioUnavailable(
            "ffmpeg is not installed. Audio analysis needs it; fixture mode reads "
            "cached features instead and needs nothing."
        )
    command = [
        "ffmpeg",
        "-nostdin",
        "-loglevel",
        "error",
        "-i",
        str(path),
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "-f",
        "f32le",
        "-",
    ]
    result = subprocess.run(command, capture_output=True, check=False)
    if result.returncode != 0:
        raise AudioUnavailable(
            f"ffmpeg could not decode {path.name}: "
            f"{result.stderr.decode('utf-8', 'replace').strip()[:200]}"
        )
    samples = np.frombuffer(result.stdout, dtype=np.float32)
    if samples.size == 0:
        raise AudioUnavailable(f"{path.name} decoded to no audio at all.")
    return samples.astype(np.float32, copy=True)


def spectrogram(samples: np.ndarray, *, n_fft: int = N_FFT, hop: int = HOP) -> np.ndarray:
    """Magnitude STFT in dB, shaped (frequency bins, time frames)."""
    if samples.size < n_fft:
        samples = np.pad(samples, (0, n_fft - samples.size))
    window = np.hanning(n_fft).astype(np.float32)
    frame_count = 1 + (samples.size - n_fft) // hop
    frames = np.lib.stride_tricks.sliding_window_view(samples, n_fft)[::hop][:frame_count]
    magnitude = np.abs(np.fft.rfft(frames * window, axis=1)).T
    # Floor before the log so silence is a number rather than negative infinity.
    return 20.0 * np.log10(np.maximum(magnitude, 1e-10))


def _dbfs(value: float) -> float:
    return float(20.0 * np.log10(max(value, 1e-10)))


def _find_transients(
    spec_db: np.ndarray, *, sample_rate: int, hop: int = HOP, limit: int = 12
) -> tuple[Transient, ...]:
    """Spectral-flux onset detection.

    Sums the frame-to-frame increase in energy across all bins - a sharp mechanical
    tick raises many bins at once, where a slow throttle change does not. Peaks
    are kept only if they stand clearly above the local variation, and the list is
    capped, because a report with forty markers on it is a report nobody reads.
    """
    if spec_db.shape[1] < 3:
        return ()
    flux = np.diff(spec_db, axis=1)
    flux = np.maximum(flux, 0.0).sum(axis=0)

    median = float(np.median(flux))
    spread = float(np.median(np.abs(flux - median))) or 1.0
    threshold = median + 6.0 * spread

    found: list[Transient] = []
    for index in range(1, flux.size - 1):
        value = float(flux[index])
        if value < threshold:
            continue
        # Local maximum only, so one onset produces one marker.
        if value < flux[index - 1] or value <= flux[index + 1]:
            continue
        # Report where the sound is, not where its analysis window began or is
        # centred.
        #
        # `flux[index]` is the rise from frame `index` to frame `index+1`.
        # Frame i spans [i*hop, i*hop + n_fft), so the samples frame index+1
        # can see and frame index cannot are exactly
        # [index*hop + n_fft, (index+1)*hop + n_fft) - one hop wide. A sound
        # that appears in that difference happened in that hop, and nowhere
        # else, so the honest estimate is its midpoint and the honest
        # uncertainty is half a hop: 5.8ms at 22.05kHz.
        #
        # Naming the frame's start was ~80ms early. Naming the window centre,
        # which replaced it, was 19-36ms early - always early, never late,
        # because a 2048-sample window is 93ms long and its centre sits well
        # before the edge the new sound arrived at.
        #
        # The peak of the flux is not the onset: a real transient has a rise
        # time, so the largest frame-to-frame difference lands one or two
        # frames after the sound began. Walking back to where the rise crossed
        # the threshold finds the frame that first saw it.
        first = index
        while first > 0 and flux[first - 1] >= threshold and flux[first - 1] < flux[first]:
            first -= 1
        onset = first * hop + N_FFT + hop / 2
        found.append(
            Transient(
                at_sec=round(onset / sample_rate, 3),
                prominence=round((value - median) / spread, 2),
            )
        )
    found.sort(key=lambda t: -t.prominence)
    return tuple(sorted(found[:limit], key=lambda t: t.at_sec))


def features(samples: np.ndarray, *, sample_rate: int = TARGET_SAMPLE_RATE) -> AudioFeatures:
    """Measure the waveform. Every field is a property of the file."""
    duration = samples.size / sample_rate
    rms = float(np.sqrt(np.mean(np.square(samples))))
    peak = float(np.max(np.abs(samples)))
    clipped = float(np.mean(np.abs(samples) >= CLIP_CEILING))

    spec_db = spectrogram(samples)
    freqs = np.fft.rfftfreq(N_FFT, 1.0 / sample_rate)

    band = (freqs >= FIRING_BAND_HZ[0]) & (freqs <= FIRING_BAND_HZ[1])
    dominant: float | None = None
    prominence = 0.0
    if band.any() and spec_db.shape[1] > 0:
        band_mean = spec_db[band].mean(axis=1)
        peak_index = int(np.argmax(band_mean))
        dominant = float(freqs[band][peak_index])
        prominence = float(band_mean[peak_index] - np.median(band_mean))

    frame_energy = spec_db.mean(axis=0)
    if frame_energy.size:
        centre = float(np.median(frame_energy))
        steadiness = float(np.mean(np.abs(frame_energy - centre) <= 3.0))
    else:
        steadiness = 0.0

    return AudioFeatures(
        duration_sec=round(duration, 3),
        sample_rate=sample_rate,
        rms_dbfs=round(_dbfs(rms), 2),
        peak_dbfs=round(_dbfs(peak), 2),
        clipped_fraction=round(clipped, 6),
        dominant_hz=round(dominant, 2) if dominant is not None else None,
        dominant_prominence_db=round(prominence, 2),
        transients=_find_transients(spec_db, sample_rate=sample_rate),
        steadiness=round(steadiness, 3),
    )


def assess_quality(measured: AudioFeatures) -> AudioQuality:
    """Can this recording support analysis at all?

    This is the one judgment in the module, and it is deliberately a judgment
    about the *recording* rather than about the vehicle. Telling a buyer their
    clip is four seconds of wind noise is useful and safe. Telling them their
    engine is fine because we heard nothing is neither.
    """
    problems: list[str] = []

    if measured.duration_sec < MIN_USABLE_SECONDS:
        problems.append(
            f"The clip is {measured.duration_sec:.1f} seconds long. Engine sounds "
            f"worth hearing - a cold start, a tick that comes and goes - need at "
            f"least {MIN_USABLE_SECONDS:.0f} seconds and ideally thirty."
        )
    if measured.clipped_fraction > 0.005:
        problems.append(
            f"{measured.clipped_fraction * 100:.1f}% of the recording is clipped - "
            f"the microphone was overloaded, and clipping destroys exactly the "
            f"detail an engine recording is for. Hold the phone further away."
        )
    if measured.rms_dbfs < -45.0:
        problems.append(
            f"The recording is very quiet ({measured.rms_dbfs:.0f} dBFS). Anything "
            f"faint is below the noise floor of the file itself."
        )
    if measured.dominant_prominence_db < 3.0:
        problems.append(
            "No steady tone stands out from the noise, which is what a running "
            "engine normally produces. This may be wind, traffic, or a recording "
            "made with the engine off."
        )

    if problems:
        return AudioQuality(
            usable=False,
            problems=tuple(problems),
            statement=(
                "This recording is not good enough to analyze. That is a statement "
                "about the audio file, not about the engine."
            ),
        )
    return AudioQuality(
        usable=True,
        problems=(),
        statement=(
            "The recording is long enough, loud enough, and steady enough to "
            "analyze. Whether TIREKICK can tell you anything from it is a separate "
            "question, answered on the accuracy page."
        ),
    )


def implied_rpm(dominant_hz: float, cylinders: int, *, stroke: int = 4) -> float:
    """Convert a firing frequency to engine RPM.

    A four-stroke engine fires each cylinder once per two revolutions, so the
    firing rate is `rpm / 60 * cylinders / 2`. Inverting gives the RPM below.

    Reported only when the cylinder count came from the VIN decode, because the
    arithmetic is exact and the input is not: guess the cylinders and the answer
    is wrong by a clean integer factor, which is the most convincing way to be
    wrong.
    """
    if cylinders <= 0:
        raise ValueError("cylinder count must be positive")
    return dominant_hz * 60.0 * (stroke / 2.0) / cylinders


#: The strip of the spectrum worth drawing. Engine content - firing order,
#: valvetrain, belt squeal - lives under 4kHz. Plotting to Nyquist wastes most of
#: the picture on hiss.
DISPLAY_MAX_HZ = 4000.0

#: Dark to bright ramp, sampled at these stops. Deliberately not a rainbow: a
#: rainbow map invents visual edges that are not in the data, which is precisely
#: the failure mode this whole product is trying to avoid.
_COLOR_STOPS: tuple[tuple[float, tuple[int, int, int]], ...] = (
    (0.00, (10, 12, 14)),
    (0.35, (26, 42, 58)),
    (0.60, (32, 96, 112)),
    (0.80, (108, 168, 130)),
    (0.92, (214, 176, 92)),
    (1.00, (245, 232, 208)),
)


def _ramp(normalized: np.ndarray) -> np.ndarray:
    """Map [0,1] to RGB through the stops above."""
    positions = np.array([stop for stop, _ in _COLOR_STOPS], dtype=np.float32)
    colors = np.array([rgb for _, rgb in _COLOR_STOPS], dtype=np.float32)
    out = np.empty((*normalized.shape, 3), dtype=np.float32)
    for channel in range(3):
        out[..., channel] = np.interp(normalized, positions, colors[:, channel])
    return out.astype(np.uint8)


def spectrogram_image(
    spec_db: np.ndarray,
    *,
    sample_rate: int = TARGET_SAMPLE_RATE,
    width: int = 1200,
    height: int = 360,
    floor_db: float = -75.0,
) -> Any:
    """Render a dB spectrogram to an image, low frequencies at the bottom.

    The picture is the deliverable. While `audio_anomaly` sits below its gate this
    is the entire audio output a buyer gets - a thing they can look at and,
    crucially, a thing they can show a mechanic - with no claims attached to it.
    """
    freqs = np.fft.rfftfreq(N_FFT, 1.0 / sample_rate)
    keep = freqs <= DISPLAY_MAX_HZ
    data = spec_db[keep]
    kept_freqs = freqs[keep]

    # Log frequency axis. On a linear axis every engine sound in the file is
    # crushed into the bottom two percent of the image and the remaining 98% is
    # empty black - technically accurate and useless to look at. Doubling
    # frequency should cover the same distance whether it happens at 40Hz or
    # 2kHz, which is also how anyone reading a spectrogram expects it to behave.
    if kept_freqs.size > 2:
        low = max(float(kept_freqs[1]), 25.0)
        high = float(kept_freqs[-1])
        targets = np.logspace(np.log10(low), np.log10(high), num=data.shape[0])
        rows = np.clip(np.searchsorted(kept_freqs, targets), 0, data.shape[0] - 1)
        data = data[rows]

    if data.shape[1] > width:
        # Max-pool in time rather than sample: a one-frame tick must survive being
        # squeezed into 1200 pixels, and picking every Nth column would drop it.
        edges = np.linspace(0, data.shape[1], width + 1).astype(int)
        data = np.stack(
            [
                data[:, edges[i] : max(edges[i] + 1, edges[i + 1])].max(axis=1)
                for i in range(width)
            ],
            axis=1,
        )

    ceiling = float(data.max()) if data.size else 0.0
    normalized = np.clip((data - (ceiling + floor_db)) / max(-floor_db, 1e-6), 0.0, 1.0)
    # Flip so low frequencies sit at the bottom, which is how everyone reads these.
    rgb = _ramp(np.flipud(normalized))

    from PIL import Image as _Image

    image = _Image.fromarray(rgb)
    return image.resize((width, height), _Image.Resampling.BILINEAR)


def write_spectrogram(
    spec_db: np.ndarray, path: Path, *, sample_rate: int = TARGET_SAMPLE_RATE
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    spectrogram_image(spec_db, sample_rate=sample_rate).save(path, format="PNG", optimize=True)
