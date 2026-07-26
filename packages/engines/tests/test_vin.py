"""VIN validation - the offline half of the data engine.

These vectors are the reason `data.py` never runs a lookup on a mistyped number.
"""

from __future__ import annotations

import pytest

from tirekick_engines import vin as vin_module

#: Documentation VINs from the golden set. Real model codes, synthetic serial,
#: check digit recomputed to match. See fixtures/federal/GOLDEN_VINS.json.
VALID = (
    "1HGCM82673A000000",
    "1HGCR2F37DA000000",
    "1FTFW1ET6DFC00000",
    "4S4BSANC9G3000000",
    "3GCUKRECXFG000000",
    "KM8J3CA43JU000000",
)


@pytest.mark.parametrize("value", VALID)
def test_golden_vins_validate(value: str) -> None:
    check = vin_module.validate(value)
    assert check.valid, check.statement
    assert check.check_digit_ok is True


@pytest.mark.parametrize("value", VALID)
def test_check_digit_is_self_consistent(value: str) -> None:
    """The digit in position 9 is exactly what the algorithm recomputes."""
    assert vin_module.check_digit(value) == value[8]


def test_check_digit_x_is_a_valid_value() -> None:
    """Remainder 10 is written X, not 10. The Silverado in the set covers it."""
    assert vin_module.check_digit("3GCUKRECXFG000000") == "X"


def test_wrong_length_is_rejected_before_anything_else() -> None:
    check = vin_module.validate("1HGCM8267")
    assert not check.valid
    assert check.problems == ("length",)
    assert "17" in check.statement


def test_separators_are_stripped_not_counted() -> None:
    """People paste VINs with spaces and hyphens in them."""
    check = vin_module.validate(" 1hg-cr2f3 7da 000000 ")
    assert check.valid
    assert check.vin == "1HGCR2F37DA000000"


@pytest.mark.parametrize("letter", ["I", "O", "Q"])
def test_forbidden_letters_are_rejected_with_the_reason(letter: str) -> None:
    """I, O and Q are excluded from the alphabet precisely to prevent this typo."""
    bad = "1HGCR2F37DA00000" + letter
    check = vin_module.validate(bad)
    assert not check.valid
    assert check.problems == ("forbidden_letters",)
    assert letter in check.statement


def test_north_american_vin_with_a_bad_check_digit_is_rejected() -> None:
    """A US-market VIN must satisfy the check digit. This one cannot be right."""
    broken = "1HGCR2F31DA000000"  # position 9 forced to 1; correct value is 7
    check = vin_module.validate(broken)
    assert not check.valid
    assert check.problems == ("check_digit",)
    assert check.check_digit_required is True


def test_imported_vin_with_a_bad_check_digit_is_flagged_not_rejected() -> None:
    """Outside North America the check digit is optional, so a mismatch is a
    warning. Rejecting these would refuse valid VINs on imported cars."""
    broken = "WBA3A5C51DF599990"
    check = vin_module.validate(broken)
    assert check.valid
    assert check.check_digit_ok is False
    assert check.check_digit_required is False
    assert "could not verify" in check.statement


def test_model_year_returns_both_readings_likeliest_first() -> None:
    """Position 10 repeats every 30 years, so one character means two years."""
    assert vin_module.model_year_candidates("1HGCM82673A000000") == (2003, 2033)
    assert vin_module.model_year_candidates("1HGCR2F37DA000000") == (2013, 1983)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1HGCM82673A000000", 2003),
        ("1HGCR2F37DA000000", 2013),
        ("1FTFW1ET6DFC00000", 2013),
        ("4S4BSANC9G3000000", 2016),
        ("3GCUKRECXFG000000", 2015),
        ("KM8J3CA43JU000000", 2018),
    ],
)
def test_model_year_hint_matches_what_vpic_decoded(value: str, expected: int) -> None:
    """The offline hint agrees with the federal decode on every golden VIN."""
    assert vin_module.model_year_hint(value) == expected


def test_mask_hides_the_serial_and_keeps_the_model_codes() -> None:
    """LIABILITY section 6. The last six characters identify one physical car."""
    assert vin_module.mask("1HGCR2F37DA000000") == "1HGCR2F37DA******"


def test_mask_never_leaks_a_short_value() -> None:
    assert vin_module.mask("12345") == "*****"
