"""VIN validation, offline.

A VIN is one of the few things in this product we can check without asking anyone
anything: ISO 3779 fixes the alphabet, the length, and - in North America - a
check digit in position 9 that is a function of the other sixteen characters. A
mistyped VIN is the single most likely input error a buyer will make, and catching
it here means we never run a lookup for a car that does not exist and then present
the answer as if it were theirs.

Nothing in this module touches the network. The federal lookups in sources.py run
only after `validate` is satisfied, so a typo costs a message rather than a
citation for the wrong vehicle.

The one subtlety worth stating plainly: the check digit is mandatory for vehicles
built for the North American market and optional everywhere else. Treating a
failed check digit on a German-market VIN as a hard error would reject valid VINs,
so the region gates the severity. See DECISIONS.md D-014.
"""

from __future__ import annotations

from dataclasses import dataclass

VIN_LENGTH = 17

#: I, O and Q are excluded from the VIN alphabet precisely because they are
#: confusable with 1, 0 and 0. Their presence is a typo, not a VIN.
FORBIDDEN_LETTERS = frozenset("IOQ")

#: Transliteration table from ISO 3779. Digits map to themselves.
_TRANSLITERATION: dict[str, int] = {
    **{str(d): d for d in range(10)},
    **dict(
        zip(
            "ABCDEFGHJKLMNPRSTUVWXYZ",
            (1, 2, 3, 4, 5, 6, 7, 8, 1, 2, 3, 4, 5, 7, 9, 2, 3, 4, 5, 6, 7, 8, 9),
            strict=True,
        )
    ),
}

#: Positional weights. Position 9 (index 8) weighs 0 - it is the check digit itself.
_WEIGHTS = (8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2)

#: Model year encoding for position 10. The alphabet runs A=1980 through 9=2009
#: and then repeats, A=2010 through 9=2039, so one character always means two
#: possible years thirty years apart.
_YEAR_CODES = "ABCDEFGHJKLMNPRSTVWXY123456789"

#: The tie-breaker is position 7. For vehicles under 10,000 lb GVWR the standard
#: puts a letter there for the 2010-2039 cycle and a digit for 1980-2009. It is a
#: convention rather than arithmetic, and it does not hold for heavy trucks, so
#: both candidate years are returned and this only decides their order.
_LIGHT_VEHICLE_YEAR_TIEBREAK_INDEX = 6

#: First character of the WMI. 1-5 are the United States, Canada and Mexico, whose
#: vehicles are required to carry a valid check digit.
_NORTH_AMERICAN_WMI = frozenset("12345")


@dataclass(frozen=True)
class VinCheck:
    """The result of looking at a VIN without looking anything up."""

    raw: str
    vin: str
    valid: bool
    #: Machine-readable reasons, empty when valid.
    problems: tuple[str, ...]
    #: None when the VIN is too malformed for the question to mean anything.
    check_digit_ok: bool | None
    check_digit_required: bool
    model_year_hint: int | None
    #: One sentence, written for the buyer, always present.
    statement: str


def normalize(raw: str) -> str:
    """Uppercase and strip the separators people type into VIN boxes."""
    return "".join(ch for ch in raw.upper() if ch.isalnum())


def check_digit(vin: str) -> str:
    """The character that position 9 must hold, per ISO 3779."""
    total = sum(_TRANSLITERATION[ch] * w for ch, w in zip(vin, _WEIGHTS, strict=True))
    remainder = total % 11
    return "X" if remainder == 10 else str(remainder)


def model_year_candidates(vin: str) -> tuple[int, ...]:
    """Both years position 10 can mean, likeliest first.

    Deliberately plural. The code repeats on a thirty-year cycle, so a VIN alone
    cannot settle the year, and the authoritative answer is whatever vPIC returns.
    This exists so `data.py` can ask whether vPIC's year is one of the two the VIN
    permits - a cheap, offline consistency check on our own plumbing.
    """
    index = _YEAR_CODES.find(vin[9])
    if index < 0:
        return ()
    older, newer = 1980 + index, 2010 + index
    looks_recent = vin[_LIGHT_VEHICLE_YEAR_TIEBREAK_INDEX].isalpha()
    return (newer, older) if looks_recent else (older, newer)


