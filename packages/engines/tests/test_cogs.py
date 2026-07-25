"""LAW 5 - the cost meter."""

from __future__ import annotations

from tirekick_engines.cogs import CostMeter


def test_fixture_mode_is_honestly_zero_and_says_why() -> None:
    meter = CostMeter(mode="fixture")
    meter.record_model_call(label="x", input_tokens=5000, output_tokens=800, images=4)
    assert meter.usd_total == 0.0
    assert "no API calls billed" in meter.note()
    assert "not a placeholder" in meter.note()


def test_fixture_mode_still_counts_the_work() -> None:
    """A zero cost is honest. A zero image count would be hiding the shape of it."""
    meter = CostMeter(mode="fixture")
    meter.record_model_call(label="x", input_tokens=0, output_tokens=0, images=8)
    meter.record_audio(22.0)
    meter.record_storage(3_000_000)
    assert meter.images_analyzed == 8
    assert meter.audio_seconds_processed == 22.0
    assert meter.storage_bytes == 3_000_000


def test_live_mode_prices_tokens() -> None:
    meter = CostMeter(mode="live")
    meter.record_model_call(label="x", input_tokens=1_000_000, output_tokens=100_000, images=1)
    # 1M input at $3 + 100k output at $15/M = $3.00 + $1.50
    assert round(meter.usd_total, 2) == 4.50


def test_render_always_prints_a_total() -> None:
    rendered = CostMeter(mode="fixture").render()
    assert "COST OF THIS REPORT" in rendered
    assert "TOTAL" in rendered
