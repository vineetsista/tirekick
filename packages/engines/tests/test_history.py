"""Title-brand scanning over user-supplied documents.

Half of these tests are about what the scanner must NOT say. A false salvage call
talks a buyer out of a clean car, and the phrasing that triggers it is not exotic
- it is how every clean history report in the world is written.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tirekick_engines.engines import history
from tirekick_engines.models import Asset

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_MEDIA = REPO_ROOT / "fixtures" / "demo-01" / "media"


def _document(tmp_path: Path, text: str) -> tuple[list[Asset], Path]:
    path = tmp_path / "history.txt"
    path.write_text(text, encoding="utf-8")
    asset = Asset(
        id="doc_01",
        kind="document",
        path="history.txt",
        sha256="0" * 64,
        bytes=len(text.encode("utf-8")),
        synthetic=True,
    )
    return [asset], tmp_path


#: Lines that report a brand. Each must produce a finding.
ASSERTING = [
    "Title brand: SALVAGE",
    "SALVAGE TITLE ISSUED 03/2019",
    "Flood damage reported by insurer",
    "Manufacturer buyback recorded under state lemon law",
    "Odometer rollback detected",
    "Vehicle declared a total loss 2020-06",
]

#: Lines that rule a brand out. None of these may produce a finding, ever.
DENYING = [
    "Salvage brand ............... None reported",
    "Salvage: None",
    "Flood or water damage ....... No records found",
    "Lemon law buyback ........... None",
    "Junk / non-repairable ....... None",
    "Total loss: not reported",
    "Odometer: no discrepancy reported",
    "Frame damage: none disclosed",
    "No salvage or flood history on record",
    "No salvage title on record",
    "Never declared a total loss",
    "Salvage records: 0",
    "Salvage? No.",
]

#: Real reports number their rows. In each of these "No." abbreviates "number"
#: and the line is asserting the brand at full strength.
ENUMERATED_ASSERTING = [
    "No. 3 - SALVAGE TITLE ISSUED",
    "Record No. 4: FLOOD DAMAGE REPORTED",
    "Item No. 2 - REBUILT TITLE ISSUED",
]


@pytest.mark.parametrize("line", ASSERTING)
def test_an_asserted_brand_becomes_a_finding(tmp_path: Path, line: str) -> None:
    assets, root = _document(tmp_path, line)
    drafts = history.title_brand_findings(assets, root)
    assert len(drafts) == 1, f"expected a finding for {line!r}"
    assert drafts[0].type == "title_brand_indicator"
    assert drafts[0].confidence == 1.0


@pytest.mark.parametrize("line", DENYING)
def test_a_denied_brand_produces_nothing(tmp_path: Path, line: str) -> None:
    """The test that protects clean cars.

    'None reported' contains a negation and an assertion verb at once. Reading it
    as ambiguous - which an earlier version of this scanner did - put a salvage
    indicator on a fixture whose paperwork explicitly denied one.
    """
    assets, root = _document(tmp_path, line)
    assert history.title_brand_findings(assets, root) == []


@pytest.mark.parametrize("line", ENUMERATED_ASSERTING)
def test_an_enumerated_record_row_is_read_as_asserting(tmp_path: Path, line: str) -> None:
    """The test that protects branded cars from reading as clean.

    'No. 3 - SALVAGE TITLE ISSUED' contains no denial at all: 'No.' is how a
    numbered report says 'number'. A scanner that reads it as negation drops
    the salvage brand silently - the false negative ACCURACY.md names as the
    costliest error, in the opposite direction from the 'Salvage: None' case.
    """
    assets, root = _document(tmp_path, line)
    drafts = history.title_brand_findings(assets, root)
    assert len(drafts) == 1, f"expected a finding for {line!r}"
    assert drafts[0].confidence == 1.0, f"{line!r} must ship asserted, not hedged"
    assert drafts[0].severity == "major"


def test_a_later_outright_assertion_outranks_an_earlier_hedge(tmp_path: Path) -> None:
    """One finding per brand, at the strongest reading the document supports.

    A line carrying both a denial token and an assertion verb ships hedged.
    But when a later line asserts the same brand outright, keeping the hedge
    because it arrived first would soften a salvage warning to minor at half
    confidence - and cite the muddier line as the evidence.
    """
    text = (
        "Odometer reading: 0 discrepancies. SALVAGE TITLE ISSUED 2020\n"
        "Salvage title issued 03/2019\n"
    )
    assets, root = _document(tmp_path, text)
    drafts = history.title_brand_findings(assets, root)
    assert len(drafts) == 1
    assert drafts[0].confidence == 1.0
    assert drafts[0].severity == "major"
    evidence = drafts[0].evidence[0]
    assert evidence.kind == "document_excerpt"
    assert evidence.excerpt == "Salvage title issued 03/2019"
    assert "line 2" in evidence.caption


def test_the_matched_line_is_quoted_back_verbatim(tmp_path: Path) -> None:
    """LAW 1. The excerpt is the evidence, so the buyer can check our reading."""
    assets, root = _document(tmp_path, "Body shop invoice notes frame damage, repaired.")
    drafts = history.title_brand_findings(assets, root)
    evidence = drafts[0].evidence[0]
    assert evidence.kind == "document_excerpt"
    assert evidence.excerpt == "Body shop invoice notes frame damage, repaired."
    assert "line 1" in evidence.caption


def test_structural_damage_is_routed_at_a_locked_system(tmp_path: Path) -> None:
    """LAW 2 reaches text findings, not just image ones.

    A document reporting frame damage must leave the pipeline as a mechanic
    referral. We can pass on the alarm; we cannot grade the repair.
    """
    assets, root = _document(tmp_path, "Structural damage recorded 2021-08")
    drafts = history.title_brand_findings(assets, root)
    assert drafts[0].system == "structure"


def test_no_finding_claims_a_title_search_was_performed(tmp_path: Path) -> None:
    """We query no title registry, and the copy has to say so unprompted."""
    assets, root = _document(tmp_path, "Title brand: SALVAGE")
    detail = history.title_brand_findings(assets, root)[0].detail
    assert "did not query any title registry" in detail
    assert "your state" in detail


def test_one_finding_per_brand_however_many_lines_mention_it(tmp_path: Path) -> None:
    text = "Title brand: SALVAGE\nSalvage retained by owner\nSALVAGE - see page 4\n"
    assets, root = _document(tmp_path, text)
    assert len(history.title_brand_findings(assets, root)) == 1


def test_the_most_serious_pattern_wins_a_shared_line(tmp_path: Path) -> None:
    """A line naming several brands is reported once, at the worst of them."""
    assets, root = _document(tmp_path, "Junk title issued after flood damage")
    drafts = history.title_brand_findings(assets, root)
    assert len(drafts) == 1
    assert drafts[0].id.startswith("title_junk")


def test_unreadable_documents_are_skipped_not_guessed(tmp_path: Path) -> None:
    """A scanned PDF is an OCR problem. Until P2 it is reported as unread."""
    (tmp_path / "report.pdf").write_bytes(b"%PDF-1.4 salvage")
    asset = Asset(
        id="doc_pdf",
        kind="document",
        path="report.pdf",
        sha256="0" * 64,
        bytes=16,
        synthetic=True,
    )
    assert history.title_brand_findings([asset], tmp_path) == []


def test_photos_are_never_scanned_as_documents(tmp_path: Path) -> None:
    asset = Asset(id="photo_01", kind="photo", path="photo_01.jpg", sha256="0" * 64, bytes=10)
    assert history.title_brand_findings([asset], tmp_path) == []


def test_the_committed_fixture_document_behaves_as_documented() -> None:
    """The demo fixture exercises both directions on every run.

    Its paperwork denies salvage, flood, lemon and junk, and reports hail and
    structural damage. If this ever changes shape, the golden report changes with
    it and someone has to look.
    """
    asset = Asset(
        id="history_01",
        kind="document",
        path="history_01.txt",
        sha256="0" * 64,
        bytes=(FIXTURE_MEDIA / "history_01.txt").stat().st_size,
        synthetic=True,
    )
    drafts = history.title_brand_findings([asset], FIXTURE_MEDIA)
    keys = {d.id for d in drafts}

    assert keys == {"title_hail_history_01", "title_structural_history_01"}
    assert not any("salvage" in k for k in keys), "the fixture denies salvage"
    assert not any("flood" in k for k in keys), "the fixture denies flood damage"
