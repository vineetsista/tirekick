"""Title-brand scanning over user-supplied documents.

Half of these tests are about what the scanner must NOT say. A false salvage call
talks a buyer out of a clean car, and the phrasing that triggers it is not exotic
- it is how every clean history report in the world is written.
"""

from __future__ import annotations

import re
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
    # The pipe table with the answer filled in. A row is one statement in both
    # directions, so the layout that must not manufacture a denial must not
    # swallow an assertion either.
    "| Salvage | Reported 03/2019 |",
]

#: Lines that rule a brand out. None of these may produce a finding, ever.
DENYING = [
    "Salvage brand ............... None reported",
    "Salvage: None",
    "Flood or water damage ....... No records found",
    "Lemon law buyback ........... None",
    "Junk / non-repairable ....... None",
    "Total loss: not reported",
    "Odometer discrepancy: none reported",
    "Frame damage: none disclosed",
    "No salvage or flood history on record",
    "No salvage title on record",
    "Never declared a total loss",
    "Salvage records: 0",
    "Salvage? No.",
    # A dot-leader row whose answer is N/A. The leader is the whole separator -
    # there is no colon to hang the denial off, and the scanner read these as
    # asserted until P10: a false salvage call on a clean car, printed from the
    # commonest table layout there is.
    "Salvage ....................... N/A",
    "Flood or water damage ......... n/a",
    # "No" immediately followed by a number is an enumeration everywhere except
    # here, where it is a date range inside a denial. We do not strip a bare
    # "No <digits>" for exactly this reason; the period is what marks a row
    # number, and real reports print it.
    "No 2019-2023 salvage records found",
    # The mirror of DENIAL_IN_ANOTHER_CLAUSE below: the denial is in the clause
    # that carries the brand, so the other clause's verb changes nothing.
    "Title issued 03/2015. No salvage brand reported",
    # A pipe table, which is what a history report in Markdown is made of. The
    # scanner read the pipe as a statement boundary for one session, and every
    # row below came out a major at confidence 1.0 with its own denial quoted
    # underneath as the evidence. A cell separator is not a sentence.
    "| Salvage | None reported |",
    "| Salvage title | None |",
    "| Flood or water damage | No records found |",
    "| Total loss | Not reported | 2019 |",
    # The same label-and-answer row punctuated with the separators that ARE
    # statement boundaries. The answer says nothing of its own - no subject, no
    # date, nothing but the denial - so it belongs to the label in front of it
    # however it is punctuated, and splitting there reads the label alone.
    "Salvage. None reported",
    "Salvage; none reported",
    "Salvage brand; not reported",
    "Salvage brand; none reported 03/2019",
    # A denial of the brand and a denial of something else, on one comma-joined
    # line. Nothing here asserts anything, so blanking the negations out has to
    # leave a line that still reads as clean rather than one that reads as
    # unreadable. The comma fix below must not hedge this row.
    "Salvage: none reported, no liens recorded",
    "Flood or water damage: none reported, no claims found",
]

#: A denial of something ELSE sharing a statement with an asserted brand. A
#: comma, a dash and a table pipe are not clause breaks - nothing in the text
#: tells a cell apart from a sentence - so the whole line is one statement and
#: both signals are in it. Until this list existed the denial won outright and
#: the brand vanished: a vehicle whose own paperwork declares salvage produced
#: no title-brand finding at all, and the buyer never saw the line, so they
#: could not check the reading. That is the silent drop D-017 calls the worse
#: of the two errors. Hedged is the answer; hedged is not silence.
CROWDED_STATEMENT_HEDGED = [
    "SALVAGE TITLE ISSUED 03/2019, no accidents reported",
    "Flood damage reported 06/2018, none disclosed by seller",
    "Title: SALVAGE BRANDED 2019 - no odometer rollback indicated",
    "| SALVAGE TITLE ISSUED 03/2019 | no accidents reported |",
]

#: Filler with no brand keyword and no negation in it, wide enough that a
#: keyword placed after it falls past MAX_EXCERPT_CHARS. Real history reports
#: print one record per row and the rows are wide, so this is the ordinary
#: shape of a document, not a contrived one.
_WIDE_FILLER = "prior owner history entry " * 13

#: The same filler in fixed-width columns, which is what a report built for a
#: line printer looks like. It is here because the excerpt is quoted with its
#: whitespace squeezed while the keyword's offset is an index into the raw line,
#: and 35 spaces of column padding put those two numbers 300 characters apart.
#: A window centred on the raw offset lands past the end of the keyword and
#: quotes the padding instead - the same empty evidence as before the fix, with
#: the fix in place.
_PADDED_COLUMN = f"{'prior owner history entry':<60}"

