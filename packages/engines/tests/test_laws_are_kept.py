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

Then it happened again, one level down. The P9 audit found four holes *in this
file* - a path pattern blind to `::`-qualified and bracketed paths, an existence
check that fell back to matching by basename anywhere in the tree, a LAW 7
presence phrase of "no", and a gate check by substring that a commented-out gate
satisfied. Each was closed, and each fix was then asserted by a docstring saying
it had been closed.

And then it happened a third time, in that sentence. P9's version of this
paragraph said `test_the_holes_*` below fed every predicate the exact input its
hole used to pass. `grep -c 'def test_the_holes'` was 0 - no test has ever
carried that name - and two predicates, `law_section` and `named_symbols`, were
called by no case at all. A claim that nothing checks is the defect class this
project keeps finding in itself, and this file wrote one about its own
completeness.

So the completeness is now the thing that is checked, rather than the thing that
is claimed. Every predicate here is a plain function over text; every one of them
is called, below the divider, with the input its hole used to pass, usually
alongside the older and weaker version that passed it; and
`test_every_predicate_here_is_fed_the_input_its_hole_passed` walks this file's own
AST and fails if a predicate has no such case. Adding a predicate without a case
is now red.
"""

from __future__ import annotations

import ast
import fnmatch
import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LAWS = REPO_ROOT / "docs" / "LAWS.md"
GATES = REPO_ROOT / "scripts" / "gates.sh"

#: Paths named in prose that the laws depend on. Matches things that look like a
#: repo path with an extension - deliberately crude, because a clever matcher
#: that silently skipped a line would reintroduce exactly this bug. A path may
#: carry a `::symbol` qualifier (LAW 1 and LAW 2 both name one) or a bracketed
#: Next.js route segment; the pattern before P9 allowed neither, so the two laws
#: with teeth were the two laws this file never looked at.
_PATH_PATTERN = re.compile(
    r"`(?P<path>[A-Za-z0-9_./\[\]-]+\.(?:py|tsx|ts|md|sh|json))(?:::(?P<symbol>[^`]+))?`"
)

#: The pattern this file used until P9. It is not used to check anything. It is
#: kept so the harness can demonstrate that the inputs below are genuinely the
#: ones the old pattern waved through, rather than arbitrary bad strings chosen
#: to make a new check look good.
_PATTERN_BEFORE_P9 = re.compile(r"`([A-Za-z0-9_./-]+\.(?:py|ts|tsx|md|sh|json))`")

#: How this file read a module's definitions until P10: a regex over raw text.
#: It is not used to check anything. It is kept so the harness can show that the
#: prose below really did satisfy it, rather than being a bad string invented to
#: make the replacement look good.
_DEFINITION_BEFORE_P10 = re.compile(
    r"^(?:async\s+def|def|class)\s+(\w+)|^(\w+)\s*[:=]", re.MULTILINE
)


def defined_symbols(source: str) -> set[str]:
    """Names a Python module binds at its top level.

    Parsed, not matched. `_DEFINITION_BEFORE_P10` read `^(\\w+)\\s*[:=]` out of
    raw file text, and a module docstring is raw file text: a header sentence
    reading `test_safety_law_clamps_brakes: deleted in P8, see DECISIONS.md`
    bound no name and defined no test, and reported LAW 2's promise kept. The
    check written to stop a law being kept by prose was satisfiable by prose.

    Top level only. A name bound inside an `if` or a `try` is not counted, and no
    law names one - which is a claim `test_every_test_the_laws_name_by_symbol_exists`
    holds, because it runs this over the real LAWS.md and would go red.
    """
    names: set[str] = set()
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def named_paths(text: str) -> set[str]:
    """Every repository path the given prose names."""
    return {m.group("path") for m in _PATH_PATTERN.finditer(text)}


def named_symbols(text: str) -> set[tuple[str, str]]:
    """Every `path::symbol` promise, as (path, symbol-or-glob) pairs."""
    return {
        (m.group("path"), m.group("symbol"))
        for m in _PATH_PATTERN.finditer(text)
        if m.group("symbol")
    }


def missing_paths(text: str, root: Path) -> list[str]:
    """Paths the prose names that are not at that path under `root`.

    Checked exactly as the law wrote it. The version before P9 fell back to
    matching by basename anywhere in the repository, as tolerance for files
    moving - and that tolerance let `bench/PROVENANCE.md` pass on the strength of
    `fixtures/PROVENANCE.md` sharing its name. A law that names a path is naming
    that path; if the file moves, the law moves with it.
    """
    return sorted(name for name in named_paths(text) if not (root / name).exists())


def unkept_promises(text: str, root: Path) -> list[str]:
    """`file.py::symbol` promises whose file exists but defines no such symbol.

    Existence of the file is the check that was missing for six phases. Existence
    of the thing inside it is the same check one level down: `test_laws.py`
    surviving while `test_safety_law_*` is deleted from it leaves LAW 2 pointing
    at a file that no longer keeps it. Only Python is inspected, because Python is
    the only language the laws qualify with `::`.
    """
    unkept: list[str] = []
    for path, symbol in sorted(named_symbols(text)):
        target = root / path
        if target.suffix != ".py" or not target.is_file():
            continue
        defined = defined_symbols(target.read_text(encoding="utf-8"))
        if not any(fnmatch.fnmatch(name, symbol) for name in defined):
            unkept.append(f"{path}::{symbol}")
    return unkept


def _law_section_before_p9(text: str, law: int) -> str:
    """What this was until P9. Kept only so the harness can show it raising."""
    return text.lower().split(f"## law {law}")[1].split("\n## ")[0]


def law_section(text: str, law: int) -> str:
    """The body of one law: lowercased, with runs of whitespace collapsed.

    Empty when the law is not in the text. `_law_section_before_p9` raised
    IndexError instead, which is red with the wrong message - the run says `list
    index out of range` where the caller wants to say LAW 3 has been deleted.

    Whitespace is collapsed because LAWS.md is wrapped at 88 columns and the
    wrapping moves. LAW 2's clause is "never cleared\\nremotely", so a phrase
    check over the raw text could only ever pin "never cleared" - two words, and
    two words was not enough to keep this file honest the last time.
    """
    lowered = text.lower()
    marker = f"## law {law}"
    if marker not in lowered:
        return ""
    return " ".join(lowered.split(marker, 1)[1].split("\n## ", 1)[0].split())


def laws_matching(text: str, phrase: str) -> list[int]:
    """Every law whose body contains the phrase.

    A phrase that matches two laws cannot report which one is present, so it
    cannot report either one going missing. "accuracy" was LAW 6's phrase and it
    matches LAW 4 as well; "no" matched all seven.
    """
    headings = re.findall(r"^## law (\d+)", text.lower(), flags=re.MULTILINE)
    numbers = sorted({int(n) for n in headings})
    wanted = " ".join(phrase.lower().split())
    return [law for law in numbers if wanted in law_section(text, law)]


def invoked_gates(script: str) -> set[str]:
    """Gate names `scripts/gates.sh` actually invokes.

    Anchored to a live invocation at the start of a line rather than searched for
    as a substring: the fast way to disable a flaky gate is to comment its line
    out, and the name is still in the file afterwards.
    """
    return set(re.findall(r'^[ \t]*gate[ \t]+"([^"]+)"', script, flags=re.MULTILINE))


#: The line the harness starts after. Tests above it check the repository; tests
#: below it check the predicates in this file, which is a different job.
_HARNESS_DIVIDER = "# --- The holes this file had, closed and kept closed"


def harness_coverage(source: str) -> dict[str, set[str]]:
    """Every predicate a module defines, mapped to its harness tests.

    A predicate is a top-level function whose name is neither private nor a
    test. A harness test is a test defined after `_HARNESS_DIVIDER`. Calling a
    predicate from above the divider does not count: those tests read LAWS.md,
    so they exercise whatever the predicate happens to do to the current text,
    and the current text is the one input guaranteed not to have the hole in it.
    """
    if _HARNESS_DIVIDER not in source:
        raise ValueError(f"no {_HARNESS_DIVIDER!r}, so this source has no harness at all")
    first_harness_line = source[: source.index(_HARNESS_DIVIDER)].count("\n") + 1

    module = ast.parse(source)
    coverage: dict[str, set[str]] = {
        node.name: set()
        for node in module.body
        if isinstance(node, ast.FunctionDef) and not node.name.startswith(("_", "test_"))
    }
    for node in module.body:
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_"):
            continue
        if node.lineno < first_harness_line:
            continue
        called = {
            call.func.id
            for call in ast.walk(node)
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
        }
        for name in called & coverage.keys():
            coverage[name].add(node.name)
    return coverage


#: Each phrase has to be one the law cannot lose without losing its meaning.
_LAW_PHRASES = [
    (1, "every finding cites"),
    (2, "never cleared remotely"),
    (3, "no bulk marketplace scraping"),
    (4, "clears its precision threshold"),
    (5, "every run prints what it cost"),
    (6, "we never oversell it"),
    (7, "anthropic_api_key"),
]

#: Every phrase this file has ever got wrong, and the law it was pinning. Each
#: one is a single word, and a single word is what a law can keep while losing
#: the sentence the word came from: LAW 7 kept "no" through any paragraph in
#: English, and LAW 3 would have kept "user-provided" through a section that had
#: stopped saying media comes from the user.
_PHRASES_THIS_FILE_GOT_WRONG = [
    (7, "no"),
    (2, "never"),
    (3, "user-provided"),
    (4, "precision"),
    (5, "cost"),
    (6, "accuracy"),
]

#: Fewest words in a phrase that pins a clause rather than a word.
#:
#: Two would already exclude every phrase above. Three costs nothing, because
#: every law in LAWS.md states its own point in a span at least that long, and
#: `test_each_law_is_still_present` is what proves that rather than this comment.
_MIN_CLAUSE_WORDS = 3


def phrase_has_teeth(phrase: str) -> bool:
    """Whether a presence phrase is a clause rather than a word.

    The standard until P10 was "this phrase is not a substring of one decoy
    paragraph written for this file", which is circular twice over. The decoy
    was authored to contain exactly the words the self-test asserted it
    contained, and any word its author did not think of passed:
    `phrase_has_teeth("user-provided")` returned True, and "user-provided" is one
    of the phrases the check was written for.

    Length is a weaker property than "says what this law and no other law says",
    and it is the half that is not circular - nothing here judges a phrase
    against text this file wrote. The other half is `laws_matching`, judged
    against LAWS.md, which nobody wrote for this test.
    """
    words = phrase.split()
    if any("_" in word for word in words):
        # An identifier is not English and cannot land in a paragraph by
        # accident. LAW 7's clause is `ANTHROPIC_API_KEY`; padding it to three
        # words would pin the markdown around it instead of the clause.
        return True
    return len(words) >= _MIN_CLAUSE_WORDS


# --- The laws, checked against this repository --------------------------------


def test_every_file_the_laws_name_exists() -> None:
    """A law pointing at a file that is not there is a law nobody is keeping."""
    text = LAWS.read_text(encoding="utf-8")
    assert named_paths(text), "no paths found in LAWS.md - the pattern is wrong, not the laws"

    missing = missing_paths(text, REPO_ROOT)
    assert not missing, "docs/LAWS.md names files that do not exist:\n  - " + "\n  - ".join(
        missing
    )


def test_every_test_the_laws_name_by_symbol_exists() -> None:
    """LAW 1 and LAW 2 name test functions, not just test files."""
    text = LAWS.read_text(encoding="utf-8")
    promises = named_symbols(text)
    assert promises, "no `path::symbol` promises found - LAW 1 and LAW 2 both make one"

    unkept = unkept_promises(text, REPO_ROOT)
    assert not unkept, "docs/LAWS.md names tests that do not exist:\n  - " + "\n  - ".join(
        unkept
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


@pytest.mark.parametrize(("law", "phrase"), _LAW_PHRASES)
def test_each_law_is_still_present(law: int, phrase: str) -> None:
    """A law cannot be deleted quietly.

    LAWS.md has an amendment procedure. This does not enforce it - it just makes
    a silent removal fail a test, so removing one is a deliberate act.
    """
    text = LAWS.read_text(encoding="utf-8")
    section = law_section(text, law)
    assert section, f"LAW {law} is no longer in docs/LAWS.md"
    assert phrase in section, f"LAW {law} no longer says anything about {phrase!r}"


@pytest.mark.parametrize(("law", "phrase"), _LAW_PHRASES)
def test_each_presence_phrase_names_one_law_and_only_one(law: int, phrase: str) -> None:
    """The half of "has teeth" that length cannot supply.

    Judged against LAWS.md rather than against a paragraph written for this file,
    because a decoy its own author wrote is a decoy shaped like the words its
    author remembered. If a phrase matches two laws it identifies neither, and
    the one it was supposed to guard can be deleted while it still matches.
    """
    matched = laws_matching(LAWS.read_text(encoding="utf-8"), phrase)
    assert matched == [law], (
        f"{phrase!r} was meant to pin LAW {law} and appears in laws {matched} - "
        f"it cannot report LAW {law} going missing"
    )


def test_the_gate_script_runs_the_test_suites_the_laws_rely_on() -> None:
    """gates.sh is what CI runs. If a suite is not in it, it is not enforced.

    The e2e test lives in the web package, so `ts:test` covers it - but only
    because that gate runs the whole workspace. Pinned here so narrowing it later
    fails loudly.
    """
    invoked = invoked_gates(GATES.read_text(encoding="utf-8"))
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
    root = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
    assert "--config-file" in root["scripts"]["py:types"], (
        "mypy discovers config from the working directory and there is no "
        "pyproject.toml at the repo root - without --config-file this is not strict"
    )
    assert "--teaser-out" in root["scripts"]["inspect:fixture"], (
        "the fixture run must emit the teaser too, or fixture:clean cannot notice "
        "the teaser going stale"
    )


# --- The holes this file had, closed and kept closed --------------------------
#
# Everything below feeds a predicate above the exact input its P9 hole let
# through. These are not hypotheticals: `bench/PROVENANCE.md` really did pass on
# `fixtures/PROVENANCE.md`, LAW 7's phrase really was "no", and a law naming a
# `::`-qualified path really was invisible to the path pattern.


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        # LAW 1 and LAW 2 name their tests this way. Before P9 the pattern
        # required a backtick straight after the extension, so both laws - the
        # only two the file could have checked most usefully - were skipped.
        (
            "**Tested in:** `packages/engines/tests/no_such_file.py::test_truth_law_*`",
            "packages/engines/tests/no_such_file.py",
        ),
        (
            "**Enforced in code:** `packages/engines/src/tirekick_engines/gone.py::TYPES`",
            "packages/engines/src/tirekick_engines/gone.py",
        ),
        # A Next.js route segment. Neither `[` nor `]` was in the old character
        # class, so a law naming a route file was never looked at either.
        (
            "**Served by:** `apps/web/src/app/f/[inspectionId]/[...path]/gone.ts`",
            "apps/web/src/app/f/[inspectionId]/[...path]/gone.ts",
        ),
    ],
)
def test_a_qualified_or_bracketed_path_that_does_not_exist_is_caught(
    line: str, expected: str
) -> None:
    assert not _PATTERN_BEFORE_P9.findall(line), (
        "this input is only interesting if the old pattern found nothing in it - "
        "otherwise it is not the hole, it is a different string"
    )
    assert named_paths(line) == {expected}
    assert missing_paths(line, REPO_ROOT) == [expected]


def test_a_file_that_exists_only_elsewhere_by_basename_does_not_satisfy_a_law(
    tmp_path: Path,
) -> None:
    """The `bench/PROVENANCE.md` hole, reconstructed.

    LAW 3 named two provenance files. Only one existed. The basename fallback
    found the other one and reported the law kept.
    """
    (tmp_path / "fixtures").mkdir()
    (tmp_path / "fixtures" / "PROVENANCE.md").write_text("origin of a file", encoding="utf-8")

    def resolves_by_basename(name: str) -> bool:
        """What the check did before P9: any file with this name, anywhere."""
        return any(tmp_path.rglob(Path(name).name))

    assert resolves_by_basename("bench/PROVENANCE.md"), "the fallback is what let this through"
    assert missing_paths("`bench/PROVENANCE.md`", tmp_path) == ["bench/PROVENANCE.md"]
    assert missing_paths("`fixtures/PROVENANCE.md`", tmp_path) == []


def test_a_law_naming_a_test_that_was_deleted_is_caught(tmp_path: Path) -> None:
    """The file surviving is not the same as the law surviving."""
    tests = tmp_path / "packages" / "engines" / "tests"
    tests.mkdir(parents=True)
    (tests / "test_laws.py").write_text(
        "def test_truth_law_rejects_a_finding_with_no_evidence() -> None:\n    pass\n",
        encoding="utf-8",
    )

    kept = "`packages/engines/tests/test_laws.py::test_truth_law_*`"
    gone = "`packages/engines/tests/test_laws.py::test_safety_law_*`"
    assert missing_paths(gone, tmp_path) == [], "the file is there; the promise is not"
    assert unkept_promises(kept, tmp_path) == []
    assert unkept_promises(gone, tmp_path) == [
        "packages/engines/tests/test_laws.py::test_safety_law_*"
    ]


@pytest.mark.parametrize("phrase", [phrase for _, phrase in _LAW_PHRASES])
def test_every_presence_phrase_has_teeth(phrase: str) -> None:
    assert phrase_has_teeth(phrase), (
        f"{phrase!r} is a word, not a clause, so it cannot tell a law being "
        f"present from a paragraph being present"
    )


@pytest.mark.parametrize(("law", "phrase"), _PHRASES_THIS_FILE_GOT_WRONG)
def test_the_teeth_check_rejects_every_word_this_file_used(law: int, phrase: str) -> None:
    """All six, including the two the P9 self-test left out.

    That self-test parametrised ["no", "cost", "accuracy", "precision"] - the
    four the decoy paragraph happened to contain - and dropped "user-provided"
    and "never", which are the two the decoy would have let through. A self-test
    that lists the cases its subject already passes is a self-test that measures
    nothing.
    """
    assert not phrase_has_teeth(
        phrase
    ), f"{phrase!r} pinned LAW {law} and could not have failed: it is one word"


def test_a_phrase_that_appears_in_two_laws_identifies_neither() -> None:
    """LAW 6's phrase was "accuracy", and LAW 4 is where ACCURACY.md is named."""
    text = LAWS.read_text(encoding="utf-8")
    assert laws_matching(text, "accuracy") == [4, 6]
    assert len(laws_matching(text, "no")) == 7, "LAW 7's phrase matched every law"
    assert laws_matching(text, "we never oversell it") == [6]


