"""The laws, tested as behaviour rather than trusted as prose.

If any test in this file fails, the correct response is to fix the code. It is
never to relax the test.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from tirekick_engines.models import (
    LOCKED_SYSTEM_STATEMENT,
    LOCKED_SYSTEMS,
    BoundingBox,
    CostBand,
    DraftFinding,
    Finding,
    ImageRegionEvidence,
    PriceDeduction,
    PriceRange,
    SystemRow,
)
from tirekick_engines.safety import apply_safety_law, is_locked, locked_system_rows


def _evidence() -> ImageRegionEvidence:
    return ImageRegionEvidence(
        asset_id="photo_01",
        box=BoundingBox(x=0.1, y=0.1, w=0.2, h=0.2),
        caption="a region of an actual image",
    )


def _draft(**overrides: object) -> DraftFinding:
    base: dict[str, object] = {
        "id": "d1",
        "type": "rust_corrosion",
        "system": "exterior",
        "title": "Corrosion visible",
        "detail": "Corrosion is visible along the rocker panel.",
        "severity": "major",
        "confidence": 0.7,
        "confidence_basis": "well-lit, unobstructed region",
        "evidence": [_evidence()],
        "engine": "vision",
    }
    base.update(overrides)
    return DraftFinding(**base)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# LAW 1 - truth                                                                #
# --------------------------------------------------------------------------- #


def test_truth_law_rejects_a_finding_with_no_evidence() -> None:
    with pytest.raises(ValidationError):
        _draft(evidence=[])


def test_truth_law_rejects_an_evidence_free_draft_too() -> None:
    """Even a draft must cite. There is no stage at which we hold an uncited claim."""
    with pytest.raises(ValidationError):
        DraftFinding(
            id="d",
            type="rust_corrosion",
            system="exterior",
            title="t",
            detail="d",
            severity="minor",
            confidence=0.5,
            confidence_basis="b",
            evidence=[],
            engine="vision",
        )


def test_truth_law_requires_a_stated_basis_for_confidence() -> None:
    with pytest.raises(ValidationError):
        _draft(confidence_basis="")


def test_truth_law_rejects_confidence_outside_zero_to_one() -> None:
    with pytest.raises(ValidationError):
        _draft(confidence=1.4)


def test_truth_law_rejects_a_box_past_the_image_edge() -> None:
    """Each coordinate can be legal while the box is not. A region that runs off
    the right of the photograph is a citation nobody can redraw."""
    with pytest.raises(ValidationError, match="image edge"):
        BoundingBox(x=0.8, y=0.1, w=0.3, h=0.2)
    with pytest.raises(ValidationError, match="image edge"):
        BoundingBox(x=0.1, y=0.9, w=0.2, h=0.5)


def test_a_box_flush_with_the_edge_is_still_a_box() -> None:
    BoundingBox(x=0.8, y=0.7, w=0.2, h=0.3)


def test_truth_law_rejects_an_inverted_cost_band() -> None:
    """'A shop quoted roughly $800 to $200' is not a range, it is a typo."""
    with pytest.raises(ValidationError, match="inverted"):
        CostBand(low=800, high=200)


def test_truth_law_rejects_an_inverted_price_range() -> None:
    with pytest.raises(ValidationError, match="inverted"):
        PriceRange(low=9000, high=7000)


def test_truth_law_rejects_an_inverted_price_deduction() -> None:
    with pytest.raises(ValidationError, match="inverted"):
        PriceDeduction(
            finding_id="f1",
            label="rust repair",
            low_usd=620,
            high_usd=380,
            basis="a band with its ends swapped",
        )


def test_a_single_point_band_is_allowed() -> None:
    CostBand(low=500, high=500)
    PriceRange(low=500, high=500)


# --------------------------------------------------------------------------- #
# LAW 2 - safety-critical                                                      #
# --------------------------------------------------------------------------- #


def test_locked_systems_are_exactly_the_four() -> None:
    assert frozenset({"brakes", "restraints", "structure", "steering"}) == LOCKED_SYSTEMS
    assert all(is_locked(s) for s in LOCKED_SYSTEMS)
    assert not is_locked("exterior")


def test_safety_law_drops_a_fabricated_all_clear() -> None:
    """The adversarial case. A confident, reassuring claim about a locked system.

    This is the exact output that would hurt someone, so it is the exact output
    the clamp exists to destroy.
    """
    drafts = [
        _draft(
            id="evil",
            system="brakes",
            title="Brake components appear to be in good condition",
            detail="The brakes look fine and show no signs of wear.",
            severity="info",
            confidence=0.99,
        )
    ]
    result = apply_safety_law(drafts)

    assert result.findings == []
    assert result.referrals == []
    assert any("dropped 'evil'" in line for line in result.clamp_log)


def test_safety_law_drops_an_all_clear_at_every_confidence() -> None:
    for confidence in (0.01, 0.5, 0.95, 1.0):
        result = apply_safety_law(
            [
                _draft(
                    id=f"c{confidence}",
                    system="steering",
                    severity="info",
                    confidence=confidence,
                )
            ]
        )
        assert result.findings == [], f"cleared steering at confidence {confidence}"


def test_safety_law_keeps_a_warning_as_a_referral() -> None:
    """D-005. Suppressing a warning would be its own kind of dishonesty."""
    drafts = [
        _draft(
            id="wet",
            system="brakes",
            title="Wet area near the front hub",
            detail="A wet area is visible on and around the front hub.",
            severity="major",
            confidence=0.55,
        )
    ]
    result = apply_safety_law(drafts)

    assert result.findings == []
    assert len(result.referrals) == 1

    referral = result.referrals[0]
    assert referral.system == "brakes"
    assert referral.evidence == drafts[0].evidence
    # The observation survives; the judgment does not.
    assert "wet area" in referral.observation.lower()
    assert not hasattr(referral, "severity")
    assert not hasattr(referral, "confidence")
    assert "mechanic" in referral.ask.lower()


@pytest.mark.parametrize("system", sorted(LOCKED_SYSTEMS))
def test_no_locked_system_ever_produces_a_finding(system: str) -> None:
    for severity in ("info", "minor", "major", "critical"):
        result = apply_safety_law(
            [_draft(id=f"{system}-{severity}", system=system, severity=severity)]
        )
        assert result.findings == [], f"{system}/{severity} leaked a finding"


def test_finding_model_refuses_a_locked_system_directly() -> None:
    """Belt and braces: even bypassing the clamp, the model will not hold it."""
    with pytest.raises(ValidationError, match="LAW 2"):
        Finding(
            id="f",
            type="rust_corrosion",
            system="brakes",
            title="t",
            detail="d",
            severity="minor",
            confidence=0.5,
            confidence_basis="b",
            evidence=[_evidence()],
            engine="vision",
        )


def test_locked_system_row_rejects_any_other_status() -> None:
    with pytest.raises(ValidationError, match="LAW 2"):
        SystemRow(system="brakes", status="no_issues_visible", statement="Brakes are fine.")


def test_locked_system_row_rejects_a_confidence() -> None:
    with pytest.raises(ValidationError, match="LAW 2"):
        SystemRow(
            system="steering",
            status="locked_mechanic_required",
            statement=LOCKED_SYSTEM_STATEMENT,
            confidence=0.9,
        )


def test_locked_system_row_rejects_a_paraphrase_of_the_statement() -> None:
    """The wording is fixed. A softened paraphrase is how a lock erodes."""
    with pytest.raises(ValidationError, match="LAW 2"):
        SystemRow(
            system="structure",
            status="locked_mechanic_required",
            statement="We could not really check the frame, probably worth a look.",
        )


def test_every_report_carries_all_four_locked_rows() -> None:
    rows = locked_system_rows()
    assert {r.system for r in rows} == LOCKED_SYSTEMS
    assert all(r.statement == LOCKED_SYSTEM_STATEMENT for r in rows)
    assert all(r.confidence is None for r in rows)
    assert all(r.finding_ids == [] for r in rows)


def test_unlocked_findings_pass_through_untouched() -> None:
    drafts = [_draft(id="ok", system="exterior")]
    result = apply_safety_law(drafts)
    assert len(result.findings) == 1
    assert result.findings[0].id == "ok"
    assert result.clamp_log == []