#: Wide single-line rows with the cited keyword at the end, at the start, in the
#: middle, and behind column padding. The excerpt truncated from the start of
#: the line, so on all but the third of these the published evidence did not
#: contain the word the finding was about - underneath copy promising the line
#: was quoted exactly as it appears.
WIDE_LINES = [
    f"{_WIDE_FILLER}SALVAGE TITLE ISSUED 03/2019 {_WIDE_FILLER}",
    f"{_WIDE_FILLER}{_WIDE_FILLER}FLOOD DAMAGE REPORTED 03/2019",
    f"JUNK TITLE ISSUED 03/2019 {_WIDE_FILLER}{_WIDE_FILLER}",
    f"{_PADDED_COLUMN * 9}SALVAGE TITLE ISSUED 03/2019 {_PADDED_COLUMN * 9}",
]

#: The one line the scanner is allowed to soften, and the reason it is here
#: rather than in ASSERTING. Nothing tells a cell separator apart from a
#: sentence boundary except what the cells say, so a pipe is never a boundary -
#: which means the N/A about the prior owner sits in the same statement as the
#: brand, both signals show, and the finding ships hedged. That is a downgrade
#: of degree on one contrived row. Reading the pipe as a boundary instead buys
#: that row full strength and turns every row of DENYING's pipe table into a
#: major on a clean car, which is the direction D-017 forbids.
CELL_SEPARATOR_HEDGED = [
    "SALVAGE TITLE ISSUED | Prior owner: N/A",
]

#: Real reports number their rows. In each of these "No." abbreviates "number"
#: and the line is asserting the brand at full strength.
ENUMERATED_ASSERTING = [
    "No. 3 - SALVAGE TITLE ISSUED",
    "No.3 SALVAGE TITLE ISSUED",
    "NO. 12 - JUNK / NON-REPAIRABLE",
    "Record No. 4: FLOOD DAMAGE REPORTED",
    "Item No. 2 - REBUILT TITLE ISSUED",
    # The same row number with the period dropped, which is how a report that
    # puts the label in its own column prints it.
    "Record No 3 - SALVAGE TITLE ISSUED",
    "Stock No 44 - FLOOD DAMAGE REPORTED",
    # Numbering that never touches the word "no" at all. These have always
    # worked; they are here so that a future rewrite of the enumeration rule
    # cannot break them quietly.
    "#3  FLOOD DAMAGE REPORTED  TX",
    "3. SALVAGE TITLE ISSUED 03/12/2019",
]

#: Row labels we claim to recognise in front of an unpunctuated "No 7". Each is
#: exercised, because a label listed in the pattern and in no test is a claim
#: nothing checks.
ROW_LABELS = ["Record", "Item", "Stock", "Entry", "Line", "Ref", "Seq"]

#: Brands whose own name contains a negation word. "NOT ACTUAL MILEAGE" is the
#: federal odometer brand, printed in those words on the title itself - so the
#: "not" belongs to the brand, not to a denial of it.
BRAND_NAMED_WITH_A_NEGATION = [
    "Odometer brand: NOT ACTUAL MILEAGE",
    "ODOMETER: NOT ACTUAL MILEAGE - BRAND APPLIED 2018",
    "Title issued with odometer reading NOT ACTUAL MILEAGE",
    # The brand followed by a denial of something else, which is where the two
    # guards collided: masking the brand's name put whitespace in front of the
    # full stop, the dot-leader lookbehind then refused to split there, and the
    # odometer brand - the one that undermines every mileage-based judgment in
    # the report - went back to being unreportable. The mask has to keep the
    # width and it has to not be whitespace.
    "Odometer: NOT ACTUAL MILEAGE. No accidents reported",
    "ODOMETER BRAND: NOT ACTUAL MILEAGE; no damage found",
]

#: Lines where a real denial sits in one clause and the brand in another. The
#: denial is true and says nothing about the brand beside it.
DENIAL_IN_ANOTHER_CLAUSE = [
    "No accidents reported. SALVAGE TITLE ISSUED 03/2019",
    "No damage found; total loss recorded 2020",
    # This one used to be the hedged half of the ranking test below. The "0"
    # denies a discrepancy in the odometer reading and denies nothing about the
    # salvage brand in the next sentence, so it is asserted now, and the line
    # is kept here to record that the reading changed on purpose.
    "Odometer reading: 0 discrepancies. SALVAGE TITLE ISSUED 2020",
    # A numbered row whose brand is followed by a denial of something else.
    # Both guards fire here and each has to leave the other's work intact: the
    # row number is masked before the line is split, so the mask has to be the
    # same width as what it replaced or every offset after it slides and the
    # brand is read in the wrong statement.
    "Record No. 4 - SALVAGE. No accidents reported",
    "Record No. 4 - SALVAGE; no damage found",
]

