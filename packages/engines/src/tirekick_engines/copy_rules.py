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
        r"\bcertif(y|ied|ication)\b",
        "We certify nothing. There is no TIREKICK pass.",
        "analysis / analyzed",
    ),
    (
        r"\bguarantee(d|s)?\b",
        "We guarantee no condition, ever.",
        "visible in the provided media",
    ),
    (
        r"\bwarrant(y|ies|ed)\b",
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
        r"\bpass(ed|es) (inspection|the inspection)\b",
        "There is nothing to pass. We do not inspect.",
        "analysis complete",
    ),
    (
        r"\bwe inspected\b",
        "A person inspects. We analyze media.",
        "TIREKICK analyzed",
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


def scan_text(text: str, *, path: str = "<text>") -> list[CopyViolation]:
    cleaned = _strip_sanctioned(text)
    violations: list[CopyViolation] = []
    for lineno, line in enumerate(cleaned.splitlines(), start=1):
        for pattern, why, instead in BANNED:
            match = re.search(pattern, line, flags=re.IGNORECASE)
            if match:
                violations.append(
                    CopyViolation(
                        path=path,
                        line=lineno,
                        matched=match.group(0),
                        why=why,
                        instead=instead,
                    )
                )
    return violations


def scan_paths(paths: list[Path]) -> list[CopyViolation]:
    violations: list[CopyViolation] = []
    for path in paths:
        if not path.is_file():
            continue
        violations.extend(scan_text(path.read_text(encoding="utf-8"), path=str(path)))
    return violations
