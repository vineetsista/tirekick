"""The implied-RPM basis sentence, held to its own arithmetic.

The RPM figure is computed in float; the sentence beside it is the buyer's
justification for that figure (LAW 1). If the sentence's arithmetic does not
reproduce the number, the report contradicts itself in the most convincing
possible way - which is precisely the failure mode the function's docstring
warns about.
"""

from __future__ import annotations

from tirekick_engines import signal
from tirekick_engines.engines import audio
from tirekick_engines.models import DecodedVehicle, VehicleRecord


def _vehicle(engine: str) -> VehicleRecord:
    return VehicleRecord(
        vin="1HGCR2F37DA000000",
        vin_masked="1HGCR2F37DA*****",
        vin_valid=True,
        vin_statement="Structurally valid.",
        decoded=DecodedVehicle(engine=engine),
        recall_scope="Recalls are published per model, not per VIN.",
    )


def _measured(dominant_hz: float) -> signal.AudioFeatures:
    return signal.AudioFeatures(
        duration_sec=22.0,
        sample_rate=signal.TARGET_SAMPLE_RATE,
        rms_dbfs=-18.0,
        peak_dbfs=-3.0,
        clipped_fraction=0.0,
        dominant_hz=dominant_hz,
        dominant_prominence_db=9.0,
        transients=(),
        steadiness=0.9,
    )


def test_an_odd_cylinder_count_states_the_true_firing_rate() -> None:
    """A 3-cylinder four-stroke fires 1.5 times per revolution. The old
    integer division printed "1", whose arithmetic gives 2,700rpm next to a
    shown figure of 1,800."""
    rpm, basis = audio._implied_rpm(_measured(45.0), _vehicle("1.0L 3-cyl turbo"))
    assert rpm == round(signal.implied_rpm(45.0, 3)) == 1800
    assert "1.5 times per revolution" in basis
    # The sentence's own arithmetic must reproduce the shown figure.
    assert round(45.0 * 60 / 1.5) == rpm


def test_an_even_cylinder_count_still_reads_as_a_whole_number() -> None:
    rpm, basis = audio._implied_rpm(_measured(31.5), _vehicle("2.4L 4-cyl"))
    assert rpm == 945
    assert "fires 2 times per revolution" in basis
    assert "2.0" not in basis


def test_five_cylinders_fire_two_and_a_half_times() -> None:
    rpm, basis = audio._implied_rpm(_measured(50.0), _vehicle("2.5L 5-cyl"))
    assert rpm == round(signal.implied_rpm(50.0, 5)) == 1200
    assert "2.5 times per revolution" in basis
