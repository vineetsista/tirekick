"""Check the laws against the build, rather than against memory.

This file exists because of a specific failure. LAW 7 has said since P0 that the
test suite includes "an e2e upload -> paid dossier test". No such test existed
until P7. Six phases were tagged with ALL GATES GREEN while a clause of one of
the seven laws was simply unmet - not disputed, not deferred with a note, just
unnoticed.

Nothing caught it because `scripts/gates.sh` encodes the checks that exist, not
the checks the laws require, and `docs/LAWS.md` is prose that nothing parses. The
laws were enforced individually - the clamp has tests, the copy scan has tests -
but the *list* of laws was never compared against the repository.

So: this reads `docs/LAWS.md`, extracts every file and test path it names, and
fails if one is missing. It cannot verify that a test is any good. It can verify
that a law which promises a mechanism is pointing at something that exists, which
is the failure that actually happened.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LAWS = REPO_ROOT / "docs" / "LAWS.md"

#: Paths named in prose that the laws depend on. Matches things that look like a
#: repo path with an extension - deliberately crude, because a clever matcher
#: that silently skipped a line would reintroduce exactly this bug. A path may
#: carry a `::test_name` qualifier (the file half is what has to exist) or a
#: bracketed Next.js route segment; the first version of this pattern allowed
#: neither, so the two laws that name `test_laws.py::...` - the truth law and
#: the safety law - were the two laws this test never looked at.
_PATH_PATTERN = re.compile(r"`([A-Za-z0-9_./\[\]-]+\.(?:py|ts|tsx|md|sh|json))(?:::[^`]+)?`")


def _named_paths() -> set[str]:
    text = LAWS.read_text(encoding="utf-8")
    return set(_PATH_PATTERN.findall(text))


def test_every_file_the_laws_name_exists() -> None:
    """A law pointing at a file that is not there is a law nobody is keeping.

    The path is checked exactly as the law wrote it. An earlier version fell
    back to matching by basename anywhere in the repository, as tolerance for
    files moving - and that tolerance let `bench/PROVENANCE.md` pass for months
    on the strength of `fixtures/PROVENANCE.md` sharing its name. A law that
    names a path is naming that path; if the file moves, the law moves with it.
    """
    named = _named_paths()
    assert named, "no paths found in LAWS.md - the pattern is wrong, not the laws"

    missing = sorted(name for name in named if not (REPO_ROOT / name).exists())
    assert not missing, "docs/LAWS.md names files that do not exist:\n  - " + "\n  - ".join(
        missing
    )


def test_law_7_names_an_end_to_end_test_and_it_exists() -> None:
    """The specific clause that went unmet for six phases.

    LAW 7: "Overlay render tests, report snapshot tests, and an e2e upload ->
    paid dossier test."
    """
    text = LAWS.read_text(encoding="utf-8")
    assert "e2e upload -> paid dossier test" in text, (
        "LAW 7 no longer names the e2e test. If the law changed, that needs an "
        "amendment entry, not a quiet edit."
    )

    e2e = REPO_ROOT / "apps" / "web" / "src" / "lib" / "flow.test.ts"
    assert e2e.is_file(), "LAW 7 requires an e2e upload -> paid dossier test"

    body = e2e.read_text(encoding="utf-8")
    # It has to actually walk the flow, not merely be named after it.
    for step in ("createInspection", "analyse", "loadTeaser", "loadReport", "issueGrant"):
        assert step in body, f"the e2e test never calls {step}"


def test_law_7_other_named_tests_exist() -> None:
    overlay = REPO_ROOT / "apps/web/src/components/Overlay.test.tsx"
    snapshot = REPO_ROOT / "apps/web/src/components/ReportView.test.tsx"
    assert overlay.is_file(), "LAW 7 requires overlay render tests"
    assert snapshot.is_file(), "LAW 7 requires report snapshot tests"


@pytest.mark.parametrize(
    ("law", "phrase"),
    [
        (1, "every finding cites"),
        (2, "never cleared"),
        (3, "user-provided"),
        (4, "precision"),
        (5, "cost"),
        (6, "accuracy"),
        (7, "anthropic_api_key"),
    ],
)
def test_each_law_is_still_present(law: int, phrase: str) -> None:
    """A law cannot be deleted quietly.

    LAWS.md has an amendment procedure. This does not enforce it - it just makes
    a silent removal fail a test, so removing one is a deliberate act.

    Each phrase has to be one the law cannot lose without losing its meaning.
    LAW 7's used to be "no", which is a substring of "not" and therefore of any
    English paragraph - a guard that could not fire. It now pins the clause with
    teeth: CI runs with no ANTHROPIC_API_KEY.
    """
    text = LAWS.read_text(encoding="utf-8").lower()
    assert f"law {law}" in text, f"LAW {law} is no longer in docs/LAWS.md"
    section = text.split(f"## law {law}")[1].split("\n## ")[0]
    assert phrase in section, f"LAW {law} no longer says anything about {phrase!r}"


def test_the_gate_script_runs_the_test_suites_the_laws_rely_on() -> None:
    """gates.sh is what CI runs. If a suite is not in it, it is not enforced.

    The e2e test lives in the web package, so `ts:test` covers it - but only
    because that gate runs the whole workspace. Pinned here so narrowing it later
    fails loudly.
    """
    import json

    gates = (REPO_ROOT / "scripts" / "gates.sh").read_text(encoding="utf-8")
    # Anchored to a live invocation at the start of a line, not a substring: the
    # fast way to disable a flaky gate is to comment its line out, and the name
    # would still be in the file.
    invoked = set(re.findall(r'^\s*gate\s+"([^"]+)"', gates, flags=re.MULTILINE))
    for required in ("py:test", "ts:test", "contract:check", "inspect:fixture"):
        assert required in invoked, f"gates.sh no longer runs {required}"

    # ts:test delegates to turbo, which fans out across the workspace. The e2e
    # test lives in apps/web, so it is enforced only if BOTH halves hold: the
    # root script fans out, and apps/web declares a test script for it to reach.
    root = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
    assert "turbo run test" in root["scripts"]["test"]

    web = json.loads((REPO_ROOT / "apps" / "web" / "package.json").read_text(encoding="utf-8"))
    assert "test" in web["scripts"], (
        "apps/web declares no test script, so turbo runs nothing there and the "
        "LAW 7 e2e test stops being enforced without anything failing"
    )


def test_the_root_scripts_match_the_gate_script() -> None:
    """The two ways to run the same check must not drift.

    `pnpm run py:types` and the py:types gate were different for three phases:
    the gate named its mypy config and the package script did not, so a developer
    running the root script got a silently non-strict typecheck.
    """
    import json

    root = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
    assert "--config-file" in root["scripts"]["py:types"], (
        "mypy discovers config from the working directory and there is no "
        "pyproject.toml at the repo root - without --config-file this is not strict"
    )
    assert "--teaser-out" in root["scripts"]["inspect:fixture"], (
        "the fixture run must emit the teaser too, or fixture:clean cannot notice "
        "the teaser going stale"
    )