def test_a_clause_split_across_a_wrapped_line_is_still_found() -> None:
    """Why `law_section` collapses whitespace.

    LAW 2's sentence wraps between "cleared" and "remotely", so the phrase that
    states the law is not a substring of the file. Without this, the longest
    honest phrase for the safety law was two words.
    """
    wrapped = "## LAW 2 - SAFETY-CRITICAL\n\nBrakes and steering are never cleared\nremotely.\n"
    assert "never cleared remotely" not in wrapped.lower(), "the raw text is the hole"
    assert "never cleared remotely" in law_section(wrapped, 2)
    assert laws_matching(wrapped, "never cleared remotely") == [2]


def test_a_law_that_was_deleted_yields_no_section_rather_than_an_error() -> None:
    """`law_section` was the predicate with no case of its own until P10.

    Its P9 form indexed [1] into a split that returned one element, so a deleted
    law came out as `IndexError: list index out of range` from inside a test
    named after presence. Red either way - but the run has to say which law went,
    and `laws_matching` now calls this for laws it has already found, so an
    exception here would be a crash rather than a report.
    """
    text = "## LAW 1 - TRUTH\n\nEvery finding cites its evidence.\n"
    assert "every finding cites" in law_section(text, 1)
    assert law_section(text, 3) == ""
    with pytest.raises(IndexError):
        _law_section_before_p9(text, 3)


