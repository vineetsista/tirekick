"""Audio engine.

**This engine still makes no claims about any engine, and that is the deliverable.**

`audio_anomaly` sits at a 0.70 precision gate with no measurement behind it, so
LAW 4 forbids it from appearing in a paid report. `docs/EVAL.md` committed in
advance to what happens in exactly this situation: the engine ships as a
spectrogram and a list of things to ask a mechanic, with no anomaly claims
attached. P3 is that commitment being honoured rather than quietly revisited now
that there is a working detector and it would be easy to say something.

So what a buyer gets is a picture and a row of measured facts under it: how long
the clip is, whether it clipped, what the dominant frequency is, and where the
sharp transients are. Three vertical lines on a spectrogram at 5.0, 11.5 and 17.2
seconds is a true statement about a file. "Your engine is knocking" is not a
statement we have earned, and the difference between those two is the entire
product.

Features are cached like federal records, for the same reason: fixture mode must
need nothing, and requiring ffmpeg to render a committed report would make the
gate that proves that dependency-free itself depend on something (D-026).
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .. import signal as signal_module
from ..cogs import CostMeter
from ..models import (
    Asset,
    AudioTrack,
    AudioTransient,
    DraftFinding,
    VehicleRecord,
)

#: What a buyer is told about audio while the anomaly gate is unmet.
GATE_STATEMENT = (
    "TIREKICK does not make claims about engine condition from audio. The anomaly "
    "detector has not been measured against a labelled set, so under our own "
    "accuracy rules it cannot appear in a report. What is below is the recording "
    "itself, drawn as a spectrogram, and the measurements taken from it. Listen to "
    "the clip yourself, and play it to a mechanic at a cold start."
)

P0_STATEMENT = (
    "An engine audio clip was provided and stored with this inspection. TIREKICK "
    "does not yet analyze engine audio - that engine is in development and will "
    "not make claims until its accuracy has been measured and published. Listen "
    "to the clip yourself, and ask a mechanic to listen at a cold start."
)

#: Only worth drawing on the timeline. The weak tail of the onset detector is
#: mostly the noise floor breathing, and a report with forty markers is a report
#: nobody reads.
MARKER_PROMINENCE_FLOOR = 20.0


def has_audio(assets: list[Asset]) -> bool:
    return any(a.kind == "audio" for a in assets)


def spectrogram_name(asset_id: str) -> str:
    return f"{asset_id}.spectrogram.png"


def cache_path(cache_dir: Path, asset_id: str) -> Path:
    return cache_dir / f"audio.features.{asset_id}.json"


def compute(path: Path) -> tuple[dict[str, object], signal_module.AudioFeatures]:
    """Decode and measure. Needs ffmpeg; only the refresh script calls it."""
    samples = signal_module.decode(path)
    measured = signal_module.features(samples)
    return asdict(measured), measured


def _implied_rpm(
    measured: signal_module.AudioFeatures, vehicle: VehicleRecord | None
) -> tuple[int | None, str]:
    """RPM from the firing frequency, but only when the VIN supplied cylinders.

    The arithmetic is exact and the input is not. Guess the cylinder count and the
    answer is wrong by a clean integer factor - 969rpm becomes 1938 - which is the
    most convincing possible way to be wrong. So it is reported only when vPIC
    told us, and the basis says where the number came from either way.
    """
    if measured.dominant_hz is None:
        return None, "No steady tone stood out, so no firing frequency was measured."

    cylinders = _cylinder_count(vehicle)
    if cylinders is None:
        return None, (
            f"The loudest steady tone is {measured.dominant_hz:.1f}Hz. Converting "
            f"that to engine RPM needs the cylinder count, which this VIN did not "
            f"give us, so no RPM is shown - a guessed cylinder count would put the "
            f"answer out by a clean factor of two and look entirely plausible."
        )

    rpm = signal_module.implied_rpm(measured.dominant_hz, cylinders)
    # A four-stroke fires once per cylinder every two revolutions, so the rate
    # is cylinders/2 - which is not a whole number on a three- or five-cylinder
    # engine. Integer division printed "fires 1 times per revolution" beside an
    # rpm figure computed from 1.5, so the sentence and the number in it
    # disagreed, in the one place the report shows its arithmetic.
    firings = cylinders / 2
    firing_text = f"{firings:g}"
    return round(rpm), (
        f"The loudest steady tone is {measured.dominant_hz:.1f}Hz. A four-stroke "
        f"{cylinders}-cylinder engine fires {firing_text} times per revolution, "
        f"which puts this at about {round(rpm):,} rpm. That is arithmetic on the "
        f"recording, not a reading from the vehicle."
    )


def _cylinder_count(vehicle: VehicleRecord | None) -> int | None:
    """Pull the cylinder count out of the decoded engine description."""
    if vehicle is None or not vehicle.decoded.engine:
        return None
    for token in vehicle.decoded.engine.split():
        if token.endswith("-cyl"):
            try:
                return int(token.removesuffix("-cyl"))
            except ValueError:
                return None
    return None


def load_track(
    assets: list[Asset],
    media_root: Path,
    cache_dir: Path,
    meter: CostMeter,
    *,
    vehicle: VehicleRecord | None = None,
) -> AudioTrack | None:
    """The audio section of the report, or None when no clip was provided."""
    clip = next((a for a in assets if a.kind == "audio"), None)
    if clip is None:
        return None

    path = cache_path(cache_dir, clip.id)
    if not path.is_file():
        # No cached measurement. Silence is the honest output - inventing a
        # spectrogram or defaulting the numbers to zero would both read as
        # findings about the recording.
        if clip.duration_sec is not None:
            meter.record_audio(clip.duration_sec)
        return None

    raw = json.loads(path.read_text(encoding="utf-8"))
    measured = signal_module.AudioFeatures(
        duration_sec=raw["duration_sec"],
        sample_rate=raw["sample_rate"],
        rms_dbfs=raw["rms_dbfs"],
        peak_dbfs=raw["peak_dbfs"],
        clipped_fraction=raw["clipped_fraction"],
        dominant_hz=raw["dominant_hz"],
        dominant_prominence_db=raw["dominant_prominence_db"],
        transients=tuple(
            signal_module.Transient(at_sec=t["at_sec"], prominence=t["prominence"])
            for t in raw["transients"]
        ),
        steadiness=raw["steadiness"],
    )
    meter.record_audio(measured.duration_sec)

    quality = signal_module.assess_quality(measured)
    rpm, rpm_basis = _implied_rpm(measured, vehicle)

    markers = [
        AudioTransient(at_sec=t.at_sec, prominence=t.prominence)
        for t in measured.transients
        if t.prominence >= MARKER_PROMINENCE_FLOOR
    ]

    spectrogram = media_root / spectrogram_name(clip.id)

    return AudioTrack(
        asset_id=clip.id,
        duration_sec=measured.duration_sec,
        sample_rate=measured.sample_rate,
        spectrogram_path=spectrogram_name(clip.id) if spectrogram.is_file() else "",
        rms_dbfs=measured.rms_dbfs,
        peak_dbfs=measured.peak_dbfs,
        clipped_fraction=measured.clipped_fraction,
        dominant_hz=measured.dominant_hz,
        implied_rpm=rpm,
        implied_rpm_basis=rpm_basis,
        transients=markers,
        transient_statement=_transient_statement(markers, measured.duration_sec),
        usable=quality.usable,
        quality_statement=quality.statement,
        quality_problems=list(quality.problems),
        claims_enabled=False,
        claims_statement=GATE_STATEMENT,
    )


def _transient_statement(markers: list[AudioTransient], duration: float) -> str:
    """Describe the marks on the timeline without saying what made them."""
    if not markers:
        return (
            "No sharp transients stood out from the recording. That is not "
            "reassurance about the engine - a knock that only appears cold, "
            "under load, or after twenty minutes will not be in a clip like "
            "this one."
        )
    times = ", ".join(f"{m.at_sec:.1f}s" for m in markers)
    return (
        f"{len(markers)} sharp transient(s) stand out from the rest of the "
        f"recording, at {times} of {duration:.0f}s. A transient is a sudden "
        f"broadband sound. It could be a mechanical tick. It could equally be a "
        f"door, a footstep, or the phone brushing a sleeve. TIREKICK is showing "
        f"you where to listen, not telling you what it heard."
    )


def analyze(assets: list[Asset], meter: CostMeter) -> list[DraftFinding]:
    """No findings, by design. See the module docstring and LAW 4."""
    del assets, meter
    return []