#: The separators the scanner reads as a boundary between statements. Each is
#: exercised in both directions below, because a separator tested only in the
#: asserting direction is how the pipe shipped: it closed one false negative
#: and opened a false major on every clean row of a table.
CLAUSE_SEPARATORS = [".", ";"]


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


@pytest.mark.parametrize("label", ROW_LABELS)
def test_every_row_label_we_claim_to_read_is_read(tmp_path: Path, label: str) -> None:
    """One test per label word, so the list in the pattern is not decoration."""
    assets, root = _document(tmp_path, f"{label} No 7 - SALVAGE TITLE ISSUED")
    drafts = history.title_brand_findings(assets, root)
    assert len(drafts) == 1, f"{label!r} row number read as a denial"
    assert drafts[0].confidence == 1.0


@pytest.mark.parametrize("line", BRAND_NAMED_WITH_A_NEGATION)
def test_a_brand_whose_name_contains_not_is_still_reported(tmp_path: Path, line: str) -> None:
    """The negation lookalike that lived inside our own keyword list.

    "not actual mileage" is one of the brands this engine scans for, and it is
    spelled with a negation word, so every line carrying it in its canonical
    form read as a denial of itself. The odometer brand could not be reported
    at all in the wording titles actually use - a false negative on the one
    finding that undermines every mileage-based judgment in the report.
    """
    assets, root = _document(tmp_path, line)
    drafts = history.title_brand_findings(assets, root)
    assert len(drafts) == 1, f"expected a finding for {line!r}"
    assert drafts[0].id.startswith("title_odometer")
    assert drafts[0].confidence == 1.0, f"{line!r} must ship asserted, not hedged"
    assert drafts[0].severity == "major"


@pytest.mark.parametrize("line", DENIAL_IN_ANOTHER_CLAUSE)
def test_a_denial_of_something_else_does_not_deny_the_brand(tmp_path: Path, line: str) -> None:
    """A denial has a scope, and it is not the whole line.

    "No accidents reported. SALVAGE TITLE ISSUED 03/2019" is two statements.
    The first is true and about accidents; the second is the reason the buyer
    should walk. Reading the line as one denial dropped the salvage brand and
    printed nothing at all - the worst available outcome, because the buyer
    then has no reason to look at the line themselves.
    """
    assets, root = _document(tmp_path, line)
    drafts = history.title_brand_findings(assets, root)
    assert len(drafts) == 1, f"expected a finding for {line!r}"
    assert drafts[0].confidence == 1.0, f"{line!r} must ship asserted, not hedged"
    assert drafts[0].severity == "major"


@pytest.mark.parametrize("line", CELL_SEPARATOR_HEDGED)
def test_a_cell_separator_leaves_the_line_hedged_rather_than_split(
    tmp_path: Path, line: str
) -> None:
    """The price of refusing to read a pipe as a statement boundary.

    The buyer still gets the line, quoted, at reduced severity and with the copy
    saying we could not read it. The alternative - splitting the row into cells
    so this one ships at full strength - prints a major on every clean row of
    the same table, and D-017 says which of those two we take.
    """
    assets, root = _document(tmp_path, line)
    drafts = history.title_brand_findings(assets, root)
    assert len(drafts) == 1, f"expected a hedged finding for {line!r}"
    assert drafts[0].confidence == 0.5, f"{line!r} must ship hedged, not asserted"
    assert drafts[0].severity == "minor"


def test_an_answer_cannot_talk_a_stated_brand_back_out(tmp_path: Path) -> None:
    """A clause that already reports the brand does not absorb the answer after it.

    Absorbing one is how "Salvage brand; none reported" reads as the label and
    answer it is. But the same absorption applied to a clause that has already
    said "ISSUED" lets a trailing "none reported" - two words that deny nothing
    in particular - delete a salvage brand from the report entirely. A
    contradictory line is a line to hand the buyer, not one to resolve in favour
    of silence (D-017).

    Written because mutation testing found the guard unpinned: deleting it left
    all 123 tests in this file green.
    """
    assets, root = _document(tmp_path, "SALVAGE TITLE ISSUED; none reported")
    drafts = history.title_brand_findings(assets, root)
    assert len(drafts) == 1, "the trailing answer deleted a stated salvage brand"