def test_a_qualified_path_is_read_as_a_promise_about_a_symbol() -> None:
    """`named_symbols` is what makes a law point at a test rather than a file."""
    law = (
        "**Tested in:** `packages/engines/tests/test_laws.py::test_truth_law_*`\n"
        "**Enforced in code:** `packages/engines/src/tirekick_engines/safety.py`\n"
    )
    assert named_symbols(law) == {("packages/engines/tests/test_laws.py", "test_truth_law_*")}
    assert named_paths(law) == {
        "packages/engines/tests/test_laws.py",
        "packages/engines/src/tirekick_engines/safety.py",
    }


def test_a_symbol_named_only_in_a_docstring_does_not_keep_a_law(tmp_path: Path) -> None:
    """The prose hole, one level down from the file-exists hole.

    LAW 2 promises `test_laws.py::test_safety_law_*`. Delete those tests, leave
    behind a header sentence explaining where they went, and the check that reads
    definitions with `^(\\w+)\\s*[:=]` finds `test_safety_law_clamps_brakes:` in
    the docstring and reports the law kept. The guard against a law being kept by
    prose was satisfied by prose.
    """
    tests = tmp_path / "packages" / "engines" / "tests"
    tests.mkdir(parents=True)
    source = (
        '"""Law tests.\n\n'
        "test_safety_law_clamps_brakes: deleted in P8 when the fixture moved.\n"
        'See DECISIONS.md for where it went.\n"""\n\n\n'
        "def test_truth_law_rejects_a_finding_with_no_evidence() -> None:\n    pass\n"
    )
    (tests / "test_laws.py").write_text(source, encoding="utf-8")

    old = {a or b for a, b in _DEFINITION_BEFORE_P10.findall(source)}
    assert (
        "test_safety_law_clamps_brakes" in old
    ), "this input is only interesting if the old check called it a definition"
    assert defined_symbols(source) == {"test_truth_law_rejects_a_finding_with_no_evidence"}

    gone = "`packages/engines/tests/test_laws.py::test_safety_law_*`"
    assert unkept_promises(gone, tmp_path) == [
        "packages/engines/tests/test_laws.py::test_safety_law_*"
    ]


