"""Two documents that transcribe code, held to the code they transcribe.

Both tables in scope were found wrong this session by somebody reading them, which
is the only way either could have been found:

- `docs/UNIT_ECONOMICS.md` quoted Opus 5 at $15/$75 for three phases after
  `cogs.MODEL_PRICES` was corrected to $5/$25. The corrected number sat in the code
  and the stale one sat on the page a person would actually read, and every dollar
  figure derived from it was wrong by threefold.
- `docs/LIABILITY.md` section 5 says of itself that it is `copy_rules.BANNED`
  "transcribed", and it was not: `inspected by` was in the scan and missing from the
  table, and bare "passed" was in the table and never in the scan.

A number copied by hand from code into prose drifts. That is not a prediction, it is
what both of these did. So the tables are parsed out of the markdown and compared,
and the documents carry the columns needed to make that mechanical.

What this does NOT check, in either case, is whether the code is right. Nothing here
can tell whether `MODEL_PRICES` still matches Anthropic's published prices - that is
a dated comment in `cogs.py` and a human re-checking it - and nothing here can tell
whether the phrase list is the right list. This gate is about drift between two
places that claim to say the same thing, and both documents say so where they state
it.
"""

from __future__ import annotations

import re
from pathlib import Path

from tirekick_engines.cogs import FALLBACK_PRICE, MODEL_PRICES, prices_for
from tirekick_engines.copy_rules import BANNED

REPO_ROOT = Path(__file__).resolve().parents[3]
UNIT_ECONOMICS = REPO_ROOT / "docs" / "UNIT_ECONOMICS.md"
LIABILITY = REPO_ROOT / "docs" / "LIABILITY.md"

#: Split a markdown table row on unescaped pipes. A banned-language regex is full
#: of alternations, so the cells that carry one are written with `\|` and the
#: separator has to know the difference.
CELL_SPLIT = re.compile(r"(?<!\\)\|")
CODE_SPAN = re.compile(r"`([^`\n]+)`")


def _cells(line: str) -> list[str]:
    return [
        cell.strip().strip("*").strip() for cell in CELL_SPLIT.split(line.strip().strip("|"))
    ]


def _money(cell: str) -> float | None:
    try:
        return float(cell.strip().lstrip("$").replace(",", ""))
    except ValueError:
        return None


def documented_prices() -> tuple[dict[str, tuple[float, float]], tuple[float, float] | None]:
    """The per-MTok table in UNIT_ECONOMICS, keyed by the model id it names.

    The model id is in the table because of this test. A row headed "Opus 5" reads
    fine and cannot be compared to anything - `TIREKICK_MODEL` is the string that
    actually selects a price, so it is the string the page has to print.
    """
    priced: dict[str, tuple[float, float]] = {}
    fallback: tuple[float, float] | None = None

    for line in UNIT_ECONOMICS.read_text(encoding="utf-8").splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = _cells(line)
        for index, cell in enumerate(cells[:-2]):
            ids = [span for span in CODE_SPAN.findall(cell) if span.startswith("claude-")]
            is_fallback = "FALLBACK_PRICE" in cell
            if not ids and not is_fallback:
                continue
            price_in, price_out = _money(cells[index + 1]), _money(cells[index + 2])
            if price_in is None or price_out is None:
                continue
            if is_fallback:
                fallback = (price_in, price_out)
            for model_id in ids:
                priced[model_id] = (price_in, price_out)

    return priced, fallback


def test_the_published_price_table_is_the_one_the_meter_bills_at() -> None:
    priced, _ = documented_prices()
    assert priced, "no priced rows parsed out of UNIT_ECONOMICS - the table shape changed"
    for model_id, documented in sorted(priced.items()):
        assert prices_for(model_id) == documented, (
            f"docs/UNIT_ECONOMICS.md prices {model_id} at {documented}; "
            f"cogs.py bills it at {prices_for(model_id)}"
        )


def test_every_priced_model_has_a_published_row() -> None:
    """A model priced in code and absent from the page is a rate nobody can check.

    Including the dated id alongside its alias: they are two spellings that select
    the same price, and a table that lists one of them makes the other look
    unpriced.
    """
    priced, _ = documented_prices()
    assert set(priced) == set(MODEL_PRICES), (
        f"only in cogs.py: {sorted(set(MODEL_PRICES) - set(priced))}; "
        f"only in the doc: {sorted(set(priced) - set(MODEL_PRICES))}"
    )


def test_the_fallback_row_is_the_fallback() -> None:
    """The most expensive row we know of, published as such.

    This row is the reason an unknown model cannot silently improve the unit
    economics, and it was the row that stayed right while the Opus row went stale -
    which is how three phases of readers saw $1.71 twice and believed it.
    """
    _, fallback = documented_prices()
    assert fallback == FALLBACK_PRICE, (
        f"docs/UNIT_ECONOMICS.md publishes {fallback} as the unpriced-model rate; "
        f"cogs.FALLBACK_PRICE is {FALLBACK_PRICE}"
    )


def documented_bans() -> list[tuple[str, str, str]]:
    """Section 5's table, unescaped back into the tuples it transcribes."""
    rows: list[tuple[str, str, str]] = []
    for line in LIABILITY.read_text(encoding="utf-8").splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = _cells(line)
        if len(cells) != 3:
            continue
        spans = CODE_SPAN.findall(cells[0])
        if len(spans) != 1 or not spans[0].startswith(r"\b"):
            continue
        rows.append((spans[0].replace(r"\|", "|"), cells[1], cells[2]))
    return rows


def test_the_banned_language_table_is_the_scan() -> None:
    """Section 5 calls itself a transcription. Held to that, in order.

    Order matters here for a duller reason than aesthetics: comparing sequences is
    what makes a duplicated row and a dropped row two different failures instead of
    one confusing one.
    """
    documented = documented_bans()
    assert documented, "no ban rows parsed out of LIABILITY section 5 - the table shape changed"
    assert documented == [tuple(row) for row in BANNED], (
        "docs/LIABILITY.md section 5 no longer transcribes copy_rules.BANNED.\n"
        f"documented: {documented}\ncode:       {[tuple(row) for row in BANNED]}"
    )


def test_every_banned_pattern_is_published_verbatim() -> None:
    """The specific P9 defect: a pattern in the scan and in no document.

    Stated separately from the transcription test because this is the direction
    that hurts - a phrase we ban and never wrote down is a rule the copy author
    cannot follow and finds out about from a red build.
    """
    documented = {pattern for pattern, _, _ in documented_bans()}
    missing = [pattern for pattern, _, _ in BANNED if pattern not in documented]
    assert not missing, f"banned in code, unpublished in LIABILITY section 5: {missing}"
