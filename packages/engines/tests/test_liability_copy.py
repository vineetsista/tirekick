"""LIABILITY section 5 - the banned-language scan, run against real source files.

The scan covers the surfaces where a banned phrase would reach a buyer: the
prompts we send the model, the strings the engines emit, and the web copy. Docs
are excluded because docs discuss the banned words in order to ban them.
"""

from __future__ import annotations

from pathlib import Path

from tirekick_engines.copy_rules import scan_paths, scan_text

REPO_ROOT = Path(__file__).resolve().parents[3]

#: Directories whose text can reach a buyer.
#:
#: Prompts are in this list for the same reason the web copy is. A banned phrase
#: in a prompt does not reach the buyer directly - it teaches the model to write
#: it back to us, which is worse, because then it arrives wearing a confidence
#: score.
SCANNED_GLOBS = (
    "packages/engines/src/tirekick_engines/**/*.py",
    "packages/engines/src/tirekick_engines/prompts/**/*.md",
    "apps/web/src/**/*.tsx",
    "apps/web/src/**/*.ts",
    "packages/shared/src/constants.ts",
)


#: Files that necessarily contain banned phrases in order to forbid them.
#:
#: `copy_rules.py` declares the phrase list. Test files assert that copy does NOT
#: contain a phrase, which means writing it down. Neither is a surface a buyer can
#: reach, which is the criterion this scan is actually applying - the globs above
#: are an approximation of "text that could be read by a customer", and these are
#: where that approximation is wrong.
#:
#: This exemption is narrow on purpose. It excuses files by role, never a specific
#: sentence, so nothing product-facing can be quietly added to it.
_EXEMPT_NAMES = ("copy_rules.py",)
_EXEMPT_SUFFIXES = (".test.tsx", ".test.ts", "_test.py")


def _is_exempt(path: Path) -> bool:
    return path.name in _EXEMPT_NAMES or path.name.endswith(_EXEMPT_SUFFIXES)


def _scanned_files() -> list[Path]:
    files: list[Path] = []
    for pattern in SCANNED_GLOBS:
        files.extend(sorted(REPO_ROOT.glob(pattern)))
    return [f for f in files if not _is_exempt(f)]


def test_the_exemption_list_does_not_swallow_product_code() -> None:
    """A guard on the guard.

    The exemption is the obvious place to hide a violation - add a file, move on.
    So: it must never exempt a component, a page, or an engine module.
    """
    exempted = [f for f in REPO_ROOT.glob("apps/web/src/**/*.tsx") if _is_exempt(f)]
    for path in exempted:
        assert path.name.endswith(".test.tsx"), f"{path.name} is not a test file"

    scanned = _scanned_files()
    assert any(f.name == "page.tsx" for f in scanned), "the landing page must be scanned"
    assert any(f.name == "ReportView.tsx" for f in scanned)
    assert any(f.name == "TeaserView.tsx" for f in scanned)
    assert any(f.name == "PurchaseGate.tsx" for f in scanned)
    assert any(f.suffix == ".md" for f in scanned), "prompts must be scanned"


def test_no_banned_language_in_product_surfaces() -> None:
    files = _scanned_files()
    assert files, "the scan found no files - the globs are wrong, not the copy"

    violations = scan_paths(files)
    assert not violations, "banned language found:\n" + "\n".join(str(v) for v in violations)


def test_the_scanner_actually_catches_things() -> None:
    """A scanner that never fires is indistinguishable from no scanner."""
    caught = scan_text("This vehicle is TIREKICK certified and safe to drive.")
    matched = {v.matched.lower() for v in caught}
    assert "certified" in matched
    assert "safe to drive" in matched


def test_the_scanner_catches_a_locked_system_all_clear() -> None:
    caught = scan_text("Good news - the brakes are fine.")
    assert any("brakes are fine" in v.matched.lower() for v in caught)


def test_sanctioned_disclaimers_are_permitted() -> None:
    """Our own denials must survive, or the scan bans the disclaimer itself."""
    text = (
        "Automated analysis of media you provided. This is not an inspection, a "
        "certification, or a warranty."
    )
    assert scan_text(text) == []


def test_locked_statement_is_permitted() -> None:
    assert scan_text("Not remotely verifiable - independent mechanic required.") == []
