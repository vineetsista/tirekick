"""Recall lookups: what a failure must say, and what "newest" must mean.

Two ways a recall list can lie without one false record in it. A lookup that
failed can render as "0 recall campaign(s) on record", which reads as a clean
bill and is actually a missing cache file - absence of evidence dressed up as
evidence of absence. And a list can promise "newest first" while sorting by
campaign number, which opens with a two-digit year and ranks every 1999
campaign above everything filed since.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from tirekick_engines.cogs import CostMeter
from tirekick_engines.engines import data as data_engine
from tirekick_engines.sources import DEFAULT_CACHE_DIR, FederalSources

GOLDEN_VIN = "1HGCM82673A000000"


def _recall_entry(campaign: str, received: str) -> dict[str, Any]:
    return {
        "NHTSACampaignNumber": campaign,
        "Component": "ELECTRICAL SYSTEM",
        "Summary": "Synthetic entry for sort-order tests. Describes no vehicle.",
        "ReportReceivedDate": received,
    }


def _campaign_order(payload: dict[str, Any]) -> list[str]:
    return [r.campaign_number for r in data_engine._recalls_from(payload)]


def test_a_failed_recall_lookup_is_never_rendered_as_zero_recalls(tmp_path: Path) -> None:
    """A lookup that failed and a lookup that found nothing are different facts.

    A partial federal cache - decode present, recalls file absent - is what a
    refresh run that crashed halfway leaves behind. The scope sentence must say
    the lookup could not be completed, never '0 recall campaign(s) on record':
    that sentence is an affirmative safety claim, and nothing ran to back it.
    """
    shutil.copy(DEFAULT_CACHE_DIR / f"vpic.decode.{GOLDEN_VIN}.json", tmp_path)
    sources = FederalSources(
        mode="fixture", cache_dir=tmp_path, meter=CostMeter(mode="fixture")
    )

    record = data_engine.lookup(GOLDEN_VIN, sources)

    assert record is not None
    assert record.recalls == []
    assert "0 recall campaign" not in record.recall_scope
    assert "could not be completed" in record.recall_scope
    assert "not the same as no recalls existing" in record.recall_scope
    # Nothing was looked up, so there is nothing to cite and - LAW 1 - nothing
    # to report as a finding either.
    assert data_engine.recall_findings(record) == []


def test_newest_first_is_chronological_across_the_century_boundary() -> None:
    """'99V...' is a 1999 campaign and must sort below everything since.

    Descending string order on campaign numbers ranks 1999 above 2024. The
    cars carrying campaigns on both sides of the boundary are real: the Takata
    era filed 15V-19V campaigns against 1999-2001 model years, next to those
    cars' original 99V/00V campaigns - and those are often the urgent ones.
    """
    payload = {
        "results": [
            _recall_entry("99V017000", "05/04/1999"),
            _recall_entry("16V061000", "09/02/2016"),
            _recall_entry("00V149000", "16/05/2000"),
        ]
    }
    assert _campaign_order(payload) == ["16V061000", "00V149000", "99V017000"]


def test_newest_first_follows_the_received_date_within_a_year() -> None:
    """Within one year the date decides. Campaign serials are not chronology."""
    payload = {
        "results": [
            _recall_entry("19V499000", "27/06/2019"),
            _recall_entry("19E068000", "10/10/2019"),
        ]
    }
    assert _campaign_order(payload) == ["19E068000", "19V499000"]


def test_a_record_without_a_date_still_lands_in_the_right_decade() -> None:
    """NHTSA does not always fill the date in; the campaign year still exists."""
    payload = {
        "results": [
            _recall_entry("99V017000", ""),
            _recall_entry("16V061000", ""),
        ]
    }
    assert _campaign_order(payload) == ["16V061000", "99V017000"]