def test_a_module_level_assignment_still_keeps_a_law(tmp_path: Path) -> None:
    """The other half: LAW 2 also names `LOCKED_SYSTEMS`, which is an assignment,
    and a definition check that only saw `def` would call that law unkept."""
    engines = tmp_path / "packages" / "engines" / "src" / "tirekick_engines"
    engines.mkdir(parents=True)
    (engines / "safety.py").write_text(
        'LOCKED_SYSTEMS: tuple[str, ...] = ("brakes",)\n\n\n'
        "def apply_safety_law() -> None:\n    pass\n",
        encoding="utf-8",
    )
    promise = "`packages/engines/src/tirekick_engines/safety.py::LOCKED_SYSTEMS`"
    assert unkept_promises(promise, tmp_path) == []
    assert unkept_promises(
        "`packages/engines/src/tirekick_engines/safety.py::clear_the_brakes`", tmp_path
    ) == ["packages/engines/src/tirekick_engines/safety.py::clear_the_brakes"]


@pytest.mark.parametrize(
    "script",
    [
        '# gate "py:test"    "$PY/pytest" packages/engines -q\n',
        '#gate "py:test"    "$PY/pytest" packages/engines -q\n',
        '  # gate "py:test"    "$PY/pytest" packages/engines -q  # flaky, back soon\n',
        '# gate "ts:test"  pnpm run test\n# gate "contract:check" pnpm contract:check\n',
    ],
)
def test_a_commented_out_gate_does_not_count_as_a_gate(script: str) -> None:
    """Commenting the line out is how a gate actually gets disabled.

    The check before P9 asked whether the gate's name appeared anywhere in
    gates.sh. The name is still there afterwards - in the comment.
    """
    assert any(
        name in script for name in ("py:test", "ts:test")
    ), "a substring check passes this input, which is the whole point of it"
    assert invoked_gates(script) == set()


