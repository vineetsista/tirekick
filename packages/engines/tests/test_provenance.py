"""LAW 3 - the provenance records, checked against what is actually committed.

Twice in one session a hand-maintained provenance table was found drifted from
disk. `fixtures/PROVENANCE.md` ran from P3 to P9 with no row for the rendered
spectrogram, and from P7 to P9 with no rows for the walkaround video or its five
extracted frames - seven files that the same document's front page described as
synthetic without listing them. Each gap opened in the commit that added the
artifact and closed in none of the phase gates after it, because no gate read the
file. Both documents said so about themselves, in writing, for phases.

So this is the gate. It reads both directions - a committed file with no row, and
a row naming a file that is not there - plus the file counts the documents state
about whole directories, which is the other hand-typed number nobody re-derives.

What it deliberately does not check is whether a row is TRUE. "Drawn by
`scripts/make_fixture_media.py`" is a claim about how a file was made and nothing
here opens the file to confirm it. This proves the enumeration is complete, not
that the descriptions are honest: the P10 audit found a frames row whose four
counts were each correct and whose sentence around them did not add up, and a test
of this shape would not have caught that. Saying so is cheaper than implying
otherwise.

The file list comes from `git ls-files` rather than from the working tree, on
purpose. An uncommitted scratch file under `fixtures/` is not yet a provenance
obligation and a developer holding one should not see a red suite. The blind spot
that buys is real - a file is checked from the moment it is staged, not from the
moment it is written - and it is the smaller of the two failures.

The document conventions this parser relies on are written down in the
"How this file is checked" note at the top of each PROVENANCE.md, because a test
that silently requires a house style is a test that gets edited around.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

#: Suffixes a provenance row can be about. A code span with any other suffix -
#: `scripts/make_fixture_media.py`, `safety.apply_safety_law` - is a reference to
#: code, not a claim about a committed artifact.
#:
#: An allowlist rather than a denylist, because the failure modes are not
#: symmetric: an unlisted suffix makes a ROW invisible, which shows up as an
#: uncovered file, while an over-broad denylist makes prose look like a filename
#: and fails on text that was never a claim. `test_every_committed_suffix_is_one
#: _this_parser_understands` closes the hole the allowlist opens.
COVERAGE_SUFFIXES = frozenset({".jpg", ".json", ".md", ".mp4", ".png", ".txt", ".wav"})

#: `photo_01.jpg` .. `photo_08.jpg` - and the abbreviated right-hand form the
#: fixture record uses, `video_01.frame_01.jpg` .. `frame_05.jpg`.
RANGE_SPAN = re.compile(r"`([^`\n]+)`\s*\.\.\s*`([^`\n]+)`")
CODE_SPAN = re.compile(r"`([^`\n]+)`")
#: A directory code span followed by a stated file count, in the same line.
DIR_COUNT = re.compile(r"`([A-Za-z0-9_./-]+/)`[^`\n]*?\b(\d+) (?:committed )?files?\b")
#: The last run of digits in a filename, which is the one a range counts on.
LAST_NUMBER = re.compile(r"(\d+)(?!.*\d)")


@dataclass(frozen=True)
class Claim:
    """One row's claim about the tree: a filename, or a pattern plus its count."""

    token: str
    line: int
    count: int | None

    @property
    def is_pattern(self) -> bool:
        return "*" in self.token or "<" in self.token


def committed(prefix: str) -> list[str]:
    """Repo-relative paths git is tracking under `prefix`."""
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", prefix],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
        text=True,
    )
    return sorted(p for p in result.stdout.split("\0") if p)


def _expand_range(left: str, right: str) -> list[str]:
    """Every filename between two endpoints written as `a` .. `b`.

    Expanded rather than treated as a wildcard so that a ninth photograph in a
    directory whose row still ends at the eighth is an uncovered file.
    """
    start_match = LAST_NUMBER.search(left)
    end_match = LAST_NUMBER.search(right)
    if start_match is None or end_match is None:
        return [left, right]
    width = len(start_match.group(1))
    start, end = int(start_match.group(1)), int(end_match.group(1))
    if end < start:
        return [left, right]
    head, tail = left[: start_match.start(1)], left[start_match.end(1) :]
    return [f"{head}{index:0{width}d}{tail}" for index in range(start, end + 1)]


def _count_for(line: str, token: str) -> int | None:
    """The count a pattern row states, in one of the two documented positions."""
    if line.lstrip().startswith("|"):
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        for index, cell in enumerate(cells[:-1]):
            if f"`{token}`" in cell and cells[index + 1].isdigit():
                return int(cells[index + 1])
        return None
    adjacent = re.search(rf"(\d+) +`{re.escape(token)}`", line)
    return int(adjacent.group(1)) if adjacent else None


