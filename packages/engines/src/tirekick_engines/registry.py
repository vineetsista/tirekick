"""LAW 4 - the eval gate.

A finding type reaches a paid report only when its measured precision clears its
declared threshold on the labeled eval set. `enabled_for_paid` is the switch, and
it is off for everything until `bench/` produces a number.

`measured_precision is None` means "not measured" - which is not the same as zero
and is not the same as bad. It means we do not know, so we do not sell it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path

from .models import FindingType

#: Written by `tirekick bench`. The gate table and docs/ACCURACY.md both read it,
#: so a published number and a measured number cannot drift apart - there is no
#: second place to type a precision figure. Absent means unmeasured, which is the
#: state the project starts in and stays in until an eval set exists.
BENCH_RESULT_PATH = Path(__file__).resolve().parents[4] / "bench" / "results" / "latest.json"


@dataclass(frozen=True)
class FindingTypeSpec:
    type: FindingType
    label: str
    #: Precision required before this type may appear in a paid report.
    precision_gate: float
    #: Measured on the eval set. None until bench/ has run.
    measured_precision: float | None
    #: Sample size behind measured_precision.
    n: int
    #: Why the gate is set where it is.
    gate_rationale: str
    #: Smallest sample that may be used to clear the gate.
    #:
    #: Without this, LAW 4 is trivially gameable and would have been gamed in P1:
    #: five VINs that decode correctly is 5/5, which "clears" a 0.99 gate while
    #: telling us essentially nothing - the 95% confidence interval on 5/5 runs
    #: down to about 0.55. Requiring a sample size before a measurement counts is
    #: what stops a clean demo from being mistaken for evidence. See D-018.
    min_n: int = 50

    @property
    def enabled_for_paid(self) -> bool:
        if self.measured_precision is None:
            return False
        if self.n < self.min_n:
            return False
        return self.measured_precision >= self.precision_gate

    @property
    def status(self) -> str:
        """Why this type is where it is, in three words or so."""
        if self.measured_precision is None:
            return "not measured"
        if self.n < self.min_n:
            return f"n too small (<{self.min_n})"
        if self.measured_precision < self.precision_gate:
            return "below gate"
        return "enabled"


# Gates set at P0, before any results existed (EVAL.md anti-gaming rules).
# Stricter for readings we present as fact than for judgments we present as opinion.
FINDING_TYPES: dict[str, FindingTypeSpec] = {
    spec.type: spec
    for spec in (
        FindingTypeSpec(
            "exterior_damage",
            "Exterior damage",
            0.85,
            None,
            0,
            "A false dent call can talk a buyer out of a good car.",
        ),
        FindingTypeSpec(
            "rust_corrosion",
            "Rust and corrosion",
            0.85,
            None,
            0,
            "High stakes both ways: missing structural rust is dangerous, "
            "over-calling surface rust kills fair deals.",
        ),
        FindingTypeSpec(
            "repaint_indicator",
            "Repaint indicators",
            0.75,
            None,
            0,
            "Presented as a cue to ask about, not a conclusion, so a lower gate "
            "is honest as long as the copy stays hedged.",
        ),
        FindingTypeSpec(
            "tire_tread_estimate",
            "Tire tread estimate",
            0.80,
            None,
            0,
            "Cheap to verify in person; an error costs a buyer a question, not a car.",
        ),
        FindingTypeSpec(
            "interior_wear",
            "Interior wear",
            0.80,
            None,
            0,
            "Mostly cosmetic, but it feeds the odometer consistency check.",
        ),
        FindingTypeSpec(
            "fluid_leak_indicator",
            "Fluid leak indicators",
            0.75,
            None,
            0,
            "Residue is visible; its source and whether it is active are not. "
            "Ships as an observation to trace, never as a diagnosis.",
        ),
        FindingTypeSpec(
            "dash_warning_light",
            "Dash warning lights",
            0.90,
            None,
            0,
            "Presented as a fact about the photograph. A misread lamp is a "
            "direct factual error.",
        ),
        FindingTypeSpec(
            "odometer_reading",
            "Odometer reading",
            0.95,
            None,
            0,
            "A number the buyer will act on. OCR either reads it or it does not.",
        ),
        FindingTypeSpec(
            "odometer_wear_mismatch",
            "Odometer vs wear mismatch",
            0.80,
            None,
            0,
            "An accusation of odometer fraud is serious; it ships hedged, as a "
            "question, or not at all.",
        ),
        FindingTypeSpec(
            "audio_anomaly",
            "Engine audio anomaly",
            0.70,
            None,
            0,
            "Expected to be the weakest engine. Below gate it ships as a "
            "spectrogram with no claims attached (EVAL.md).",
        ),
        FindingTypeSpec(
            "vin_decode",
            "VIN decode",
            0.99,
            None,
            0,
            "A federal database lookup. Anything below near-perfect is a bug.",
        ),
        FindingTypeSpec(
            "open_recall",
            "Open recall",
            0.99,
            None,
            0,
            "Straight from NHTSA. Errors here would be ours, not the model's.",
        ),
        FindingTypeSpec(
            "complaint_pattern",
            "Complaint pattern",
            0.0,
            None,
            0,
            "A summary of public complaint volume, not a claim about this car. "
            "No precision gate applies; the honesty burden is on the wording.",
        ),
        FindingTypeSpec(
            "title_brand_indicator",
            "Title brand indicator",
            0.90,
            None,
            0,
            "Reads the buyer's own paperwork, so the arithmetic is exact and the "
            "risk is entirely in negation - 'Salvage: None' contains the word. A "
            "false salvage call talks a buyer out of a clean car, so the gate is "
            "set where a false positive is nearly unacceptable.",
        ),
        FindingTypeSpec(
            "price_comparison",
            "Price comparison",
            0.0,
            None,
            0,
            "Arithmetic on comps the user chose. Correctness is a unit-test "
            "question, not an eval question.",
        ),
        FindingTypeSpec(
            "documentation_gap",
            "Documentation gap",
            0.80,
            None,
            0,
            "Reads what the buyer uploaded and notes what is missing.",
        ),
    )
}


def _measured(path: Path = BENCH_RESULT_PATH) -> dict[str, tuple[float | None, int]]:
    """Precision and sample size per finding type, from the last bench run."""
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = (data.get("headline") or {}).get("by_type") or {}
    return {
        name: (row.get("precision"), int(row.get("n_predictions") or 0))
        for name, row in rows.items()
    }


def _with_measurements(
    specs: dict[str, FindingTypeSpec], path: Path = BENCH_RESULT_PATH
) -> dict[str, FindingTypeSpec]:
    measured = _measured(path)
    out: dict[str, FindingTypeSpec] = {}
    for key, spec in specs.items():
        precision, n = measured.get(key, (None, 0))
        out[key] = replace(spec, measured_precision=precision, n=n)
    return out


FINDING_TYPES = _with_measurements(FINDING_TYPES)


def enabled_types() -> set[str]:
    """Finding types currently permitted in a paid report."""
    return {k for k, v in FINDING_TYPES.items() if v.enabled_for_paid}


def withheld_types() -> dict[str, str]:
    """Types that have been measured and failed, with the sentence saying so.

    This is the half of LAW 4 that had no mechanism. `enabled_for_paid` was read
    by the gate table and by the accuracy statement - by things that *describe*
    the gate - and by nothing that enforces it, so a type measured at 0.60
    against a 0.85 threshold would have printed "NO / below gate" in the console
    while shipping in the paid dossier unchanged.

    Unmeasured types are deliberately not in here. "We have not measured this"
    and "we measured this and it failed" are different states, and D-032 settled
    the first one: every unmeasured type ships with a generated sentence saying
    none of them has cleared a threshold, on the teaser and above the payment
    button. Filtering on unmeasured would empty every report the product can
    currently produce while telling the buyer less than that sentence does.
    A measured failure has no such defence - the number exists and it is bad.
    See D-056 in DECISIONS.md.
    """
    out: dict[str, str] = {}
    for key, spec in FINDING_TYPES.items():
        if spec.measured_precision is None or spec.enabled_for_paid:
            continue
        out[key] = (
            f"{spec.label} findings are withheld from this report. Measured "
            f"precision {spec.measured_precision:.2f} on n={spec.n} against a "
            f"{spec.precision_gate:.2f} threshold ({spec.status})."
        )
    return out


def gate_status_table() -> str:
    """Rendered on every run so the gate is visible, not buried in a doc."""
    rows = ["  TYPE                      GATE  MEASURED     n  PAID  WHY"]
    for spec in FINDING_TYPES.values():
        measured = (
            "     -" if spec.measured_precision is None else f"{spec.measured_precision:>6.2f}"
        )
        flag = "yes" if spec.enabled_for_paid else " NO"
        rows.append(
            f"  {spec.type:<24} {spec.precision_gate:>5.2f}    {measured} "
            f"{spec.n:>5}   {flag}  {spec.status}"
        )
    return "\n".join(rows)