def model_year_hint(vin: str) -> int | None:
    """The likelier of the two candidate years, or None if position 10 is invalid."""
    candidates = model_year_candidates(vin)
    return candidates[0] if candidates else None


def validate(raw: str) -> VinCheck:
    """Check a VIN's shape without asking the network anything."""
    vin = normalize(raw)
    problems: list[str] = []

    if len(vin) != VIN_LENGTH:
        return VinCheck(
            raw=raw,
            vin=vin,
            valid=False,
            problems=("length",),
            check_digit_ok=None,
            check_digit_required=False,
            model_year_hint=None,
            statement=(
                f"That is {len(vin)} characters; a VIN is exactly {VIN_LENGTH}. "
                f"Check the number on the dash plate or the driver's door jamb."
            ),
        )

    bad_letters = sorted(set(vin) & FORBIDDEN_LETTERS)
    if bad_letters:
        problems.append("forbidden_letters")

    # I, O and Q are absent from the transliteration table too, so they would
    # otherwise be reported twice - once for being forbidden and once for being
    # unknown. The forbidden reason is the useful one; it explains itself.
    unknown = sorted(
        ch for ch in vin if ch not in _TRANSLITERATION and ch not in FORBIDDEN_LETTERS
    )
    if unknown:
        problems.append("non_vin_characters")

    if problems:
        # The check digit is arithmetic over the alphabet; it cannot be computed
        # for characters outside it, and guessing would be worse than declining.
        hint = ", ".join(bad_letters + unknown)
        return VinCheck(
            raw=raw,
            vin=vin,
            valid=False,
            problems=tuple(problems),
            check_digit_ok=None,
            check_digit_required=False,
            model_year_hint=None,
            statement=(
                f"A VIN never contains {hint}. The letters I, O and Q are excluded "
                f"from the VIN alphabet so they cannot be confused with 1 and 0 - "
                f"so those characters are digits, misread."
            ),
        )

    required = vin[0] in _NORTH_AMERICAN_WMI
    expected = check_digit(vin)
    ok = vin[8] == expected
    year = model_year_hint(vin)

    if not ok and required:
        return VinCheck(
            raw=raw,
            vin=vin,
            valid=False,
            problems=("check_digit",),
            check_digit_ok=False,
            check_digit_required=True,
            model_year_hint=year,
            statement=(
                "This VIN fails its check digit. Every VIN built for the North "
                "American market carries a digit in position 9 computed from the "
                "other sixteen characters, and this one does not match, which "
                "means at least one character is wrong. Re-read it and try again."
            ),
        )

    if not ok:
        # Valid, but say so out loud rather than quietly pretending we verified it.
        return VinCheck(
            raw=raw,
            vin=vin,
            valid=True,
            problems=("check_digit_unverified",),
            check_digit_ok=False,
            check_digit_required=False,
            model_year_hint=year,
            statement=(
                "This VIN is the right length and alphabet, but it fails the "
                "position-9 check digit. That digit is only mandatory on vehicles "
                "built for the North American market, and this VIN was not, so the "
                "mismatch is not proof of a typo - but it is not confirmation "
                "either. TIREKICK could not verify the VIN arithmetically."
            ),
        )

    return VinCheck(
        raw=raw,
        vin=vin,
        valid=True,
        problems=(),
        check_digit_ok=True,
        check_digit_required=required,
        model_year_hint=year,
        statement=(
            "VIN is 17 characters and passes its position-9 check digit, so it is "
            "internally consistent. That confirms the number was transcribed "
            "correctly. It does not confirm the number belongs to the car in the "
            "photographs."
        ),
    )


def mask(vin: str) -> str:
    """LIABILITY section 6 - full VINs never reach a shareable surface.

    The last six characters are the serial: the part that identifies one physical
    vehicle rather than a model. Those are what get hidden.
    """
    if len(vin) <= 6:
        return "*" * len(vin)
    return vin[:-6] + "******"