def _pattern_regex(token: str) -> re.Pattern[str]:
    parts = re.split(r"(\*|<[^>]*>)", token)
    body = "".join(
        ".*" if part == "*" else ".+" if part.startswith("<") else re.escape(part)
        for part in parts
    )
    return re.compile(rf"^{body}$")


def claims_in(doc_text: str) -> list[Claim]:
    """Every coverage claim a provenance document makes, in document order."""
    found: list[Claim] = []
    for number, line in enumerate(doc_text.splitlines(), start=1):
        tokens: list[str] = []
        endpoints: set[str] = set()
        for left, right in RANGE_SPAN.findall(line):
            tokens.extend(_expand_range(left, right))
            endpoints.update((left, right))
        # The endpoints themselves are dropped: the expansion already names them,
        # and the right-hand one is written abbreviated - `frame_05.jpg` for
        # `video_01.frame_05.jpg` - so read alone it is a row for a file that does
        # not exist.
        tokens.extend(span for span in CODE_SPAN.findall(line) if span not in endpoints)
        for raw in tokens:
            token = raw.strip()
            if " " in token or token.endswith("/"):
                continue
            if Path(token).suffix not in COVERAGE_SUFFIXES:
                continue
            found.append(Claim(token, number, _count_for(line, token)))
    return found


def _resolve(token: str, root: str, files: list[str]) -> list[str]:
    if "/" in token:
        wanted = {f"{root}/{token}", token}
        return [path for path in files if path in wanted]
    return [path for path in files if Path(path).name == token]


@dataclass(frozen=True)
class Audit:
    uncovered: list[str]
    orphaned: list[str]
    miscounted: list[str]


def audit(root: str, doc_text: str, files: list[str]) -> Audit:
    """Compare one provenance document against one committed subtree.

    Split out from the tests that call it on the real repository so that the
    checker itself is exercised on inputs that are known to be wrong. A gate whose
    only inputs are the files it currently passes on is a gate nobody has watched
    fail.
    """
    names = [Path(path).name for path in files]
    covered: set[str] = set()
    orphaned: list[str] = []
    miscounted: list[str] = []

    for claim in claims_in(doc_text):
        if claim.is_pattern:
            pattern = _pattern_regex(claim.token)
            matched = [
                path for path, name in zip(files, names, strict=True) if pattern.match(name)
            ]
            covered.update(matched)
            if claim.count is None:
                miscounted.append(
                    f"line {claim.line}: `{claim.token}` covers files by pattern and "
                    f"states no count, so a new file can hide inside it"
                )
            elif claim.count != len(matched):
                miscounted.append(
                    f"line {claim.line}: `{claim.token}` says {claim.count} file(s), "
                    f"{len(matched)} committed"
                )
            continue

        matched = _resolve(claim.token, root, files)
        if matched:
            covered.update(matched)
        elif not (REPO_ROOT / claim.token).exists():
            # Not in this tree and not anywhere else either: a row about a file
            # that is not in the repository at all.
            orphaned.append(f"line {claim.line}: `{claim.token}`")

    for statement in DIR_COUNT.finditer(doc_text):
        raw_dir, stated = statement.group(1), int(statement.group(2))
        prefix = (
            raw_dir
            if raw_dir.startswith(f"{root}/") or raw_dir == f"{root}/"
            else f"{root}/{raw_dir}"
        )
        actual = len([path for path in files if path.startswith(prefix)])
        if actual != stated:
            miscounted.append(f"`{raw_dir}` says {stated} file(s), {actual} committed")

    return Audit(
        uncovered=sorted(set(files) - covered),
        orphaned=orphaned,
        miscounted=miscounted,
    )


FIXTURES_DOC = REPO_ROOT / "fixtures" / "PROVENANCE.md"
BENCH_DOC = REPO_ROOT / "bench" / "PROVENANCE.md"


@pytest.mark.parametrize(
    ("root", "doc"),
    [("fixtures", FIXTURES_DOC), ("bench", BENCH_DOC)],
    ids=["fixtures", "bench"],
)
def test_the_record_matches_the_tree(root: str, doc: Path) -> None:
    """The gate itself, in all three directions at once."""
    files = committed(root)
    assert files, f"git is tracking nothing under {root}/ - the check is looking at nothing"

    result = audit(root, doc.read_text(encoding="utf-8"), files)
    assert not result.uncovered, (
        f"committed under {root}/ with no row in {doc.name}:\n  "
        + "\n  ".join(result.uncovered)
    )
    assert not result.orphaned, (
        f"{doc.name} names files that are not in the repository:\n  "
        + "\n  ".join(result.orphaned)
    )
    assert not result.miscounted, (
        f"{doc.name} states counts that do not match the tree:\n  "
        + "\n  ".join(result.miscounted)
    )