def test_a_live_gate_line_is_still_recognised() -> None:
    """The other half: the fix must not reject the real script's own syntax."""
    script = (
        "# --- Python engines ---\n"
        'gate "py:lint"    bash -c "ruff check packages/engines"\n'
        '  gate "ts:test"      pnpm run test\n'
    )
    assert invoked_gates(script) == {"py:lint", "ts:test"}
    assert invoked_gates(GATES.read_text(encoding="utf-8")) >= {"py:lint", "py:test"}


def test_a_predicate_with_no_case_below_the_divider_is_reported() -> None:
    """`harness_coverage` is the one that says the list above is complete."""
    source = (
        "def covered(text: str) -> str:\n    return text\n\n\n"
        "def uncovered(text: str) -> str:\n    return text\n\n\n"
        "def _private(text: str) -> str:\n    return text\n\n\n"
        f"{_HARNESS_DIVIDER}\n\n\n"
        "def test_covered() -> None:\n    assert covered('x') == 'x'\n"
    )
    assert harness_coverage(source) == {"covered": {"test_covered"}, "uncovered": set()}

    # A call from above the divider does not count. Those tests run against the
    # real LAWS.md, which is the one input certain not to contain the hole.
    above = (
        "def only(text: str) -> str:\n    return text\n\n\n"
        "def test_live() -> None:\n    assert only('x')\n\n\n"
        f"{_HARNESS_DIVIDER}\n"
    )
    assert harness_coverage(above) == {"only": set()}

    with pytest.raises(ValueError, match="harness"):
        harness_coverage("def only(text: str) -> str:\n    return text\n")


def test_every_predicate_here_is_fed_the_input_its_hole_passed() -> None:
    """The completeness claim in this file's header, checked instead of written.

    P9 closed four holes and then asserted the closures in a paragraph. The
    paragraph named `test_the_holes_*`, a family of tests this file has never
    had, and two predicates - `law_section` and `named_symbols` - were called by
    no case at all. `law_section` was the one whose fix therefore had no proof in
    the suite. Adding a predicate and forgetting its case is the same mistake
    with a different name, so it is this that fails now, not a reviewer's memory.
    """
    coverage = harness_coverage(Path(__file__).read_text(encoding="utf-8"))
    assert len(coverage) >= 8, "predicates went missing, which is not what this checks"

    uncovered = sorted(name for name, tests in coverage.items() if not tests)
    assert not uncovered, (
        "these predicates are checked only against the current LAWS.md, so "
        "nothing here proves their hole is closed:\n  - " + "\n  - ".join(uncovered)
    )
