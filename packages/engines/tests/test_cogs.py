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
    meter = CostMeter(mode="live", model="claude-sonnet-5")
    meter.record_model_call(label="x", input_tokens=1_000_000, output_tokens=100_000, images=1)
    # 1M input at $3 + 100k output at $15/M = $3.00 + $1.50
    assert round(meter.usd_total, 2) == 4.50


def test_a_different_model_is_priced_differently() -> None:
    """Price and model choice are one decision. A global rate silently lies."""
    meter = CostMeter(mode="live", model="claude-opus-5")
    meter.record_model_call(label="x", input_tokens=1_000_000, output_tokens=100_000, images=1)
    # 1M input at $15 + 100k output at $75/M = $15.00 + $7.50
    assert round(meter.usd_total, 2) == 22.50


def test_an_unknown_model_is_priced_at_the_worst_rate_and_says_so() -> None:
    """Guessing cheap on an unknown model is how unit economics quietly break."""
    meter = CostMeter(mode="live", model="some-model-we-have-not-priced")
    meter.record_model_call(label="x", input_tokens=1_000_000, output_tokens=0, images=1)
    assert round(meter.usd_total, 2) == 15.00
    assert "not in the price table" in meter.note()
    assert "upper bound" in meter.note()


def test_render_always_prints_a_total() -> None:
    rendered = CostMeter(mode="fixture").render()
    assert "COST OF THIS REPORT" in rendered
    assert "TOTAL" in rendered