def test_every_committed_suffix_is_one_this_parser_understands() -> None:
    """The hole the allowlist opens, closed.

    `COVERAGE_SUFFIXES` decides which code spans count as rows. A media file with
    a suffix outside it can be enumerated in the document and still read as
    uncovered, which is a confusing red rather than a silent green - but it is
    still a reason to extend the list deliberately rather than to argue with the
    failure.
    """
    unknown = {
        Path(path).suffix
        for path in committed("fixtures") + committed("bench")
        if Path(path).suffix not in COVERAGE_SUFFIXES
    }
    assert not unknown, f"add these to COVERAGE_SUFFIXES: {sorted(unknown)}"


def test_the_directory_counts_are_actually_being_read() -> None:
    """A regex that matches nothing passes every test built on it.

    The counts are the half of this file most likely to become decorative, since
    they live in prose rather than in a table.
    """
    fixtures_statements = DIR_COUNT.findall(FIXTURES_DOC.read_text(encoding="utf-8"))
    bench_statements = DIR_COUNT.findall(BENCH_DOC.read_text(encoding="utf-8"))
    assert len(fixtures_statements) >= 2, fixtures_statements
    assert len(bench_statements) >= 1, bench_statements


def test_a_committed_file_with_no_row_is_caught() -> None:
    """The P3 spectrogram and the P7 video, as this gate would have seen them."""
    doc = "| `photo_01.jpg` | drawn |"
    result = audit("fixtures", doc, ["fixtures/m/photo_01.jpg", "fixtures/m/video_01.mp4"])
    assert result.uncovered == ["fixtures/m/video_01.mp4"]


def test_a_row_naming_a_file_that_does_not_exist_is_caught() -> None:
    """The other direction: a row that outlived the file it describes."""
    doc = "| `photo_01.jpg` | drawn |\n| `photo_02.jpg` | drawn |"
    result = audit("fixtures", doc, ["fixtures/m/photo_01.jpg"])
    assert result.orphaned == ["line 2: `photo_02.jpg`"]


def test_a_range_covers_its_endpoints_and_stops_there() -> None:
    """`photo_01.jpg` .. `photo_08.jpg` must not quietly cover a ninth."""
    doc = "| `photo_01.jpg` .. `photo_03.jpg` | drawn |"
    files = [f"fixtures/m/photo_0{n}.jpg" for n in (1, 2, 3, 4)]
    result = audit("fixtures", doc, files)
    assert result.uncovered == ["fixtures/m/photo_04.jpg"]


def test_an_abbreviated_range_endpoint_expands_from_the_left_token() -> None:
    assert _expand_range("video_01.frame_01.jpg", "frame_03.jpg") == [
        "video_01.frame_01.jpg",
        "video_01.frame_02.jpg",
        "video_01.frame_03.jpg",
    ]


def test_a_pattern_row_must_state_a_count() -> None:
    """Otherwise the pattern is a hiding place, which is what a row must not be."""
    doc = "| `vpic.decode.<vin>.json` | | vPIC |"
    result = audit("fixtures", doc, ["fixtures/federal/vpic.decode.A.json"])
    assert result.miscounted and "states no count" in result.miscounted[0]


def test_a_pattern_count_that_no_longer_matches_the_tree_is_caught() -> None:
    doc = "| `vpic.decode.<vin>.json` | 1 | vPIC |"
    files = ["fixtures/federal/vpic.decode.A.json", "fixtures/federal/vpic.decode.B.json"]
    result = audit("fixtures", doc, files)
    assert result.miscounted == ["line 1: `vpic.decode.<vin>.json` says 1 file(s), 2 committed"]


def test_a_stated_directory_count_that_drifted_is_caught() -> None:
    doc = "Cached responses - `demo-01/cached/` - 1 files\n| `vision.a.json` | 1 |"
    files = ["fixtures/demo-01/cached/vision.a.json", "fixtures/demo-01/cached/vision.b.json"]
    result = audit("fixtures", doc, files)
    assert any("says 1 file(s), 2 committed" in problem for problem in result.miscounted)


def test_a_reference_to_code_elsewhere_in_the_repo_is_not_read_as_a_row() -> None:
    """`docs/ACCURACY.md` is a cross-reference. `photo_09.jpg` is a claim."""
    doc = "See `docs/ACCURACY.md` and `scripts/make_fixture_media.py` and `DECISIONS.md`."
    result = audit("fixtures", doc, ["fixtures/m/photo_01.jpg"])
    assert result.orphaned == []
    assert result.uncovered == ["fixtures/m/photo_01.jpg"]
