"""The constants both runtimes hold a copy of, compared rather than trusted.

D-002 keeps the report *shape* honest by parsing the emitted artifact with zod.
That gate can only see values a report contains, and `MODEL_LEVEL_TYPES` never
appears in one: it is the rule for what a report leaves out. A recall campaign
is true of every car of a model year, so those findings are kept out of the
red-flag score (D-021), out of the systems table (D-058) and out of the teaser
sample (D-044). Both runtimes apply that rule to their own copy of the list -
`dossier.py` on the way in, `report.ts` on the way out - and until this file
nothing compared the two. A finding type added to one copy would have been
excluded on one side of the paywall and scored on the other, and every test in
the repository would have stayed green.

The other constants here are gated only incidentally. `LOCKED_SYSTEM_STATEMENT`
is compared because the fixture happens to carry a locked row; `REPORT_BANNER`
is not compared anywhere at all, because the copy the landing page renders comes
from `constants.ts` while the copy in the report comes from `models.py`, and the
two are only ever read on different pages. D-049 says a duplicated definition
ships with the test that compares the copies. This is that test.

The parser is deliberately crude: the text between `export const NAME =` and the
terminating semicolon, with its double-quoted literals pulled out in order, or
read as a bare number when the constant is one. A computed value would defeat
it, so an unreadable declaration fails here rather than being quietly skipped -
a parser that silently matches nothing would turn every assertion below into a
green that means nothing.

`PRICE_USD` is here for a worse version of the `MODEL_LEVEL_TYPES` story. The
price existed three times - `checkout.ts` for the landing page, `cli.py` for the
teaser the engine writes, `test_teaser.py` for the tests - and the landing page
printed the TypeScript one while the very next page printed the Python one, from
constants that had never been compared. Equal literals pass every equality test
in the repository, so the gate below is on the *source*: a number typed a second
time is the defect, whether or not it happens to agree today.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import get_args

import pytest

from tirekick_engines.dossier import MODEL_LEVEL_TYPES
from tirekick_engines.models import (
    LOCKED_SYSTEM_STATEMENT,
    LOCKED_SYSTEMS,
    REPORT_BANNER,
    SCHEMA_VERSION,
    FindingType,
)
from tirekick_engines.teaser import PRICE_USD

REPO_ROOT = Path(__file__).resolve().parents[3]
CONSTANTS_TS = REPO_ROOT / "packages" / "shared" / "src" / "constants.ts"

_DOUBLE_QUOTED = re.compile(r'"((?:[^"\\]|\\.)*)"')
_EXPORTED = re.compile(r"^export const (\w+)", re.M)
_BARE_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")

#: Every constant `constants.ts` and the Python side both declare.
#:
#: A string compares by value, including one written as concatenated literals.
#: A number compares by value across the two spellings of the same amount - the
#: TypeScript copy is `25` and the Python one is `25.0`, because the teaser field
#: it fills is a float. A collection compares as a set: the TypeScript copies are
#: ordered arrays and the Python ones are frozensets, and neither side's
#: iteration order is a claim the other has to honour.
MIRRORED: dict[str, str | float | frozenset[str]] = {
    "SCHEMA_VERSION": SCHEMA_VERSION,
    "LOCKED_SYSTEM_STATEMENT": LOCKED_SYSTEM_STATEMENT,
    "REPORT_BANNER": REPORT_BANNER,
    "LOCKED_SYSTEMS": LOCKED_SYSTEMS,
    "MODEL_LEVEL_TYPES": MODEL_LEVEL_TYPES,
    "PRICE_USD": PRICE_USD,
}

#: Constants that exist only for the web app.
#:
#: `SHARE_FOOTER` is the watermark on the share page and the print footer. No
#: engine emits it and no report carries it, so there is no second copy to drift
#: from. Named rather than omitted, so that adding a constant to `constants.ts`
#: forces a choice instead of silently landing outside every gate.
WEB_ONLY = frozenset({"SHARE_FOOTER"})


def _declaration(name: str) -> str:
    source = CONSTANTS_TS.read_text(encoding="utf-8")
    match = re.search(rf"^export const {name}\s*=\s*(.*?);\s*$", source, re.M | re.S)
    if match is None:
        pytest.fail(f"{name} is not declared in {CONSTANTS_TS}")
    return match.group(1)


def _strings(name: str) -> list[str]:
    values = _DOUBLE_QUOTED.findall(_declaration(name))
    if not values:
        pytest.fail(f"{name} holds no string literal this parser can read")
    return values


def _number(name: str) -> float:
    declaration = _declaration(name).strip()
    if not _BARE_NUMBER.fullmatch(declaration):
        pytest.fail(f"{name} is not a bare number this parser can read: {declaration!r}")
    return float(declaration)


@pytest.mark.parametrize("name", sorted(MIRRORED))
def test_the_typescript_copy_says_the_same_thing(name: str) -> None:
    expected = MIRRORED[name]
    if isinstance(expected, str):
        assert "".join(_strings(name)) == expected
    elif isinstance(expected, float):
        assert _number(name) == expected
    else:
        assert set(_strings(name)) == set(expected)


def test_model_level_types_are_finding_types_that_exist() -> None:
    """A misspelt member excludes nothing, and says nothing about it.

    `MODEL_LEVEL_TYPES` is a frozenset of bare strings on both sides, tested
    with `in` against a finding's type. `open_recal` would match no finding,
    every recall would be scored as damage observed on this car, and the parity
    test above would pass because both copies agree on the same typo.
    """
    assert set(MODEL_LEVEL_TYPES) <= set(get_args(FindingType))


def test_every_shared_constant_is_compared_or_declared_web_only() -> None:
    """The list above is a third copy, and lists drift too.

    `MODEL_LEVEL_TYPES` was not missing a gate because anyone decided it did not
    need one - it was missing because nothing ever asked what `constants.ts`
    declares. This asks. A constant added there tomorrow is either compared
    against its Python twin or named as web-only, and there is no third state
    where it is simply not looked at.
    """
    declared = set(_EXPORTED.findall(CONSTANTS_TS.read_text(encoding="utf-8")))
    assert declared - set(MIRRORED) - WEB_ONLY == set()


#: The one Python file allowed to write the report price down as a number.
PRICE_DECLARED_IN = "teaser.py"

#: Python source that puts a number where the report price belongs.
#:
#: Crude in the same way as the declaration parser above, and for the same
#: reason. `assign` matches `PRICE = 25.0`, `PRICE_USD = 25.0` and
#: `price_usd=25.0`; the lookbehind keeps it off `asking_price_usd`, which is
#: what the seller wants for the car and has nothing to do with what we charge.
#: `argparse` matches a numeric `default=` inside the `--price` declaration.
#:
#: What it does not catch: a literal reached by arithmetic, a price spelled in
#: cents, or a number handed in from outside the repository. Nothing checks
#: those. This catches the shape the defect actually took twice.
_PRICE_LITERALS = (
    re.compile(r"(?<![A-Za-z_])price(_usd)?\s*=\s*[0-9]", re.I),
    re.compile(r'"--price"[\s\S]{0,400}?default\s*=\s*[0-9]'),
)

#: Files the scan does not read.
#:
#: `teaser.py` is where the number is supposed to be. This file has to write the
#: forbidden shapes down in order to prove the scan fires at all, the same way
#: `copy_rules.py` is exempt from the banned-language scan it declares. Exempt by
#: role, never by sentence - and it is a hole: a second literal hidden in this
#: file is a second literal nothing catches.
_SCAN_EXEMPT = frozenset({PRICE_DECLARED_IN, Path(__file__).name})


def test_only_one_python_file_writes_the_price_down() -> None:
    """Equal literals pass every equality test, so this one reads the source.

    `cli.py` carried `--price default=25.0` and `test_teaser.py` carried
    `PRICE = 25.0`, both agreeing with `checkout.ts` and with each other, and a
    test asserting they were equal would have been green on the day the defect
    shipped. The number moves when someone changes it in one place, and no
    assertion about values can fail before that happens. So the rule is that the
    literal exists once: everywhere else reads `teaser.PRICE_USD`, which the
    parity test above holds against `constants.ts`.
    """
    sources = sorted(REPO_ROOT.glob("packages/engines/src/tirekick_engines/**/*.py"))
    sources += sorted(REPO_ROOT.glob("packages/engines/tests/*.py"))
    assert sources, "the globs found no Python files, so this test asserts nothing"

    offenders = sorted(
        {
            str(path.relative_to(REPO_ROOT))
            for path in sources
            if path.name not in _SCAN_EXEMPT
            for pattern in _PRICE_LITERALS
            if pattern.search(path.read_text(encoding="utf-8"))
        }
    )
    assert offenders == [], (
        "a second price literal: " + ", ".join(offenders) + f" - read it from "
        f"{PRICE_DECLARED_IN}::PRICE_USD instead"
    )


def test_the_price_literal_scan_can_actually_fire() -> None:
    """A scan that never matches is indistinguishable from no scan.

    Both patterns are asserted against the exact source shapes they were written
    for, because `test_only_one_python_file_writes_the_price_down` passes just as
    happily when the regexes are broken as when the tree is clean.
    """
    assign, argparse_default = _PRICE_LITERALS
    assert assign.search("PRICE = 25.0")
    assert assign.search("PRICE_USD = 25.0")
    assert assign.search("build_teaser(report, price_usd=25.0)")
    assert not assign.search("build_teaser(report, price_usd=PRICE_USD)")
    assert not assign.search("PriceCheck(asking_price_usd=9000)")
    assert argparse_default.search('inspect.add_argument("--price", type=float, default=25.0)')
    assert not argparse_default.search(
        'inspect.add_argument("--price", type=float, default=PRICE_USD)'
    )
