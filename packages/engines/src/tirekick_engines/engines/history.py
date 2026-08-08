"""History-document engine - title-brand keyword checks.

What this is: a keyword scan over documents the buyer uploaded themselves.

What this is not, and the report says so in as many words: a title search.
TIREKICK queries no title registry. NMVTIS, the federal title database, is not
openly queryable, and the commercial history reports that sit on top of it are
licensed products we do not resell. So the honest description of this engine is
that it reads the buyer's own paperwork closely and points at the lines that
matter - the job of a careful friend, not of a database.

That framing decides the whole design. Because we are quoting the buyer's
document back at them, the excerpt is the finding: every hit renders the line it
came from, verbatim, so the buyer checks our reading against the source in one
glance (LAW 1). A line too wide to print whole is quoted as a window around the
keyword instead, and then the copy says so - for a while it did not, and a
finding about salvage shipped over 240 characters of preamble that never used
the word, under a sentence promising the line exactly as it appears.

The failure that would actually hurt someone is the negation case. A history
report that says "Salvage: None" contains the word "salvage", and a scanner that
reported a salvage indicator there would talk a buyer out of a clean car - the
exact error ACCURACY.md names as the one that costs a good deal. So a match is
classified as asserted, denied, or ambiguous, denied matches produce nothing, and
ambiguous ones ship hedged and at lower severity. See DECISIONS.md D-017.

The mirror of that failure took nine phases to find, and it is worse, because it
is the one nobody can catch by reading the report: a denial we invent out of a
word that was not denying anything. "No. 3 - SALVAGE TITLE ISSUED" is a numbered
row, "NOT ACTUAL MILEAGE" is the name of an odometer brand, and "No accidents
reported. Salvage title issued" denies accidents only. Each read as a denial, and
each answered a document announcing a branded title with an empty page. The three
guards against that are _ENUMERATION, _NAMED_WITH_A_NEGATION and _CLAUSE_BREAK,
and every one of them was written after a line a real report prints came out
classified as the opposite of what it says.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ..models import Asset, DocumentExcerptEvidence, DraftFinding, Severity, SystemKey

#: Extensions we can read as text in P1. A scanned PDF or a photograph of a title
#: is an OCR problem, and OCR is P2 - until then an unreadable document is
#: reported as unread rather than quietly skipped.
READABLE_SUFFIXES = frozenset({".txt", ".md", ".text"})

#: Longest line we will quote back. Long enough for a full record row, short
#: enough that the evidence stays readable next to the claim.
MAX_EXCERPT_CHARS = 240


@dataclass(frozen=True)
class BrandPattern:
    key: str
    label: str
    pattern: str
    system: SystemKey
    severity: Severity
    #: What it would mean if the document really is asserting this.
    meaning: str


#: Ordered most-serious first; the first pattern to match a line wins it, so a
#: line reading "salvage - flood" is reported once, as salvage. Winning it only
#: ends the line when the winner has something to say: this order is by
#: seriousness and not by position, so a denied salvage brand used to take a
#: flood brand asserted later on the same line down with it.
BRAND_PATTERNS: tuple[BrandPattern, ...] = (
    BrandPattern(
        "junk",
        "Junk or non-repairable",
        r"\b(junk(ed)?|non[- ]?repairable|certificate of destruction)\b",
        "documentation",
        "major",
        "The vehicle was declared unfit to return to the road. In most states a "
        "junk or non-repairable title can never be retitled for road use.",
    ),
    BrandPattern(
        "salvage",
        "Salvage title",
        r"\bsalvage\b",
        "documentation",
        "major",
        "An insurer declared the vehicle a total loss. A salvage brand stays on "
        "the title for life and typically cuts resale value by a third or more.",
    ),
    BrandPattern(
        "rebuilt",
        "Rebuilt or reconstructed title",
        r"\b(rebuilt|reconstructed|prior salvage)\b",
        "documentation",
        "major",
        "The vehicle was totalled and repaired. The repair quality is exactly "
        "what a pre-purchase inspection exists to judge.",
    ),
    BrandPattern(
        "flood",
        "Flood or water damage",
        r"\b(flood(ed)?|water damage)\b",
        "documentation",
        "major",
        "Water reaches wiring and modules and the faults surface months later. "
        "Flood cars are routinely retitled across state lines to shed the brand.",
    ),
    BrandPattern(
        "fire",
        "Fire damage",
        r"\bfire damage[d]?\b",
        "documentation",
        "major",
        "Heat damage to wiring and structure is frequently not visible once the "
        "panels are back on.",
    ),
    BrandPattern(
        "lemon",
        "Lemon law buyback",
        r"\b(lemon law|manufacturer buyback|lemon buyback)\b",
        "documentation",
        "major",
        "The manufacturer repurchased the vehicle after failing to fix a defect. "
        "Ask which defect, and whether it was ever resolved.",
    ),
    BrandPattern(
        "odometer",
        "Odometer discrepancy",
        r"\b(odometer (rollback|discrepancy|tamper\w*)|not actual mileage|"
        r"exceeds mechanical limits|mileage inconsistent)\b",
        "documentation",
        "major",
        "The recorded mileage is not trusted. Every wear-based judgment about "
        "this car, including ours, rests on a number that is in dispute.",
    ),
    BrandPattern(
        "total_loss",
        "Total loss record",
        r"\b(total loss|totall?ed)\b",
        "documentation",
        "major",
        "An insurer decided repair would cost more than the vehicle was worth.",
    ),
    BrandPattern(
        # Routed at a locked system on purpose. LAW 2 converts this to a mechanic
        # referral: we can raise the alarm, we cannot grade the repair.
        "structural",
        "Frame or structural damage",
        r"\b(frame damage|structural damage|unibody damage|frame (is )?bent)\b",
        "structure",
        "major",
        "Structural repair quality cannot be assessed from paperwork or from " "photographs.",
    ),
    BrandPattern(
        "theft",
        "Theft recovery",
        r"\b(theft recover\w*|recovered theft|stolen[- ]recovered)\b",
        "documentation",
        "minor",
        "Often harmless, occasionally hides a stripped-and-rebuilt interior.",
    ),
    BrandPattern(
        "hail",
        "Hail damage",
        r"\bhail damage[d]?\b",
        "documentation",
        "minor",
        "Usually cosmetic, and usually reflected in the price already.",
    ),
)

#: A row number wearing a denial's clothes. Real reports number their rows -
#: "No. 3 - SALVAGE TITLE ISSUED", "Record No 4", "Stock No 44" - and every one
#: of those "No"s abbreviates "number". Reading one as a denial drops an
#: asserted brand in silence, which is the error a buyer cannot recover from:
#: they never see the line, so they never get the chance to check our reading.
#:
#: The rule is stated once, here, and applied by blanking the label out before
#: the line is classified - not by a lookahead copied into each denial pattern.
#: The first version of the fix was that lookahead, and it only ever guarded
#: the spelling with a period; "Record No 4" went on reading as a denial.
#:
#: A bare "No 5" is deliberately not enumeration. "No 2019-2023 salvage records
#: found" has the identical shape and is a denial, nothing in the text tells
#: them apart, and we would rather refuse the guess: a row number is printed
#: with its period or with a label in front of it, and both are matched here.
_ENUMERATION = re.compile(
    r"\b(?:record|item|stock|entry|line|ref|seq)\s+nos?\b\.?\s*\d+\b|\bnos?\b\.\s*\d+\b",
    re.IGNORECASE,
)

#: A brand whose own name is spelled with a negation word. "NOT ACTUAL MILEAGE"
#: is the federal odometer brand and appears in exactly those words on the
#: title, so its "not" denies nothing - it is the name of the thing. Until this
#: existed the odometer brand was unreportable in its canonical wording, which
#: is the wording a buyer photographs, and the scanner answered a document
#: saying the mileage is false by saying nothing at all.
_NAMED_WITH_A_NEGATION = re.compile(r"\bnot actual mileage\b", re.IGNORECASE)

#: Where one statement on a line ends and the next begins. A denial has a scope
#: and it is not the whole line: "No accidents reported. SALVAGE TITLE ISSUED
#: 03/2019" denies accidents and reports salvage, and reading it as one denial
#: threw the salvage brand away.
#:
#: A PIPE IS NOT ON THIS LIST, and that is the whole of what P10 learned here.
#: A cell separator was added to it for one session, on the reasoning that a
#: table row holds two statements. Nothing tells a cell apart from a sentence
#: except what the cells say, so every clean row of every markdown history
#: report - "| Salvage | None reported |" - split into a bare label and an
#: answer about nothing, and shipped as a major at confidence 1.0 with its own
#: denial quoted underneath as the evidence. It bought one contrived row full
#: strength and cost a whole layout a false alarm. D-017 says which direction to
#: be wrong in, and it is not that one.
#:
#: The lookbehind keeps dot-leader rows in one piece: "Salvage brand .......
#: None reported" must not split at its leader. It tests for a preceding DOT
#: rather than for any preceding whitespace, because `_blank` below replaces a
#: masked span with spaces - so a lookbehind that refused to split after
#: whitespace was disarmed by our own masking, and "Odometer: NOT ACTUAL
#: MILEAGE. No accidents reported" became one statement whose trailing denial
#: swallowed the odometer brand.
_CLAUSE_BREAK = re.compile(r"(?<!\.)[.;]\s+")

#: Words a bare answer is made of. Everything else in a clause is a subject, and
#: a clause with a subject of its own is a statement of its own.
#:
#: This is the distinction that lets "." and ";" be statement boundaries without
#: turning "Salvage brand; none reported" into a bare label. "None reported" says
#: nothing that is not an answer, so it answers the label in front of it;
#: "No accidents reported" is about accidents, and denies the brand nothing.
_ANSWER_WORDS = frozenset(
    """
    no none not never nil negative zero clear clean na n a yes true
    reported recorded found issued declared branded applied stamped
    disclosed indicated on file record records
    """.split()
)

#: Tokens that, on the same statement as a match, mean the document is denying
#: the brand rather than reporting it. "Salvage: None" is the common shape, and
#: reporting it as a salvage indicator would be a false alarm on a clean car.
#:
#: "N/A" counts wherever it appears, not only after a colon. The colon-anchored
#: form missed "Salvage ......... N/A" - the same answer in the layout most
#: reports actually use - and read it as an asserted salvage brand.
#:
#: Words that only look like denials are blanked before this runs; see
#: _ENUMERATION and _NAMED_WITH_A_NEGATION.
_DENIAL = re.compile(
    r"\b(no|none|not|never|nil|negative|clear|clean|zero|0)\b"
    r"|\bno records? (found|reported)\b"
    r"|\bn/a\b"
    r"|:\s*(n/?a|no|none)\b",
    re.IGNORECASE,
)

#: Tokens that mean the statement is asserting the brand. In a statement that
#: also carries a denial token, these demote the denial to ambiguous: both
#: signals are present, and picking one would be a guess.
_ASSERTION = re.compile(
    r"\b(issued|reported|declared|branded|recorded|applied|stamped|yes|true)\b",
    re.IGNORECASE,
)

#: A denial that is spelled with an assertion verb inside it: "None reported",
#: "No records found", "Not declared". This is how a clean history report
#: actually reads, and it contains both signals, so it has to be recognised as a
#: unit before either one is counted separately. Without this the commonest
#: phrasing of good news reads as ambiguous - which is how the first version of
#: this scanner put a salvage indicator on a clean fixture.
_NEGATED_ASSERTION = re.compile(
    r"\b(no|none|not|never|nil|zero)\b[^\n]{0,20}?"
    r"\b(reported|recorded|found|issued|declared|branded|applied|stamped|"
    r"disclosed|indicated)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class BrandHit:
    asset_id: str
    pattern: BrandPattern
    line_number: int
    excerpt: str
    #: "asserted", "denied", or "ambiguous".
    stance: str
    #: Whether `excerpt` is the whole line or a window cut out of it. The copy
    #: downstream promises a verbatim quote, and that promise has to be checked
    #: against what we actually printed rather than assumed.
    truncated: bool


def _blank(match: re.Match[str]) -> str:
    """Spaces of the same width, so every other offset stays where it was.

    `brand_at` below is an index into the original line. Replacing a span with
    a shorter one would slide the brand keyword out from under it.
    """
    return " " * (match.end() - match.start())


def _is_bare_answer(clause: str) -> bool:
    """Does this clause say anything that is not an answer?

    "None reported" does not, so it belongs to whatever label precedes it.
    "No accidents reported" does - it is about accidents - so it is a statement
    of its own and denies the brand next door nothing.
    """
    words = re.findall(r"[a-z]+", clause.lower())
    return bool(words) and all(word in _ANSWER_WORDS for word in words)


def _is_bare_label(clause: str) -> bool:
    """A clause that is waiting for an answer: no verb of its own, no denial.

    Only such a clause absorbs the answer after it. Without this guard an
    already-asserted brand could be talked back out of the report by whatever
    happened to follow it on the line.
    """
    return not _ASSERTION.search(clause) and not _DENIAL.search(clause)


def _statement_around(line: str, index: int) -> str:
    """The one statement on this line that the character at `index` belongs to.

    Plus the answer to it, if the next clause is nothing but an answer. A row
    printed "Salvage brand; none reported" is a label and its answer however it
    is punctuated, and reading the label alone reports a salvage brand on a car
    whose paperwork denies one in the next three words.
    """
    spans: list[tuple[int, int]] = []
    start = 0
    for brk in _CLAUSE_BREAK.finditer(line):
        spans.append((start, brk.start()))
        start = brk.end()
    spans.append((start, len(line)))

    at = next((i for i, (_, stop) in enumerate(spans) if index < stop), len(spans) - 1)
    statement = line[spans[at][0] : spans[at][1]]
    if not _is_bare_label(statement):
        return statement

    for nxt_start, nxt_stop in spans[at + 1 :]:
        clause = line[nxt_start:nxt_stop]
        if not _is_bare_answer(clause):
            break
        statement = f"{statement} {clause}"
    return statement


def _classify(line: str, brand_at: int) -> str:
    """Is this brand being reported, denied, or written down unreadably?

    A statement with no negating language at all is treated as asserting the
    brand. That is the asymmetry this function exists to get right: 'Title
    brand: SALVAGE' carries no verb, and reading it as ambiguous would soften a
    report that a buyer needs delivered at full strength. Denial has to be
    written down to count, because denial is what the clean-title case actually
    looks like - 'Salvage: None' - and that shape is unmistakable.

    Three things happen before any of that, and all of them exist because a
    word that looks like a denial is not always denying anything. Enumeration
    labels and brand names spelled with a negation are blanked out; then only
    the statement carrying the brand keyword is read, because a denial in the
    clause next door is about whatever that clause is about; then the denial
    inside that statement is blanked in its turn, because a denial about
    accidents shares a statement with a salvage brand every time the line is
    joined by a comma. Each of the four steps was added after a line a real
    report would print classified as the opposite of what it says.
    """
    neutral = _NAMED_WITH_A_NEGATION.sub(_blank, _ENUMERATION.sub(_blank, line))
    statement = _statement_around(neutral, brand_at)

    # A negated assertion is read as a unit and then taken OUT of the statement,
    # the way the two lookalike guards above are, because "denies something"
    # and "denies the brand" are not the same claim and this function used to
    # confuse them. It returned "denied" the moment _NEGATED_ASSERTION matched
    # anywhere in the statement, with no check on what was being denied - and a
    # comma, a dash and a table pipe are not clause breaks, so the denial had
    # the whole line to work with. "SALVAGE TITLE ISSUED 03/2019, no accidents
    # reported" came out denied: a car whose own paperwork declares salvage
    # produced no finding, and the line was never printed, so the buyer had
    # nothing to check. That is the silent drop, and D-017 says it is worse than
    # the false alarm P10 spent itself fixing.
    #
    # So: blank the denial and read what is left standing. Something still
    # asserting there means both signals are on the line and we say so; nothing
    # left means the denial was the whole of it, whatever else it mentioned.
    remainder, negations = _NEGATED_ASSERTION.subn(_blank, statement)
    if negations:
        return "ambiguous" if _ASSERTION.search(remainder) else "denied"

    denied = bool(_DENIAL.search(statement))
    if not denied:
        return "asserted"
    if _ASSERTION.search(statement):
        # Both signals in one statement. We cannot tell, and picking a reading
        # would be worse than reporting that we could not.
        return "ambiguous"
    return "denied"


#: Room kept for the two ellipses, so a windowed quote still fits the budget.
_ELLIPSIS = "..."


def _collapse(line: str) -> tuple[str, list[int]]:
    """The line with its runs of whitespace squeezed to one space, plus a map.

    The map answers "where did the character at index i end up", and it exists
    because the brand keyword's offset is an index into the RAW line while the
    window below is cut out of the squeezed one. A dot-leader row - "Salvage
    ........ N/A" is the tame version, a real report indents and pads far worse
    - moves the keyword by however many spaces were collapsed in front of it,
    and a window centred on the raw offset would drift off the word it is
    supposed to be showing.
    """
    out: list[str] = []
    where: list[int] = []
    for char in line:
        if char.isspace():
            where.append(max(len(out) - 1, 0))
            if out and out[-1] != " ":
                out.append(" ")
        else:
            where.append(len(out))
            out.append(char)
    while out and out[-1] == " ":
        out.pop()
    return "".join(out), where


def _excerpt(line: str, brand_at: int) -> tuple[str, bool]:
    """The line as the buyer will see it, and whether we had to cut it.

    The window is centred on the keyword the finding cites. It used to be cut
    from the start of the line instead, which is fine for a sentence and wrong
    for a record row: real history reports print one wide single-line row per
    event, and past character 240 the published evidence did not contain the
    word the finding was about. The buyer who did the one thing LAW 1 asks of
    them - read the quote and check our reading - found 240 characters of
    preamble and no salvage in it, underneath copy promising the line exactly as
    it appears. A quote that omits the point is not evidence, it is furniture.

    The caller is told when a cut happened, because that promise then has to be
    withdrawn rather than left standing over a shortened quote.
    """
    cleaned, where = _collapse(line)
    if len(cleaned) <= MAX_EXCERPT_CHARS:
        return cleaned, False

    budget = MAX_EXCERPT_CHARS - 2 * len(_ELLIPSIS)
    at = where[brand_at] if 0 <= brand_at < len(where) else 0
    stop = min(len(cleaned), max(at + budget // 2, budget))
    start = max(0, stop - budget)
    window = cleaned[start:stop]
    if start > 0:
        window = _ELLIPSIS + window
    if stop < len(cleaned):
        window = window + _ELLIPSIS
    return window, True


def readable_documents(assets: list[Asset], media_root: Path) -> list[tuple[Asset, str]]:
    """Document assets we can actually read as text, with their contents."""
    out: list[tuple[Asset, str]] = []
    for asset in assets:
        if asset.kind != "document":
            continue
        path = media_root / asset.path
        if path.suffix.lower() not in READABLE_SUFFIXES or not path.is_file():
            continue
        out.append((asset, path.read_text(encoding="utf-8", errors="replace")))
    return out


def scan(assets: list[Asset], media_root: Path) -> list[BrandHit]:
    """Every brand keyword hit across every readable document, classified."""
    hits: list[BrandHit] = []
    for asset, text in readable_documents(assets, media_root):
        for lineno, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            for pattern in BRAND_PATTERNS:
                match = re.search(pattern.pattern, line, flags=re.IGNORECASE)
                if not match:
                    continue
                excerpt, truncated = _excerpt(line, match.start())
                stance = _classify(line, match.start())
                hits.append(
                    BrandHit(
                        asset_id=asset.id,
                        pattern=pattern,
                        line_number=lineno,
                        excerpt=excerpt,
                        # Where the keyword sits decides which statement on the
                        # line is read, and now also which part of the line is
                        # quoted back - LAW 1, the buyer checks our reading, so
                        # the quote has to contain what we read.
                        stance=stance,
                        truncated=truncated,
                    )
                )
                if stance != "denied":
                    # The most serious match on the line wins it, but only if it
                    # produced something the buyer will see. BRAND_PATTERNS is
                    # ordered by seriousness and not by position, so stopping at
                    # the first match full stop meant a correctly DENIED salvage
                    # brand took the line with it: "Salvage: none reported.
                    # Flood damage reported 03/2019." reported nothing, while
                    # the same two sentences on two lines reported the flood. A
                    # document that warns or stays silent depending on where it
                    # wrapped is not reading the document at all.
                    break
    return hits


def title_brand_findings(assets: list[Asset], media_root: Path) -> list[DraftFinding]:
    """Turn asserted and ambiguous hits into drafts. Denied hits produce nothing."""
    # One finding per brand per document, however many lines mention it - and
    # the strongest reading wins the finding. A document can hedge on line 3
    # and assert outright on line 40; shipping the hedge because it came first
    # would soften a salvage warning to minor at half confidence, and cite the
    # muddier line as the evidence. Within a stance, the earliest line keeps
    # the citation.
    strongest: dict[str, BrandHit] = {}
    order: list[str] = []
    for hit in scan(assets, media_root):
        if hit.stance == "denied":
            continue
        dedupe_key = f"{hit.asset_id}:{hit.pattern.key}"
        if dedupe_key not in strongest:
            strongest[dedupe_key] = hit
            order.append(dedupe_key)
        elif strongest[dedupe_key].stance == "ambiguous" and hit.stance == "asserted":
            strongest[dedupe_key] = hit

    drafts: list[DraftFinding] = []
    for dedupe_key in order:
        hit = strongest[dedupe_key]
        # What we can honestly say about the quote underneath. "Exactly as it
        # appears" was printed over every finding including the ones whose
        # excerpt had been cut, which is this product's own recurring defect -
        # a claim that nothing checks - sitting directly above the evidence it
        # was wrong about.
        quoting = (
            "The line is too long to print whole, so the quote below is a window "
            "around the words that matched and the ... marks where it was cut"
            if hit.truncated
            else "The line is quoted below exactly as it appears"
        )
        ambiguous = hit.stance == "ambiguous"
        if ambiguous:
            detail = (
                f"A document you uploaded contains a line mentioning "
                f"{hit.pattern.label.lower()}, and TIREKICK could not tell whether "
                f"that line is reporting it or ruling it out - the wording carries "
                f"both. {quoting}; read it yourself. {hit.pattern.meaning}"
            )
            severity: Severity = "minor"
            basis = (
                "A keyword matched, and the surrounding wording contains both "
                "affirming and negating language. We are reporting that we could "
                "not read it, rather than picking an interpretation."
            )
        else:
            detail = (
                f"A document you uploaded reports {hit.pattern.label.lower()}. "
                f"{quoting}. {hit.pattern.meaning} "
                f"TIREKICK did not query any title registry - this is a reading of "
                f"your own paperwork, and paperwork can be incomplete or forged. "
                f"Confirm the brand with your state's motor vehicle agency before "
                f"you buy, and price the car as branded until you have."
            )
            severity = hit.pattern.severity
            basis = (
                "Exact text matching against the document you provided, not a "
                "model judgment. What is certain is that the quoted line appears "
                "in your document. Whether the document is complete, current, or "
                "genuine is not something TIREKICK can check."
            )

        drafts.append(
            DraftFinding(
                id=f"title_{hit.pattern.key}_{hit.asset_id}",
                type="title_brand_indicator",
                system=hit.pattern.system,
                title=(
                    f"{hit.pattern.label} mentioned in your documents"
                    if ambiguous
                    else f"{hit.pattern.label} reported in your documents"
                ),
                detail=detail,
                severity=severity,
                confidence=1.0 if not ambiguous else 0.5,
                confidence_basis=basis,
                evidence=[
                    DocumentExcerptEvidence(
                        asset_id=hit.asset_id,
                        excerpt=hit.excerpt,
                        caption=f"{hit.asset_id}, line {hit.line_number}",
                    )
                ],
                seller_question=(
                    f"My paperwork mentions {hit.pattern.label.lower()}. Can you "
                    f"walk me through what happened, and show me the title itself?"
                ),
                mechanic_check=(
                    "Tell the mechanic what the paperwork says before the "
                    "inspection - it changes what they look at first."
                ),
                engine="data",
            )
        )

    return drafts
