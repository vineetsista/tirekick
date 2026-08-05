"""LIABILITY section 5 - banned language, enforced by a scan.

Certain words are things we must never say about a car: that it is certified, that
it passed, that it is safe to drive, that we inspected it. They are banned in
product copy, in report output, and in model prompts - a prompt that uses the word
"inspect" teaches the model to write it back to us.

The complication is that our own disclaimers must be able to say "this is not a
certification" - the banned word appears inside the sentence that denies it. Rather
than guess at negation with a regex, sanctioned disclaimer sentences are declared
verbatim and stripped from the text before scanning. If a disclaimer changes, this
list changes with it, deliberately and in review.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

#: (pattern, why it is banned, what to say instead)
BANNED: tuple[tuple[str, str, str], ...] = (
    (
        r"\bcertif(y|ies|ied|ying|ication|ications)\b",
        "We certify nothing. There is no TIREKICK pass.",
        "analysis / analyzed",
    ),
    (
        r"\bguarantee(d|s|ing)?\b",
        "We guarantee no condition, ever.",
        "visible in the provided media",
    ),
    (
        r"\bwarrant(y|ies|ed|ing|s)\b",
        "We offer no warranty of condition or fitness.",
        "observed / not observed",
    ),
    (
        r"\b(safe to drive|road safe|roadworthy)\b",
        "We never assert a vehicle is safe. That is the claim that hurts someone.",
        "have a mechanic verify before purchase",
    ),
    (
        r"\bclean bill of health\b",
        "Implies a clearance we cannot give.",
        "no issues visible in the media provided",
    ),
    (
        r"\bpass(ed|es) (\w+ ){0,2}inspection\b",
        "There is nothing to pass. We do not inspect.",
        "analysis complete",
    ),
    (
        r"\b(we|tirekick) inspect(s|ed|ing)?\b",
        "A person inspects. We analyze media.",
        "TIREKICK analyzed",
    ),
    (
        r"\binspected by\b",
        "Passive voice does not make it true. Nobody inspected anything.",
        "analyzed by",
    ),
    (
        r"\bno problems found\b",
        "Overclaims absence. Absence of evidence is not evidence of absence.",
        "no problems visible in the media provided",
    ),
    (
        r"\bbrakes (are|look|appear) (fine|good|ok)\b",
        "LAW 2. A locked system is never cleared.",
        "not remotely verifiable - independent mechanic required",
    ),
)

#: Exact sentences permitted to contain banned words, because they deny them.
#: Any change here is a change to the disclaimer architecture (LIABILITY section 4).
SANCTIONED_DISCLAIMERS: tuple[str, ...] = (
    "This is not an inspection, a certification, or a warranty.",
    "Not remotely verifiable - independent mechanic required.",
    "not an inspection",
    "TIREKICK cannot assess it from photos, video, or audio.",
)


@dataclass(frozen=True)
class CopyViolation:
    path: str
    line: int
    matched: str
    why: str
    instead: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.matched!r} - {self.why} Use: {self.instead}"


#: Between any two words of a sanctioned phrase, source may insert whitespace,
#: quote marks, a concatenation operator, or a line break - our own banner is
#: written across several lines in both Python and TypeScript. Matching on the
#: words rather than the formatting means the scan checks what a phrase says, not
#: how it was typed.
_JOINER = r"[\s\"'+\\`)(,]*"


def _sanctioned_patterns() -> list[re.Pattern[str]]:
    patterns = []
    for phrase in SANCTIONED_DISCLAIMERS:
        words = phrase.split()
        patterns.append(re.compile(_JOINER.join(re.escape(w) for w in words), re.IGNORECASE))
    return patterns


_SANCTIONED_RE = _sanctioned_patterns()


def _blank(match: re.Match[str]) -> str:
    """Replace a match with spaces, keeping newlines so line numbers still hold."""
    return "".join("\n" if ch == "\n" else " " for ch in match.group(0))


def _strip_sanctioned(text: str) -> str:
    for pattern in _SANCTIONED_RE:
        text = pattern.sub(_blank, text)
    return text


#: What may sit between two words of a banned phrase without breaking it.
#:
#: The mirror of `_JOINER`. The sanctioned-disclaimer stripper has always been
#: newline-tolerant, on the correct grounds that our own banner is written
#: across several lines of source - and the ban was not, so the identical
#: wrapping that the stripper anticipates was an escape hatch out of it:
#: `"This car is safe to " + "drive"` scanned as two innocent lines. A phrase
#: is what it says, not how it was typed, in both directions.
_GAP = r"[\s\"'+\\`)(,]+"


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _relaxed(pattern: str) -> re.Pattern[str]:
    """Let a banned pattern match across the whitespace and quotes of source."""
    return re.compile(pattern.replace(" ", _GAP), re.IGNORECASE)


_BANNED_RE: tuple[tuple[re.Pattern[str], str, str], ...] = tuple(
    (_relaxed(pattern), why, instead) for pattern, why, instead in BANNED
)


def scan_text(text: str, *, path: str = "<text>") -> list[CopyViolation]:
    cleaned = _strip_sanctioned(text)
    violations: list[CopyViolation] = []
    for pattern, why, instead in _BANNED_RE:
        for match in pattern.finditer(cleaned):
            violations.append(
                CopyViolation(
                    path=path,
                    line=_line_of(cleaned, match.start()),
                    matched=" ".join(match.group(0).split()),
                    why=why,
                    instead=instead,
                )
            )
    violations.sort(key=lambda v: v.line)
    return violations


def scan_paths(paths: list[Path]) -> list[CopyViolation]:
    violations: list[CopyViolation] = []
    for path in paths:
        if not path.is_file():
            continue
        violations.extend(scan_text(path.read_text(encoding="utf-8"), path=str(path)))
    return violations
