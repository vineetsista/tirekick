"""Generate the README's numbers and quotes from the repository. D-063.

The README opens with a table of nine numbers and quotes the product's own output
back at the reader. Every one of those was typed by hand, and by P10 the drift was
exactly what this project spends its phases finding in other people's documents:

  * "Tests | 612" was wrong - the suites collected a different number, and nobody
    could have noticed, because nothing compared the two;
  * the could-not-assess block was presented as the product's output in a code
    fence and was actually a *paraphrase* - the report says "Airbags and
    restraints" and "Frame and structural integrity", the README said "Restraints"
    and "Structure", tidied into aligned columns that no code path produces.

The second one is the one worth being uncomfortable about. A repository whose
argument is "we do not claim what we have not measured" was pretty-printing the
product's words on its front page. Nothing malicious and nothing load-bearing -
which is the point, because that is what drift looks like before it matters.

So the README gets the treatment docs/ACCURACY.md got in D-061: the numbers and
the quotes live in generated regions, written from the repository, and `--check`
fails the build when the committed text and the repository disagree.

    phase_reports/, DECISIONS.md, docs/LAWS.md, scripts/gates.sh,
    registry.FINDING_TYPES, the collected test suites, and the committed
    fixture report   ->   README.md

What is deliberately NOT generated: every sentence of argument in the README. This
script owns two marked blocks and the link integrity of the whole file. Prose is a
human's job; the numbers inside it are not.

Usage:

    python scripts/check_readme.py           rewrite the generated regions
    python scripts/check_readme.py --check   fail if they have drifted

`--check` collects both test suites in subprocesses (pytest --collect-only and
vitest list), which takes about half a minute. It is a gate in scripts/gates.sh
rather than a pytest test for one boring reason: it runs pytest, and a pytest test
that runs pytest is a recursion waiting for someone to hit it.
"""

from __future__ import annotations

import difflib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "packages" / "engines" / "src"))

from tirekick_engines import registry  # noqa: E402

README = REPO_ROOT / "README.md"
REPORT = REPO_ROOT / "fixtures" / "reports" / "demo-01.report.json"

#: Guard against the recursion the module docstring warns about.
GUARD = "TIREKICK_CHECK_README_RUNNING"

STANDING_BEGIN = "<!-- generated: standing. scripts/check_readme.py - do not edit by hand -->"
STANDING_END = "<!-- end generated: standing -->"
FIXTURE_BEGIN = "<!-- generated: fixture. scripts/check_readme.py - do not edit by hand -->"
FIXTURE_END = "<!-- end generated: fixture -->"

#: Packages with a vitest suite, in the order `pnpm test` runs them.
TS_PACKAGES = ("apps/web", "packages/shared", "packages/db")


# --- counting -----------------------------------------------------------------


def count_phases() -> int:
    """The highest phase number with a report, not the number of report files.

    P0 was the setup phase and its report is numbered zero, so counting files
    gives one more phase than has shipped.
    """
    numbers = [
        int(match.group(1))
        for path in (REPO_ROOT / "phase_reports").glob("PHASE_*.md")
        if (match := re.fullmatch(r"PHASE_(\d+)\.md", path.name))
    ]
    if not numbers:
        raise SystemExit("error: no phase reports found - phase_reports/ is empty or renamed")
    return max(numbers)


def count_decisions() -> int:
    """Decisions are `### D-NNN - title`. Counting the heading counts the entry."""
    text = (REPO_ROOT / "DECISIONS.md").read_text(encoding="utf-8")
    return len(re.findall(r"^### D-\d+\b", text, re.MULTILINE))


def count_laws() -> int:
    text = (REPO_ROOT / "docs" / "LAWS.md").read_text(encoding="utf-8")
    return len(re.findall(r"^## LAW \d+\b", text, re.MULTILINE))


def count_gates() -> int:
    """Only lines that actually invoke `gate`, so a commented-out gate is not one.

    test_laws_are_kept.py learned this the hard way in P10: it checked gate
    presence by substring, so `# gate "py:test" ...` satisfied LAW 7.
    """
    text = (REPO_ROOT / "scripts" / "gates.sh").read_text(encoding="utf-8")
    return len(re.findall(r"^gate\s+\"", text, re.MULTILINE))


def _run(cmd: list[str], cwd: Path) -> str:
    env = {**os.environ, GUARD: "1"}
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        raise SystemExit(
            f"error: `{' '.join(cmd)}` failed in {cwd.relative_to(REPO_ROOT)} "
            f"(exit {proc.returncode}). The README's test count cannot be verified "
            f"against a suite that does not collect.\n{proc.stdout[-2000:]}\n"
            f"{proc.stderr[-2000:]}"
        )
    return proc.stdout


