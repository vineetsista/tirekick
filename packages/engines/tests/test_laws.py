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
from tirekick_engines.prompts import PROMPT_ROOT
from tirekick_engines.safety import (
    LOCKED_SYSTEM_LABELS,
    SELF_AUTHORED_ENGINES,
    apply_safety_law,
    is_locked,
    locked_system_rows,
)


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


def test_every_locked_system_has_a_name_to_call_it_by() -> None:
    """Two constants that must not drift apart.

    A referral now opens with the buyer-facing label for the system it concerns,
    looked up by key. Lock a fifth system without naming it and the clamp raises
    KeyError on the one draft it exists to handle - the report does not go out
    hedged, it does not go out at all."""
    assert set(LOCKED_SYSTEM_LABELS) == LOCKED_SYSTEMS


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
    """D-005. Suppressing a warning would be its own kind of dishonesty.

    This test used to assert `"wet area" in referral.observation` - that the
    model's own sentence was reprinted for the buyer. That assertion was the
    defect written down as a requirement: whatever the model wrote about a
    locked system went out verbatim, and nothing distinguished "a wet area is
    visible" from "the pads have plenty of life left". The referral still
    exists, still points at the same photograph, and still sends the buyer to a
    mechanic. What it no longer does is speak in the model's voice.
    """
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
    # The citation survives intact - same photograph, same box. That is what a
    # mechanic works from, and it is what a reader checks the claim against.
    assert [e.asset_id for e in referral.evidence] == ["photo_01"]  # type: ignore[union-attr]
    assert [e.box for e in referral.evidence] == [e.box for e in drafts[0].evidence]  # type: ignore[union-attr]
    assert not hasattr(referral, "severity")
    assert not hasattr(referral, "confidence")
    assert "mechanic" in referral.ask.lower()


def _shingles(text: str, n: int = 4) -> set[str]:
    """Every run of `n` consecutive words, lowercased.

    A test that only asserts `detail not in observation` passes the moment a
    refactor copies half the sentence instead of all of it. Comparing word runs
    catches the half.
    """
    words = text.lower().split()
    return {" ".join(words[i : i + n]) for i in range(len(words) - n + 1)}


#: A vision model's all-clear on brakes, written the way a careful one writes it:
#: hedged, specific, entirely reassuring, and tagged `minor` rather than `info`
#: because it did notice surface rust. Severity alone cannot see this.
_REASSURING_BRAKE_DETAIL = (
    "The visible brake rotors show only light surface rust and the pads appear "
    "to have plenty of life left. Nothing here suggests the braking system "
    "needs work."
)


def _reassuring_brake_draft() -> DraftFinding:
    return _draft(
        id="soft",
        system="brakes",
        title="Brake components appear serviceable",
        detail=_REASSURING_BRAKE_DETAIL,
        severity="minor",
        confidence=0.88,
        evidence=[
            ImageRegionEvidence(
                asset_id="photo_08",
                box=BoundingBox(x=0.6, y=0.58, w=0.24, h=0.2),
                caption="Rotor face, light surface rust only",
            )
        ],
    )


def test_a_model_sentence_about_a_locked_system_is_never_published() -> None:
    """The all-clear that used to walk straight through the clamp.

    `_is_adverse` reads `severity`, and severity is a label the same model chose.
    Tag the reassurance `minor` instead of `info` and it became a referral whose
    observation was the reassurance, word for word, printed under a heading that
    says a mechanic is required. That is a remotely-generated all-clear on
    brakes - the one output LAW 2 exists to make impossible.

    The fix is not a better classifier. It is that no sentence a model wrote
    about a locked system is published at all, so there is nothing left to
    classify.
    """
    draft = _reassuring_brake_draft()
    result = apply_safety_law([draft])

    assert result.findings == []
    assert len(result.referrals) == 1
    published = result.referrals[0].model_dump_json().lower()

    caption = draft.evidence[0].caption  # type: ignore[union-attr]
    for source in (draft.detail, draft.title, caption):
        for shingle in _shingles(source):
            assert shingle not in published, (
                f"the model's own words reached the buyer: {shingle!r} survives "
                f"in the referral"
            )

    # The words a buyer would read as clearance, checked one at a time as well -
    # a shingle check cannot see a single word lifted out of its sentence.
    for word in ("rotors", "rust", "pads", "serviceable", "suggests"):
        assert word not in published, f"{word!r} came from the model and was printed"


def test_the_referral_still_says_which_system_and_where_to_look() -> None:
    """D-017. Withholding the model's sentence must not turn into silence.

    Dropping the referral entirely, or emitting a blank one, would cost the
    buyer the car - they would never learn there was anything to look at. The
    referral names the locked system and names the media it was flagged in, both
    from fields this pipeline sets rather than from anything a model wrote.
    """
    result = apply_safety_law([_reassuring_brake_draft()])
    referral = result.referrals[0]

    assert "brakes" in referral.observation.lower()
    assert "photo_08" in referral.observation
    assert "mechanic" in referral.ask.lower()
    assert referral.evidence[0].asset_id == "photo_08"  # type: ignore[union-attr]


def test_prose_this_repository_wrote_itself_still_reaches_the_buyer() -> None:
    """The other half of the fix, and the reason it is keyed on provenance.

    The paperwork engine writes its own referrals - what the document said, what
    a branded title means, which agency to confirm it with. That text is in this
    repository, reviewed in a diff, and covered by the banned-language scan.
    Withholding it too would be the silent-drop failure of D-017 dressed up as
    caution: the buyer loses real, checkable advice and gains nothing.
    """
    detail = (
        "A document you uploaded reports frame or structural damage. Confirm the "
        "brand with your state's motor vehicle agency before you buy."
    )
    result = apply_safety_law(
        [
            _draft(
                id="title",
                type="title_brand_indicator",
                system="structure",
                title="Structural damage reported in your paperwork",
                detail=detail,
                severity="major",
                engine="data",
            )
        ]
    )
    assert result.referrals[0].observation == detail


def test_no_engine_that_talks_to_a_model_is_trusted_with_its_own_prose() -> None:
    """The allowlist is a claim; this is the thing that checks it.

    `SELF_AUTHORED_ENGINES` says "these engines write their own sentences". If
    someone gives one of them a prompt directory, that stops being true and the
    clamp starts republishing model text about brakes while still looking
    correct. Prompts live on disk one directory per model-facing engine
    (prompts/__init__.py), so the claim is checkable, and this fails the moment
    it stops holding.
    """
    for engine in SELF_AUTHORED_ENGINES:
        assert not (PROMPT_ROOT / engine).is_dir(), (
            f"{engine!r} is listed as writing its own prose but has prompts at "
            f"{PROMPT_ROOT / engine} - it talks to a model, so its drafts about a "
            f"locked system cannot be published verbatim"
        )
    assert "vision" not in SELF_AUTHORED_ENGINES


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