@pytest.mark.parametrize("separator", CLAUSE_SEPARATORS)
def test_every_clause_separator_is_covered_in_both_directions(
    tmp_path: Path, separator: str
) -> None:
    """A separator that only ever upgrades is a separator nobody weighed.

    Line 1 is a label and its answer, and must stay denied. Line 2 is a denial
    of something else in front of a brand, and must assert. One line per
    direction, on the same separator, in one document - so a change that fixes
    either direction by breaking the other cannot pass.
    """
    denying = f"Salvage brand{separator} none reported"
    asserting = f"No accidents reported{separator} SALVAGE TITLE ISSUED 03/2019"
    assets, root = _document(tmp_path, f"{denying}\n{asserting}\n")
    drafts = history.title_brand_findings(assets, root)
    assert len(drafts) == 1, f"{separator!r}: {denying!r} produced a finding"
    assert drafts[0].confidence == 1.0, f"{separator!r}: {asserting!r} shipped hedged"
    assert (
        "line 2" in drafts[0].evidence[0].caption
    ), f"{separator!r}: the finding cites {denying!r}, so the denial was read as an assertion"


@pytest.mark.parametrize("line", CROWDED_STATEMENT_HEDGED)
def test_a_denial_of_something_else_cannot_delete_an_asserted_brand(
    tmp_path: Path, line: str
) -> None:
    """The silent drop, which is the worst thing this file can ship.

    "SALVAGE TITLE ISSUED 03/2019, no accidents reported" declares a salvage
    brand and denies accidents. A comma is not a clause break, so both live in
    one statement, and the scanner answered the whole line "denied" the moment
    it saw a negated assertion anywhere in it - without ever checking that the
    negation was about the brand. The wreck shipped as clean and the line was
    never printed, so the buyer had nothing to check (LAW 1, D-017).

    Hedged is what a line carrying both signals earns. What it must not earn is
    nothing.
    """
    assets, root = _document(tmp_path, line)
    drafts = history.title_brand_findings(assets, root)
    assert len(drafts) == 1, f"{line!r} asserts a brand and produced no finding at all"
    assert drafts[0].confidence == 0.5, f"{line!r} carries both signals and must ship hedged"
    assert drafts[0].severity == "minor"
    assert drafts[0].evidence[0].excerpt == line, "the buyer has to see the line to check us"


def test_a_denied_serious_brand_does_not_hide_an_asserted_lesser_one(tmp_path: Path) -> None:
    """One finding per line was one finding too few.

    BRAND_PATTERNS is ordered by seriousness, not by position, and the scan
    stopped at the first pattern that matched. So on "Salvage: none reported.
    Flood damage reported 03/2019." the salvage pattern won the line, was
    correctly denied, and produced nothing - and the flood brand asserted three
    words later was never tested. The same two sentences on two lines report the
    flood. A document warning or staying silent depending on where it wrapped is
    not a reading, it is a coin toss.
    """
    assets, root = _document(tmp_path, "Salvage: none reported. Flood damage reported 03/2019.")
    drafts = history.title_brand_findings(assets, root)
    assert len(drafts) == 1, "the denied salvage brand swallowed the asserted flood brand"
    assert drafts[0].id.startswith("title_flood")
    assert drafts[0].confidence == 1.0
    assert not any(
        "salvage" in d.id for d in drafts
    ), "the salvage brand is denied on this line and must stay unreported"


def test_scanning_on_past_a_denial_cannot_double_report_a_brand(tmp_path: Path) -> None:
    """The claim the fix above rests on, checked rather than assumed.

    Continuing past a denied match is only safe because the dedupe in
    `title_brand_findings` keys on asset and pattern, so a brand found twice is
    reported once. Assuming that is how a fix for a missing finding turns into a
    report that says the same thing twice and reads as though we cannot count.
    """
    text = (
        "Salvage: none reported. Flood damage reported 03/2019.\n"
        "Flood damage reported again 05/2019\n"
    )
    assets, root = _document(tmp_path, text)
    drafts = history.title_brand_findings(assets, root)
    assert [d.id for d in drafts] == ["title_flood_doc_01"]