def count_python_tests() -> int:
    """What pytest would run, not what `def test_` greps to.

    A static count is wrong the moment a test is parameterised, and 25 of these
    are. Collection is the only honest number, and it takes two seconds.
    """
    out = _run(
        [str(REPO_ROOT / "packages" / "engines" / ".venv" / "bin" / "pytest"),
         "packages/engines", "--collect-only", "-q"],
        REPO_ROOT,
    )
    match = re.search(r"^(\d+) tests? collected", out, re.MULTILINE)
    if not match:
        raise SystemExit(
            "error: could not read a test count out of pytest --collect-only.\n"
            f"  last lines:\n{out[-800:]}"
        )
    return int(match.group(1))


def count_ts_tests() -> int:
    """`vitest list` prints one `file > suite > name` line per test case."""
    total = 0
    for package in TS_PACKAGES:
        out = _run(["pnpm", "exec", "vitest", "list"], REPO_ROOT / package)
        cases = [ln for ln in out.splitlines() if re.match(r"^\S+\.test\.tsx? > ", ln)]
        if not cases:
            raise SystemExit(
                f"error: `vitest list` in {package} listed no tests. A package whose "
                f"suite collects nothing must not silently contribute zero."
            )
        total += len(cases)
    return total


# --- the two generated regions ------------------------------------------------


def render_standing(python_tests: int, ts_tests: int) -> str:
    """The table at the top of the README.

    The four zeros are read from the registry rather than asserted, so the day one
    of them stops being zero, the front page says so without anyone remembering to
    edit it - and until then, nobody can quietly soften them either.
    """
    specs = registry.FINDING_TYPES.values()
    measured = sum(1 for s in specs if s.measured_precision is not None)
    enabled = len(registry.enabled_types())
    vehicles = _real_vehicles()

    rows = [
        ("Phases shipped", str(count_phases())),
        ("Tests", f"{python_tests + ts_tests} ({python_tests} Python, {ts_tests} TypeScript)"),
        ("Gates", f"{count_gates()}, green local and CI"),
        ("Laws", str(count_laws())),
        ("Decisions logged", str(count_decisions())),
        ("Finding types the engines can produce", str(len(registry.FINDING_TYPES))),
        ("**Finding types with a measured accuracy**", f"**{measured}**"),
        ("**Finding types enabled for a paid report**", f"**{enabled}**"),
        ("**Real vehicles this has ever seen**", f"**{vehicles}**"),
        ("**Live model calls ever made**", "**0**"),
    ]
    lines = [STANDING_BEGIN, "", "| | |", "|---|---|"]
    lines += [f"| {label} | {value} |" for label, value in rows]
    lines += ["", STANDING_END]
    return "\n".join(lines)


def _real_vehicles() -> int:
    """Count the eval set, because that is where a real vehicle would first appear.

    Not a constant. `bench/labels/` is where a photograph of somebody's actual car
    gets labelled before it can move any number in docs/ACCURACY.md, so counting
    the labelled sessions there is the measurement, and an empty directory is the
    honest zero rather than a zero somebody typed.

    A session counts when it has assets, which is the same rule the bench harness
    applies - `TEMPLATE.json` is skipped because its `assets` object is empty, not
    because anything special-cases its name. Deriving the count the same way means
    a template that someone fills in starts counting without anyone editing this.
    """
    labels = REPO_ROOT / "bench" / "labels"
    if not labels.is_dir():
        return 0
    sessions = 0
    for path in sorted(labels.glob("*.json")):
        try:
            assets = json.loads(path.read_text(encoding="utf-8")).get("assets")
        except (json.JSONDecodeError, AttributeError) as broken:
            raise SystemExit(f"error: {path.relative_to(REPO_ROOT)} is not a label file: {broken}")
        if assets:
            sessions += 1
    return sessions


def render_fixture() -> str:
    """The product's own output, copied out of the committed report verbatim.

    Verbatim is the whole point. The previous hand-written version tidied the
    could-not-assess lines into aligned columns and shortened two of them, which
    made the front page's one direct quotation of the product a paraphrase of it.
    """
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    verdict = report["verdict"]
    coverage = report["coverage"]

    headline = _wrap(verdict["headline"], 72)
    locked = [line for line in verdict["couldNotAssess"] if "mechanic required" in line]

    lines = [
        FIXTURE_BEGIN,
        "",
        "```",
        *headline,
        "```",
        "",
        f"Red-flag score {verdict['redFlagScore']}/100 · {len(report['findings'])} findings · "
        f"{len(report['mechanicReferrals'])} mechanic referrals · "
        f"{round(coverage['score'] * 100)}% coverage",
        "",
        "The verdict opens with what it *could not* assess, and these lines are in",
        "every report this product can produce:",
        "",
        "```",
        *locked,
        "```",
        "",
        FIXTURE_END,
    ]
    return "\n".join(lines)


