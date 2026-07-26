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
glance (LAW 1).

The failure that would actually hurt someone is the negation case. A history
report that says "Salvage: None" contains the word "salvage", and a scanner that
reported a salvage indicator there would talk a buyer out of a clean car - the
exact error ACCURACY.md names as the one that costs a good deal. So a match is
classified as asserted, denied, or ambiguous, denied matches produce nothing, and
ambiguous ones ship hedged and at lower severity. See DECISIONS.md D-017.
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
#: line reading "salvage - flood" is reported once, as salvage.
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

#: Tokens that, on the same line as a match, mean the document is denying the
#: brand rather than reporting it. "Salvage: None" is the common shape, and
#: reporting it as a salvage indicator would be a false alarm on a clean car.
_DENIAL = re.compile(
    r"\b(no|none|not|never|nil|negative|clear|clean|zero|0)\b"
    r"|\bno records? (found|reported)\b"
    r"|:\s*(n/?a|no|none)\b",
    re.IGNORECASE,
)

#: Tokens that mean the line is asserting the brand, and that outrank a stray
#: "no" elsewhere on the same line ("No. 3 - SALVAGE TITLE ISSUED").
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


def _classify(line: str) -> str:
    """Is this line reporting the brand, denying it, or unreadable either way?

    A line with no negating language at all is treated as asserting the brand.
    That is the asymmetry this function exists to get right: 'Title brand:
    SALVAGE' carries no verb, and reading it as ambiguous would soften a report
    that a buyer needs delivered at full strength. Denial has to be written down
    to count, because denial is what the clean-title case actually looks like -
    'Salvage: None' - and that shape is unmistakable.
    """
    if _NEGATED_ASSERTION.search(line):
        return "denied"
    denied = bool(_DENIAL.search(line))
    if not denied:
        return "asserted"
    if _ASSERTION.search(line):
        # Both signals on one line. We cannot tell, and picking a reading would
        # be worse than reporting that we could not.
        return "ambiguous"
    return "denied"


def _excerpt(line: str) -> str:
    cleaned = " ".join(line.split())
    if len(cleaned) <= MAX_EXCERPT_CHARS:
        return cleaned
    return cleaned[: MAX_EXCERPT_CHARS - 3] + "..."


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
                if re.search(pattern.pattern, line, flags=re.IGNORECASE):
                    hits.append(
                        BrandHit(
                            asset_id=asset.id,
                            pattern=pattern,
                            line_number=lineno,
                            excerpt=_excerpt(line),
                            stance=_classify(line),
                        )
                    )
                    # One finding per line: the first, most serious, match wins.
                    break
    return hits


def title_brand_findings(assets: list[Asset], media_root: Path) -> list[DraftFinding]:
    """Turn asserted and ambiguous hits into drafts. Denied hits produce nothing."""
    drafts: list[DraftFinding] = []
    seen: set[str] = set()

    for hit in scan(assets, media_root):
        if hit.stance == "denied":
            continue
        # One finding per brand per document, however many lines mention it.
        dedupe_key = f"{hit.asset_id}:{hit.pattern.key}"
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        ambiguous = hit.stance == "ambiguous"
        if ambiguous:
            detail = (
                f"A document you uploaded contains a line mentioning "
                f"{hit.pattern.label.lower()}, and TIREKICK could not tell whether "
                f"that line is reporting it or ruling it out - the wording carries "
                f"both. The line is quoted below exactly as it appears; read it "
                f"yourself. {hit.pattern.meaning}"
            )
            severity: Severity = "minor"
            basis = (
                "A keyword matched, and the surrounding wording contains both "
                "affirming and negating language. We are reporting that we could "
                "not read it, rather than picking an interpretation."
            )
        else:
            detail = (
                f"A document you uploaded reports {hit.pattern.label.lower()}. The "
                f"line is quoted below exactly as it appears. {hit.pattern.meaning} "
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
