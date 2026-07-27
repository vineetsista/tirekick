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


def _scanned_files() -> list[Path]:
    files: list[Path] = []
    for pattern in SCANNED_GLOBS:
        files.extend(sorted(REPO_ROOT.glob(pattern)))
    # The rules module names the banned phrases in order to ban them.
    return [f for f in files if f.name not in ("copy_rules.py",)]


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
