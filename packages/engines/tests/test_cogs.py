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
    # 1M input at $5 + 100k output at $25/M = $5.00 + $2.50. The table once
    # said $15/$75 - a 3x overstatement asserted as fact in the note, because
    # a wrong number that IS in the table gets no caveat.
    assert round(meter.usd_total, 2) == 7.50


def test_the_documented_haiku_alias_is_priced_not_guessed() -> None:
    """TIREKICK_MODEL=claude-haiku-4-5 is the documented spelling. Keying the
    table only by the dated id silently priced the alias at the fallback rate -
    a 15x overstatement that at least confessed itself in the note."""
    meter = CostMeter(mode="live", model="claude-haiku-4-5")
    meter.record_model_call(label="x", input_tokens=1_000_000, output_tokens=0, images=0)
    assert round(meter.usd_total, 2) == 1.00
    assert "not in the price table" not in meter.note()


def test_the_note_counts_model_calls_not_federal_lookups() -> None:
    """A federal lookup is counted - LAW 5 - but it is not a model call, and
    the note must not say it was. A live demo run makes ~18 model calls plus 4
    lookups; the shipped note read '22 model calls'."""
    meter = CostMeter(mode="live", model="claude-sonnet-5")
    meter.record_model_call(label="a", input_tokens=10, output_tokens=5, images=0)
    meter.record_model_call(label="b", input_tokens=10, output_tokens=5, images=0)
    meter.record_federal_lookup("vpic decode")
    meter.record_federal_lookup("recalls")
    assert "2 model calls" in meter.note()
    assert meter.federal_lookups == 2


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