@pytest.mark.parametrize("line", WIDE_LINES)
def test_the_excerpt_contains_the_keyword_the_finding_cites(tmp_path: Path, line: str) -> None:
    """The evidence has to contain the word the finding is about.

    `_excerpt` truncated at MAX_EXCERPT_CHARS counting from the START of the
    line while the keyword can sit anywhere on it, so on a wide record row - the
    ordinary shape of a real history report - the published excerpt was 240
    characters of preamble that never mentioned salvage, printed under copy
    saying the line was quoted exactly as it appears. The buyer checking our
    reading against the quote would have found nothing to check.

    Re-matching the pattern against the emitted excerpt guards both halves at
    once: the window has to be centred on the match AND it has to keep the whole
    keyword, not just the first characters of it.
    """
    assets, root = _document(tmp_path, line)
    hits = history.scan(assets, root)
    assert hits, f"{line!r} matches no BRAND_PATTERN: it proves nothing"
    for hit in hits:
        assert re.search(
            hit.pattern.pattern, hit.excerpt, flags=re.IGNORECASE
        ), f"{hit.pattern.key}: the excerpt does not contain the word the finding cites"
        assert len(hit.excerpt) <= history.MAX_EXCERPT_CHARS


@pytest.mark.parametrize("line", WIDE_LINES)
def test_a_shortened_excerpt_does_not_claim_to_be_the_whole_line(
    tmp_path: Path, line: str
) -> None:
    """A claim that nothing checks, printed under the evidence it is wrong about.

    The detail copy said "The line is quoted below exactly as it appears" on
    every finding, including the ones whose excerpt had been cut to 240
    characters. Saying so of a shortened quote is the defect class this product
    keeps finding in itself, and here it sits directly above the shortened quote.
    """
    assets, root = _document(tmp_path, line)
    drafts = history.title_brand_findings(assets, root)
    assert len(drafts) == 1
    detail = drafts[0].detail
    assert "exactly as it appears" not in detail, "a shortened quote is not the whole line"
    assert "too long to print whole" in detail, "the copy has to say what was done to the line"
    assert "..." in drafts[0].evidence[0].excerpt, "the cut has to be visible in the quote"


def test_a_line_that_fits_is_still_quoted_whole_and_says_so(tmp_path: Path) -> None:
    """The other half of the excerpt fix, which the golden report depends on.

    Every line in the demo fixture fits, so the ordinary copy has to survive the
    windowing change byte for byte - no ellipsis, no hedge about shortening, and
    the promise of a verbatim quote kept because it is true.
    """
    assets, root = _document(tmp_path, "Body shop invoice notes frame damage, repaired.")
    drafts = history.title_brand_findings(assets, root)
    assert drafts[0].evidence[0].excerpt == "Body shop invoice notes frame damage, repaired."
    assert "The line is quoted below exactly as it appears." in drafts[0].detail
    assert "too long to print whole" not in drafts[0].detail


@pytest.mark.parametrize(
    "line",
    [
        *ASSERTING,
        *DENYING,
        *ENUMERATED_ASSERTING,
        *BRAND_NAMED_WITH_A_NEGATION,
        *DENIAL_IN_ANOTHER_CLAUSE,
        *CELL_SEPARATOR_HEDGED,
        *CROWDED_STATEMENT_HEDGED,
        *WIDE_LINES,
    ],
)
def test_every_line_in_the_tables_matches_a_brand_pattern(tmp_path: Path, line: str) -> None:
    """A row that matches nothing passes for a reason that is not its name.

    'Odometer: no discrepancy reported' sat in DENYING for a session claiming to
    prove a denial was read as one. No BRAND_PATTERN matches it - the odometer
    pattern wants the two words adjacent - so it produced no hit to classify and
    could not have failed however wrong the classifier got.
    """
    assets, root = _document(tmp_path, line)
    assert history.scan(assets, root), f"{line!r} matches no BRAND_PATTERN: it proves nothing"


def test_one_statement_carrying_both_signals_ships_hedged(tmp_path: Path) -> None:
    """The premise the ranking test below rests on, checked rather than assumed.

    If this line were classified as denied instead of ambiguous, that test would
    still pass - on one finding from its second line - while proving nothing
    about ranking. It is only worth having if the hedge is real.
    """
    assets, root = _document(tmp_path, "Salvage record on file: clean title issued 2020")
    drafts = history.title_brand_findings(assets, root)
    assert len(drafts) == 1
    assert drafts[0].confidence == 0.5
    assert drafts[0].severity == "minor"


def test_a_later_outright_assertion_outranks_an_earlier_hedge(tmp_path: Path) -> None:
    """One finding per brand, at the strongest reading the document supports.

    A line carrying both a denial token and an assertion verb in one statement
    ships hedged - a salvage record on file and a clean title issued is exactly
    the muddle a keyword scanner should admit to. But when a later line asserts
    the same brand outright, keeping the hedge because it arrived first would
    soften a salvage warning to minor at half confidence, and cite the muddier
    line as the evidence.
    """
    text = "Salvage record on file: clean title issued 2020\nSalvage title issued 03/2019\n"
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