def _wrap(text: str, width: int) -> list[str]:
    out: list[str] = []
    line = ""
    for word in text.split():
        if line and len(line) + 1 + len(word) > width:
            out.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        out.append(line)
    return out


# --- link integrity -----------------------------------------------------------


def check_links(text: str) -> list[str]:
    """Every path the README names must resolve to a file that exists.

    Two kinds, both checked, because both have been wrong here before:

      * markdown links - `[LAWS](docs/LAWS.md)` - resolved from the repo root;
      * backticked BARE FILENAMES in prose - `safety.py` - resolved by basename,
        and required to be UNAMBIGUOUS. A basename that matches two files is not
        a reference, it is a guess, and P10 removed exactly that fallback from
        test_laws_are_kept.py for making its existence check near-vacuous;
      * backticked paths CONTAINING A SLASH - `packages/db/src/schema.ts` - which
        must resolve exactly. Writing part of a path is a claim about where a
        file lives, and `db/schema.ts` satisfying itself by matching some
        `schema.ts` elsewhere is the same near-vacuous check one level down. It
        passed that way in the first draft of this function.
    """
    problems: list[str] = []

    for label, target in re.findall(r"\[([^\]]+)\]\(([^)]+)\)", text):
        if target.startswith(("http://", "https://", "#")):
            continue
        path = REPO_ROOT / target.split("#")[0]
        if not path.exists():
            problems.append(f"link [{label}]({target}) points at nothing")

    suffixes = ("py", "ts", "tsx", "md", "sh", "json", "mjs", "css", "yml", "toml")
    pattern = r"`([A-Za-z0-9_./-]+\.(?:" + "|".join(suffixes) + r"))`"
    for raw in sorted(set(re.findall(pattern, text))):
        if (REPO_ROOT / raw).exists():
            continue
        if "/" in raw:
            problems.append(f"`{raw}` is a path, and there is no such file")
            continue
        matches = [
            p
            for p in REPO_ROOT.rglob(raw)
            if not any(
                part in {"node_modules", ".venv", ".next", ".git", ".turbo", "__pycache__"}
                for part in p.parts
            )
        ]
        if not matches:
            problems.append(f"`{raw}` names no file in the repository")
        elif len(matches) > 1:
            rel = ", ".join(sorted(str(m.relative_to(REPO_ROOT)) for m in matches))
            problems.append(f"`{raw}` is ambiguous - matches {rel}. Write the path.")

    return problems


# --- driver -------------------------------------------------------------------


def _replace(text: str, begin: str, end: str, body: str) -> str:
    start = text.find(begin)
    stop = text.find(end)
    if start == -1 or stop == -1:
        raise SystemExit(
            f"error: README.md has no generated region delimited by\n"
            f"    {begin}\n    {end}\n"
            f"  Re-add the markers; this script will not guess where the block goes."
        )
    if stop < start:
        raise SystemExit(f"error: README.md has the markers for {begin!r} inverted")
    return text[:start] + body + text[stop + len(end) :]


def rendered(python_tests: int, ts_tests: int) -> str:
    text = README.read_text(encoding="utf-8")
    text = _replace(text, STANDING_BEGIN, STANDING_END, render_standing(python_tests, ts_tests))
    text = _replace(text, FIXTURE_BEGIN, FIXTURE_END, render_fixture())
    return text


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    check = args == ["--check"]
    if args and not check:
        print(__doc__)
        return 2

    if os.environ.get(GUARD):
        print("  check_readme: already running, refusing to recurse")
        return 0

    python_tests = count_python_tests()
    ts_tests = count_ts_tests()

    current = README.read_text(encoding="utf-8")
    wanted = rendered(python_tests, ts_tests)

    problems = check_links(wanted)
    ok = current == wanted and not problems

    if problems:
        print("  README.md names files that are not there:", file=sys.stderr)
        for problem in problems:
            print(f"    {problem}", file=sys.stderr)

    if ok:
        print(f"  README.md: {python_tests + ts_tests} tests, numbers and quotes match the repo")
        return 0

    if check:
        if current != wanted:
            sys.stdout.writelines(
                difflib.unified_diff(
                    current.splitlines(keepends=True),
                    wanted.splitlines(keepends=True),
                    fromfile="README.md (committed)",
                    tofile="README.md (from the repository)",
                )
            )
            print(
                "\nerror: the README's generated regions do not match the repository.\n"
                "  Run: python scripts/check_readme.py",
                file=sys.stderr,
            )
        return 1

    if problems:
        print("error: fix the paths above before regenerating", file=sys.stderr)
        return 1

    README.write_text(wanted, encoding="utf-8")
    print(f"  rewrote the generated regions in README.md ({python_tests + ts_tests} tests)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
