"""The eval harness, tested on constructed cases.

There is no labeled photograph in this repository yet, so these are synthetic
scenarios. That is the point: the harness has to be known-correct *before* real
numbers run through it, because afterwards there is a strong incentive to find a
reason the scoring was too harsh.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tirekick_engines import bench
from tirekick_engines.models import BoundingBox
from tirekick_engines.registry import FINDING_TYPES, _with_measurements


def box(x: float, y: float, w: float, h: float) -> BoundingBox:
    return BoundingBox(x=x, y=y, w=w, h=h)


def prediction(
    asset: str = "photo_01",
    type_: str = "rust_corrosion",
    b: BoundingBox | None = None,
    confidence: float = 0.8,
    finding_id: str = "f1",
    severity: str | None = None,
) -> bench.Prediction:
    return bench.Prediction(
        asset_id=asset,
        type=type_,
        box=b or box(0.1, 0.1, 0.2, 0.2),
        confidence=confidence,
        finding_id=finding_id,
        severity=severity,
    )


def label(
    asset: str = "photo_01",
    type_: str = "rust_corrosion",
    b: BoundingBox | None = None,
    severity: str | None = None,
) -> bench.Label:
    return bench.Label(
        asset_id=asset,
        type=type_,
        box=b or box(0.1, 0.1, 0.2, 0.2),
        severity=severity,
    )


# --------------------------------------------------------------------------- #
# geometry                                                                     #
# --------------------------------------------------------------------------- #


def test_identical_boxes_have_iou_one() -> None:
    assert bench.iou(box(0.1, 0.1, 0.2, 0.2), box(0.1, 0.1, 0.2, 0.2)) == pytest.approx(1.0)


def test_disjoint_boxes_have_iou_zero() -> None:
    assert bench.iou(box(0, 0, 0.1, 0.1), box(0.5, 0.5, 0.1, 0.1)) == 0.0


def test_touching_boxes_do_not_overlap() -> None:
    assert bench.iou(box(0, 0, 0.2, 0.2), box(0.2, 0, 0.2, 0.2)) == 0.0


def test_half_overlap_is_one_third() -> None:
    """Two unit squares sharing half their area: 0.5 / 1.5."""
    value = bench.iou(box(0, 0, 0.2, 0.2), box(0.1, 0, 0.2, 0.2))
    assert value == pytest.approx(1 / 3)


# --------------------------------------------------------------------------- #
# matching                                                                     #
# --------------------------------------------------------------------------- #


def test_a_matching_box_is_a_true_positive() -> None:
    result = bench.score([prediction()], [label()])
    entry = result.by_type["rust_corrosion"]
    assert (entry.true_positives, entry.false_positives, entry.false_negatives) == (1, 0, 0)
    assert entry.precision == 1.0
    assert entry.recall == 1.0


def test_two_predictions_on_one_label_score_one_hit_and_one_miss() -> None:
    """Boxing the same dent twice is not twice as right.

    Without single-claim matching, a model that carpets an image in overlapping
    boxes scores perfect precision, which is the easiest way to game this.
    """
    result = bench.score(
        [
            prediction(confidence=0.9, finding_id="a"),
            prediction(confidence=0.5, finding_id="b"),
        ],
        [label()],
    )
    entry = result.by_type["rust_corrosion"]
    assert (entry.true_positives, entry.false_positives) == (1, 1)
    assert entry.precision == 0.5


def test_the_more_confident_prediction_claims_the_label() -> None:
    high = prediction(confidence=0.9, finding_id="high")
    low = prediction(confidence=0.2, finding_id="low", b=box(0.11, 0.11, 0.2, 0.2))
    result = bench.score([low, high], [label()])
    assert result.by_type["rust_corrosion"].true_positives == 1


def test_a_prediction_where_nothing_is_labeled_is_a_false_positive() -> None:
    """The eval set must contain photographs whose right answer is silence, or it
    measures enthusiasm rather than precision."""
    result = bench.score([prediction()], [], evaluated_assets={"photo_01"})
    entry = result.by_type["rust_corrosion"]
    assert (entry.true_positives, entry.false_positives) == (0, 1)
    assert entry.precision == 0.0


def test_a_prediction_on_an_unlabeled_asset_is_ignored_entirely() -> None:
    """Nobody looked at that photo, so we do not know it is wrong."""
    result = bench.score([prediction(asset="photo_99")], [], evaluated_assets={"photo_01"})
    assert result.by_type == {}


def test_a_missed_label_is_a_false_negative() -> None:
    result = bench.score([], [label()], evaluated_assets={"photo_01"})
    entry = result.by_type["rust_corrosion"]
    assert (entry.true_positives, entry.false_negatives) == (0, 1)
    assert entry.recall == 0.0
    # No positive predictions, so precision is undefined rather than zero.
    assert entry.precision is None


def test_the_right_box_with_the_wrong_type_is_not_a_hit() -> None:
    result = bench.score([prediction(type_="exterior_damage")], [label(type_="rust_corrosion")])
    assert result.by_type["exterior_damage"].false_positives == 1
    assert result.by_type["rust_corrosion"].false_negatives == 1


def test_the_right_box_on_the_wrong_photo_is_not_a_hit() -> None:
    result = bench.score(
        [prediction(asset="photo_01")],
        [label(asset="photo_02")],
        evaluated_assets={"photo_01", "photo_02"},
    )
    assert result.by_type["rust_corrosion"].true_positives == 0


# --------------------------------------------------------------------------- #
# thresholds - D-008                                                           #
# --------------------------------------------------------------------------- #


def test_a_loose_box_matches_at_the_headline_threshold_and_not_at_the_strict_one() -> None:
    """D-008 in one test. The published pair of numbers is exactly this gap."""
    # Two 0.2-wide boxes offset by 0.076 overlap at about 0.45: the box is on the
    # right part of the car and is not tight around it.
    loose = prediction(b=box(0.176, 0.10, 0.2, 0.2))
    assert bench.HEADLINE_IOU <= bench.iou(loose.box, label().box) < bench.STRICT_IOU

    headline = bench.score([loose], [label()], threshold=bench.HEADLINE_IOU)
    strict = bench.score([loose], [label()], threshold=bench.STRICT_IOU)

    assert headline.by_type["rust_corrosion"].true_positives == 1
    assert strict.by_type["rust_corrosion"].true_positives == 0


def test_the_thresholds_are_the_ones_fixed_in_p0() -> None:
    """Changing these changes what every published number means."""
    assert bench.HEADLINE_IOU == 0.4
    assert bench.STRICT_IOU == 0.5


# --------------------------------------------------------------------------- #
# locked systems - LAW 2                                                       #
# --------------------------------------------------------------------------- #


def test_locked_system_referrals_are_counted_and_never_scored() -> None:
    """We said in writing we cannot assess these from a photograph. Scoring them
    would mean asserting ground truth we have disclaimed."""
    result = bench.score([], [], unscored_referrals=4)
    assert result.unscored_referrals == 4
    assert result.by_type == {}


# --------------------------------------------------------------------------- #
# end to end                                                                   #
# --------------------------------------------------------------------------- #


def _write_label_file(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "assets": {
                    "photo_01": {
                        "labels": [
                            {
                                "type": "rust_corrosion",
                                "box": {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2},
                                "note": "rocker panel",
                                "severity": "minor",
                            }
                        ]
                    },
                    # Labeled, and correctly empty. This is what makes a false
                    # positive countable.
                    "photo_02": {"labels": []},
                }
            }
        ),
        encoding="utf-8",
    )


def _write_report_file(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "findings": [
                    {
                        "id": "f1",
                        "type": "rust_corrosion",
                        "confidence": 0.8,
                        "severity": "major",
                        "evidence": [
                            {
                                "kind": "image_region",
                                "assetId": "photo_01",
                                "box": {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2},
                                "caption": "rust",
                            }
                        ],
                    },
                    {
                        "id": "f2",
                        "type": "rust_corrosion",
                        "confidence": 0.6,
                        "severity": "critical",
                        "evidence": [
                            {
                                "kind": "image_region",
                                "assetId": "photo_02",
                                "box": {"x": 0.5, "y": 0.5, "w": 0.1, "h": 0.1},
                                "caption": "not rust",
                            }
                        ],
                    },
                ],
                "mechanicReferrals": [{"id": "r1", "system": "brakes"}],
            }
        ),
        encoding="utf-8",
    )


def test_a_full_run_scores_reports_against_labels(tmp_path: Path) -> None:
    labels_dir = tmp_path / "labels"
    reports_dir = tmp_path / "reports"
    labels_dir.mkdir()
    reports_dir.mkdir()
    _write_label_file(labels_dir / "capture-01.json")
    _write_report_file(reports_dir / "capture-01.report.json")

    result = bench.run(labels_dir, reports_dir)
    rust = result["headline"]["by_type"]["rust_corrosion"]

    assert rust["true_positives"] == 1
    assert rust["false_positives"] == 1  # the call on the correctly-empty photo
    assert rust["precision"] == 0.5
    assert rust["recall"] == 1.0
    assert result["headline"]["assets_evaluated"] == 2
    assert result["headline"]["unscored_referrals"] == 1
    assert "TYPE" in bench.render(result)


# --------------------------------------------------------------------------- #
# the gate reads the result - LAW 4                                            #
# --------------------------------------------------------------------------- #


def test_the_gate_reads_measurements_from_the_bench_file(tmp_path: Path) -> None:
    """There is no second place to type a precision figure."""
    results = tmp_path / "latest.json"
    results.write_text(
        json.dumps(
            {
                "headline": {
                    "by_type": {"rust_corrosion": {"precision": 0.91, "n_predictions": 120}}
                }
            }
        ),
        encoding="utf-8",
    )
    specs = _with_measurements(FINDING_TYPES, results)

    rust = specs["rust_corrosion"]
    assert rust.measured_precision == 0.91
    assert rust.n == 120
    assert rust.enabled_for_paid is True
    assert rust.status == "enabled"

    # Everything else stays unmeasured rather than inheriting anything.
    assert specs["exterior_damage"].measured_precision is None
    assert specs["exterior_damage"].enabled_for_paid is False


def test_a_high_score_on_a_small_sample_still_does_not_ship(tmp_path: Path) -> None:
    """D-018. Five out of five is not evidence."""
    results = tmp_path / "latest.json"
    results.write_text(
        json.dumps(
            {"headline": {"by_type": {"vin_decode": {"precision": 1.0, "n_predictions": 5}}}}
        ),
        encoding="utf-8",
    )
    spec = _with_measurements(FINDING_TYPES, results)["vin_decode"]

    assert spec.measured_precision == 1.0
    assert spec.enabled_for_paid is False
    assert "n too small" in spec.status


def test_a_missing_bench_file_means_unmeasured_not_zero(tmp_path: Path) -> None:
    specs = _with_measurements(FINDING_TYPES, tmp_path / "nope.json")
    assert all(s.measured_precision is None for s in specs.values())
    assert all(not s.enabled_for_paid for s in specs.values())


# --------------------------------------------------------------------------- #
# F1 - promised since P0, computed since P10                                   #
# --------------------------------------------------------------------------- #


def type_score(tp: int = 0, fp: int = 0, fn: int = 0) -> bench.TypeScore:
    return bench.TypeScore(
        type="rust_corrosion", true_positives=tp, false_positives=fp, false_negatives=fn
    )


def test_f1_is_the_harmonic_mean_and_not_the_arithmetic_one() -> None:
    """A model that finds one dent in fifty and is certain about that one.

    Precision 1.00, recall 0.02. The arithmetic mean is 0.51 and describes a
    respectable system; the harmonic mean is 0.04 and describes this one. The
    difference is the entire reason F1 is the metric and not "the average".
    """
    score = type_score(tp=1, fp=0, fn=49)
    assert score.precision == 1.0
    assert score.recall == pytest.approx(0.02)

    f1 = score.f1
    assert f1 is not None
    assert f1 == pytest.approx(2 * 1.0 * 0.02 / 1.02)
    assert f1 < 0.05
    assert f1 != pytest.approx((1.0 + 0.02) / 2)


def test_an_unmeasured_f1_is_none_and_a_measured_failure_is_zero() -> None:
    """Two different sentences that must not print as the same number.

    "We have no predictions of this type" and "we made predictions and every one
    was wrong" are not the same state. Collapsing the first into 0.0 publishes a
    terrible score for a type nobody has tested; promoting the second to None
    hides a real failure behind "not measured", which is this repository's
    favourite place to hide.
    """
    # No predictions: precision does not exist, so F1 does not exist.
    assert type_score(tp=0, fp=0, fn=3).f1 is None
    # No labels: recall does not exist, so F1 does not exist.
    assert type_score(tp=0, fp=5, fn=0).f1 is None
    # Both exist and we got nothing right. That is a zero, and it is real.
    assert type_score(tp=0, fp=5, fn=3).f1 == 0.0


def test_macro_f1_ships_with_the_types_it_averaged() -> None:
    """A macro over 2 of 16 types reads as a system score unless it names them.

    Two types with an F1 and one without: the mean must be over the two, and the
    payload must say which two, because "F1 0.90" and "F1 0.90 across
    rust_corrosion and vin_decode, 2 types" invite completely different beliefs
    about what has been measured.
    """
    result = bench.BenchResult(iou=bench.HEADLINE_IOU)
    result.by_type["rust_corrosion"] = bench.TypeScore("rust_corrosion", 3, 1, 1)
    result.by_type["vin_decode"] = bench.TypeScore("vin_decode", 1, 1, 1)
    # Predictions but no labels: no recall, so no F1, so it is not in the mean.
    result.by_type["interior_wear"] = bench.TypeScore("interior_wear", 0, 4, 0)

    macro = result.macro_f1()
    rust = result.by_type["rust_corrosion"].f1
    vin = result.by_type["vin_decode"].f1
    assert rust is not None and vin is not None
    assert macro["f1_macro"] == pytest.approx((rust + vin) / 2)
    assert macro["f1_macro_types"] == ["rust_corrosion", "vin_decode"]
    assert macro["f1_macro_n_types"] == 2
    assert "interior_wear" not in macro["f1_macro_types"]


def test_macro_f1_on_an_empty_run_is_none_and_does_not_raise() -> None:
    """The mean of no numbers is not zero, and it is not an exception either.

    statistics.mean([]) raises and sum([])/len([]) divides by zero; both would
    take the harness down on the eval set this project actually has. 0.0 is worse
    than either, because it is a score.
    """
    macro = bench.BenchResult(iou=bench.HEADLINE_IOU).macro_f1()
    assert macro["f1_macro"] is None
    assert macro["f1_macro_types"] == []
    assert macro["f1_macro_n_types"] == 0


# --------------------------------------------------------------------------- #
# precision at high confidence                                                 #
# --------------------------------------------------------------------------- #


def test_the_high_confidence_threshold_is_the_one_written_down_at_p0() -> None:
    """docs/EVAL.md has said ">= 0.8" since before there was anything to score.

    A threshold chosen after seeing a run is a threshold chosen to flatter it.
    """
    assert bench.HIGH_CONFIDENCE == 0.80


def test_precision_at_high_confidence_ignores_sub_threshold_findings() -> None:
    """The number is about the findings the report puts at the top of the page."""
    hit = prediction(confidence=0.9, finding_id="hit")
    miss = prediction(
        asset="photo_02", confidence=0.5, finding_id="miss", b=box(0.5, 0.5, 0.1, 0.1)
    )
    assets = {"photo_01", "photo_02"}

    overall = bench.score([hit, miss], [label()], evaluated_assets=assets)
    assert overall.by_type["rust_corrosion"].precision == 0.5

    high = bench.score(
        [p for p in [hit, miss] if bench.clears_high_confidence(p)],
        [label()],
        evaluated_assets=assets,
    )
    block = bench.high_confidence_block(high)
    assert block["n_predictions"] == 1
    assert block["precision"] == 1.0


def test_a_confidence_of_exactly_the_threshold_is_included() -> None:
    """`>` instead of `>=` silently drops the boundary case.

    0.8 is a value models emit constantly, and excluding it would quietly shrink
    the population of the number EVAL.md calls the one that matters most - a
    change nothing in the output would announce.
    """
    exact = prediction(confidence=0.80, finding_id="exact", b=box(0.5, 0.5, 0.1, 0.1))
    assert bench.clears_high_confidence(exact) is True
    assert bench.clears_high_confidence(prediction(confidence=0.7999)) is False

    high = bench.score(
        [p for p in [exact] if bench.clears_high_confidence(p)],
        [],
        evaluated_assets={"photo_01"},
    )
    block = bench.high_confidence_block(high)
    assert block["n_predictions"] == 1
    assert block["precision"] == 0.0


def test_the_high_confidence_block_publishes_no_recall_anywhere() -> None:
    """Recall over a confidence-filtered set is not this system's recall.

    A real dent found only by a 0.5-confidence prediction becomes a false
    negative the moment the filter is applied. The resulting number would be
    lower than the system's recall for reasons that have nothing to do with what
    the system missed, and it would still be read as recall. F1 goes with it,
    because F1 is half recall.
    """
    high = bench.score([prediction(confidence=0.9)], [label()])
    block = bench.high_confidence_block(high)

    assert block["recall"] is None
    assert block["f1"] is None
    assert "recall" in block["_recall_note"]
    for row in block["by_type"].values():
        assert row["recall"] is None
        assert row["f1"] is None
        # The ingredients of a recall are not published here either.
        assert "false_negatives" not in row
        assert "n_labels" not in row


def test_precision_at_high_confidence_is_null_when_nothing_clears() -> None:
    """0/0 guarded to 1.0 reads as "we were right about all zero of them"."""
    high = bench.score(
        [p for p in [prediction(confidence=0.5)] if bench.clears_high_confidence(p)],
        [label()],
        evaluated_assets={"photo_01"},
    )
    block = bench.high_confidence_block(high)
    assert block["n_predictions"] == 0
    assert block["precision"] is None


# --------------------------------------------------------------------------- #
# severity confusion matrix                                                    #
# --------------------------------------------------------------------------- #


def test_the_severity_vocabulary_is_the_codes_ordered_by_seriousness() -> None:
    """docs/EVAL.md promises {cosmetic, moderate, significant} and is wrong.

    That vocabulary matches nothing in the code. The order here is not cosmetic
    either: it is the ordinal scale that decides whether a disagreement was an
    over-call or an under-call, so reversing it inverts every ethical claim the
    matrix makes.
    """
    assert bench.SEVERITY_VOCABULARY == ("info", "minor", "major", "critical")


def test_a_severity_disagreement_on_a_matched_box_is_still_a_true_positive() -> None:
    """Finding the rust and mis-grading it is one success and one failure.

    If severity were a match criterion, the same event would be scored as a false
    positive *and* a false negative, detection precision would fall for a reason
    that has nothing to do with detection, and the grading error would vanish
    into the detection numbers where nobody could see it.
    """
    result = bench.score([prediction(severity="critical")], [label(severity="minor")])
    entry = result.by_type["rust_corrosion"]
    assert (entry.true_positives, entry.false_positives, entry.false_negatives) == (1, 0, 0)

    block = bench.severity_confusion(result.matches)
    assert block["n_matched"] == 1
    assert block["over_called"] == 1


def test_the_matrix_reads_labelled_first_and_predicted_second() -> None:
    """Transposed, over-calling reads as under-calling.

    We said critical, the human said minor: that is a finding that talks a buyer
    out of a good car (D-017). The transpose says we were the cautious ones. This
    is the single number in the file where getting the direction backwards
    inverts the claim about who the product hurts.
    """
    result = bench.score([prediction(severity="critical")], [label(severity="minor")])
    block = bench.severity_confusion(result.matches)

    assert block["matrix"]["minor"]["critical"] == 1
    assert block["matrix"]["critical"]["minor"] == 0
    assert (block["exact"], block["over_called"], block["under_called"]) == (0, 1, 0)
    assert "labelled" in block["_orientation"]


def test_under_calling_is_counted_as_the_other_failure() -> None:
    """The other direction, which sells the buyer a bad car instead."""
    result = bench.score([prediction(severity="minor")], [label(severity="critical")])
    block = bench.severity_confusion(result.matches)

    assert block["matrix"]["critical"]["minor"] == 1
    assert (block["exact"], block["over_called"], block["under_called"]) == (0, 0, 1)


def test_only_matched_findings_enter_the_severity_matrix() -> None:
    """A false positive has no labelled severity; a false negative has no called one.

    Letting either in turns a detection error into a grading error, and the
    grading numbers then move whenever detection moves.
    """
    result = bench.score(
        [prediction(asset="photo_02", severity="major", b=box(0.5, 0.5, 0.1, 0.1))],
        [label(asset="photo_01", severity="major")],
        evaluated_assets={"photo_01", "photo_02"},
    )
    entry = result.by_type["rust_corrosion"]
    assert (entry.false_positives, entry.false_negatives) == (1, 1)

    block = bench.severity_confusion(result.matches)
    assert block["n_matched"] == 0
    assert all(sum(row.values()) == 0 for row in block["matrix"].values())


def test_a_missing_labelled_severity_is_counted_missing_and_never_imputed() -> None:
    """Filling the human's blank with our own answer scores us against ourselves.

    An unlabelled severity is a hole in the ground truth. Treating our prediction
    as the label there produces exact agreement out of nothing, and the more
    severities the labeler skips the better we look.
    """
    result = bench.score([prediction(severity="major")], [label(severity=None)])
    block = bench.severity_confusion(result.matches)

    assert block["n_matched"] == 1
    assert block["n_matched_with_label_severity"] == 0
    assert block["n_matched_missing_label_severity"] == 1
    assert block["n_scored"] == 0
    assert block["exact"] == 0
    assert block["matrix"]["major"]["major"] == 0
    assert block["exact_rate"] is None


def test_an_unrecognised_severity_string_is_a_hard_error(tmp_path: Path) -> None:
    """Silently reading a typo as None would shrink the matrix without saying so.

    The pairs that survived would then be the ones spelled correctly, and the
    agreement rate over that subset is a cleaner number with nothing announcing
    that it is a subset. Missing is a state; misspelled is a mistake.
    """
    (tmp_path / "capture-01.json").write_text(
        json.dumps(
            {
                "assets": {
                    "photo_01": {
                        "labels": [
                            {
                                "type": "rust_corrosion",
                                "box": {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2},
                                # EVAL.md's vocabulary, which the code does not have.
                                "severity": "significant",
                            }
                        ]
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="significant"):
        bench.load_labels(tmp_path)


def test_severity_rates_are_null_not_perfect_when_nothing_matched() -> None:
    """exact / max(n, 1) is 1.0 on an empty set: flawless agreement with nobody."""
    block = bench.severity_confusion([])
    assert block["n_matched"] == 0
    assert block["exact_rate"] is None
    assert block["over_called_rate"] is None
    assert block["under_called_rate"] is None


# --------------------------------------------------------------------------- #
# calibration                                                                  #
# --------------------------------------------------------------------------- #


def judgement(confidence: float, correct: bool) -> bench.Judgement:
    return bench.Judgement(
        prediction=prediction(confidence=confidence),
        label=label() if correct else None,
    )


def test_a_confidence_lands_in_the_bin_its_value_names() -> None:
    """A bin boundary belongs to the bin above it, and 0.7 is a boundary.

    Half-open the other way - `<=` instead of `<` on the upper edge - puts 0.7 in
    the [0.6,0.7) row, and every round number a model likes to emit shifts down
    one bin with it. Nothing in the output would look wrong; the reliability
    table would simply describe a slightly different model than the one that ran.
    """
    block = bench.calibration([judgement(0.7, True)])
    assert block["bins"][7]["n"] == 1
    assert block["bins"][7]["lo"] == pytest.approx(0.7)
    assert block["bins"][6]["n"] == 0

    lower = bench.calibration([judgement(0.3, True)])
    assert lower["bins"][3]["n"] == 1
    assert lower["bins"][2]["n"] == 0


def test_a_confidence_of_one_lands_in_the_last_bin() -> None:
    """The most confident finding a model can emit is the worst one to drop.

    int(1.0 * 10) is 10, one past the end of a ten-element list, so with ten
    half-open bins the single prediction most worth checking against reality
    goes uncounted - and the bins stop summing to n with nothing saying so.
    """
    block = bench.calibration([judgement(1.0, False)])
    assert block["bins"][9]["n"] == 1
    assert block["bins"][9]["closed"] is True
    assert block["n"] == 1
    assert sum(row["n"] for row in block["bins"]) == 1


def test_an_overconfident_bin_shows_a_positive_gap() -> None:
    """Said 0.90, right half the time. The sign is the finding.

    A reader who has to work out which way round the subtraction went will guess,
    and half of them will guess that this model is modest.
    """
    block = bench.calibration([judgement(0.9, True)] * 2 + [judgement(0.9, False)] * 2)
    row = block["bins"][9]
    assert row["n"] == 4
    assert row["observed_precision"] == 0.5
    assert row["mean_confidence"] == pytest.approx(0.9)
    assert row["gap"] == pytest.approx(0.4)
    assert "OVERCONFIDENT" in block["_gap_sign"]


def test_an_underconfident_bin_shows_a_negative_gap() -> None:
    """The other sign, so the convention is pinned from both directions."""
    block = bench.calibration([judgement(0.5, True), judgement(0.5, True)])
    row = block["bins"][5]
    assert row["observed_precision"] == 1.0
    assert row["gap"] == pytest.approx(-0.5)


def test_an_empty_bin_is_null_and_not_zero() -> None:
    """A bin nobody predicted into is not a bin where we were wrong every time.

    Zero observed precision in an empty bin also feeds a gap equal to the bin's
    confidence, which would print as the most overconfident row on the page.
    """
    block = bench.calibration([judgement(0.9, True)])
    empty = block["bins"][0]
    assert empty["n"] == 0
    assert empty["observed_precision"] is None
    assert empty["mean_confidence"] is None
    assert empty["gap"] is None


def test_expected_calibration_error_is_none_on_an_empty_run_not_zero() -> None:
    """The worst number this file could publish.

    ECE written as an accumulator that starts at 0.0 and is never divided comes
    out as 0.0 on a run with nothing in it, and 0.0 is the value that means
    perfectly calibrated. A model that has never been run would be documented as
    the best-calibrated model we have ever measured.
    """
    block = bench.calibration([])
    assert block["expected_calibration_error"] is None
    assert block["n"] == 0
    assert block["bins_populated"] == 0


def test_expected_calibration_error_is_population_weighted() -> None:
    """Ninety findings off by 0.1 and ten off by 0.5 is 0.14, not 0.30.

    The unweighted mean over populated bins lets a bin holding one prediction
    push the headline calibration number as hard as a bin holding hundreds -
    usually a sparse, extreme bin, and usually in the direction that makes a
    well-behaved model look erratic or an erratic one look fine.
    """
    big = [judgement(0.9, True)] * 72 + [judgement(0.9, False)] * 18  # gap 0.1
    small = [judgement(0.6, True)] * 1 + [judgement(0.6, False)] * 9  # gap 0.5
    block = bench.calibration(big + small)

    assert block["bins"][9]["gap"] == pytest.approx(0.1)
    assert block["bins"][6]["gap"] == pytest.approx(0.5)
    assert block["n"] == 100
    assert block["bins_populated"] == 2
    assert block["expected_calibration_error"] == pytest.approx(0.14)
    assert block["expected_calibration_error"] != pytest.approx(0.30)


def test_only_judged_predictions_are_calibrated(tmp_path: Path) -> None:
    """A prediction on a photo nobody labelled belongs in no bin.

    Counted as incorrect it would make us look wildly overconfident; counted as
    correct it would make us look perfect. It is neither - we do not know what is
    in that photograph, which is the same reason it is not a false positive.
    """
    labels_dir = tmp_path / "labels"
    reports_dir = tmp_path / "reports"
    labels_dir.mkdir()
    reports_dir.mkdir()
    _write_label_file(labels_dir / "capture-01.json")
    reports_dir.joinpath("capture-01.report.json").write_text(
        json.dumps(
            {
                "findings": [
                    {
                        "id": "f9",
                        "type": "rust_corrosion",
                        "confidence": 0.95,
                        "severity": "major",
                        "evidence": [
                            {
                                "kind": "image_region",
                                "assetId": "photo_99",
                                "box": {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2},
                                "caption": "nobody looked at this photo",
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = bench.run(labels_dir, reports_dir)
    assert result["calibration"]["n"] == 0
    assert result["calibration"]["bins"][9]["n"] == 0
    assert result["calibration"]["expected_calibration_error"] is None


# --------------------------------------------------------------------------- #
# determinism                                                                  #
# --------------------------------------------------------------------------- #


def test_two_equally_confident_predictions_resolve_the_same_way_every_run() -> None:
    """Four derived metrics now depend on which box claimed which label.

    With confidence as the only sort key, two findings tied at 0.9 were ordered
    by however the reports happened to be read, so the true positive - and the
    severity it contributes to the matrix - moved between runs on identical data.
    """
    first = prediction(confidence=0.9, finding_id="aaa")
    second = prediction(confidence=0.9, finding_id="bbb", b=box(0.11, 0.11, 0.2, 0.2))

    forward = bench.score([first, second], [label()])
    backward = bench.score([second, first], [label()])

    winners = {tuple(j.prediction.finding_id for j in r.matches) for r in (forward, backward)}
    assert winners == {("aaa",)}


def test_the_strictly_best_overlap_wins_a_tie_rather_than_the_last_one() -> None:
    """Two labels on the same box, and the file order decided the severity.

    Matching on `>=` handed the label to whichever tying candidate was listed
    last, so a run could report an under-call against the second label where the
    first was an exact agreement - a grading error manufactured by label order.
    """
    labels = [label(severity="minor"), label(severity="critical")]
    result = bench.score([prediction(severity="minor")], labels)
    block = bench.severity_confusion(result.matches)

    assert block["matrix"]["minor"]["minor"] == 1
    assert block["exact"] == 1
    assert block["under_called"] == 0


# --------------------------------------------------------------------------- #
# the refusal - this is what the file actually contains today                  #
# --------------------------------------------------------------------------- #


def test_an_empty_run_refuses_instead_of_reporting(tmp_path: Path) -> None:
    """Nothing in, and every rate null rather than flattering.

    Three of the four metrics added in P10 evaluate to a perfect score on an
    empty set if written the obvious way: precision at high confidence 1.00,
    severity agreement 1.00, calibration error 0.00. This is the state the
    project is actually in, so this is the test that matters.
    """
    labels_dir = tmp_path / "labels"
    reports_dir = tmp_path / "reports"
    labels_dir.mkdir()
    reports_dir.mkdir()

    result = bench.run(labels_dir, reports_dir)

    assert result["scored"] is False
    assert result["refusal"] == (
        "Not a measurement. 0 labeled assets, 0 labels, 0 judged predictions "
        "on the eval set. No figure in this file is a result."
    )
    assert result["headline"]["f1_macro"] is None
    assert result["high_confidence"]["precision"] is None
    assert result["high_confidence"]["recall"] is None
    assert result["severity_confusion"]["exact_rate"] is None
    assert result["calibration"]["expected_calibration_error"] is None


def test_render_prints_the_refusal_and_not_a_table_of_dashes(tmp_path: Path) -> None:
    """A table of dashes is still a table, and a screenshot of one is a claim.

    The refusal has to occupy the place a reader looks for the result, or the
    output still reads as a report card with the grades not yet filled in.
    """
    labels_dir = tmp_path / "labels"
    reports_dir = tmp_path / "reports"
    labels_dir.mkdir()
    reports_dir.mkdir()

    out = bench.render(bench.run(labels_dir, reports_dir))

    assert "NOT A MEASUREMENT" in out
    assert "No figure in this file is a result." in out
    assert "TYPE" not in out
    assert "PRECISION" not in out
    assert "ECE" not in out
    assert "0.00" not in out
    assert "1.00" not in out


def test_the_committed_bench_result_is_a_refusal() -> None:
    """The file on disk, not a constructed one.

    docs/ACCURACY.md and the gate table read this exact file, and the four zeros
    say it has never scored anything. If it ever stops being a refusal without an
    eval set landing in the same commit, something has written a number into it.
    """
    path = Path(__file__).resolve().parents[3] / "bench" / "results" / "latest.json"
    data = json.loads(path.read_text(encoding="utf-8"))

    assert data["scored"] is False
    assert data["refusal"].startswith("Not a measurement.")
    assert data["headline"]["f1_macro"] is None
    assert data["headline"]["by_type"] == {}
    assert data["high_confidence"]["precision"] is None
    assert data["high_confidence"]["recall"] is None
    assert data["severity_confusion"]["exact_rate"] is None
    assert data["severity_confusion"]["n_matched"] == 0
    assert data["calibration"]["expected_calibration_error"] is None
    assert data["calibration"]["n"] == 0


# --------------------------------------------------------------------------- #
# the derived metrics on a run that does have something in it                  #
# --------------------------------------------------------------------------- #


def test_a_full_run_reports_all_four_derived_metrics(tmp_path: Path) -> None:
    """One hit at 0.8 called major against a minor label, one miss at 0.6."""
    labels_dir = tmp_path / "labels"
    reports_dir = tmp_path / "reports"
    labels_dir.mkdir()
    reports_dir.mkdir()
    _write_label_file(labels_dir / "capture-01.json")
    _write_report_file(reports_dir / "capture-01.report.json")

    result = bench.run(labels_dir, reports_dir)

    assert result["scored"] is True
    assert result["refusal"] is None

    # F1: precision 0.5, recall 1.0.
    rust = result["headline"]["by_type"]["rust_corrosion"]
    assert rust["f1"] == pytest.approx(2 / 3)
    assert result["headline"]["f1_macro"] == pytest.approx(2 / 3)
    assert result["headline"]["f1_macro_types"] == ["rust_corrosion"]

    # Only the 0.8 finding clears the high-confidence filter, and it was right.
    assert result["high_confidence"]["n_predictions"] == 1
    assert result["high_confidence"]["precision"] == 1.0

    # We called the matched rust major; the human wrote minor.
    assert result["severity_confusion"]["matrix"]["minor"]["major"] == 1
    assert result["severity_confusion"]["over_called"] == 1
    assert result["severity_confusion"]["exact_rate"] == 0.0

    # 0.8 correct, 0.6 wrong: |0.8-1.0|/2 + |0.6-0.0|/2.
    assert result["calibration"]["n"] == 2
    assert result["calibration"]["expected_calibration_error"] == pytest.approx(0.4)

    rendered = bench.render(result)
    assert "Macro F1" in rendered
    assert "SEVERITY" in rendered
    assert "CALIBRATION" in rendered


# --------------------------------------------------------------------------- #
# the new metrics must not change what ships - LAW 4                           #
# --------------------------------------------------------------------------- #


def _gate_file(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "latest.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_a_flattering_f1_and_p_at_high_confidence_do_not_open_the_gate(
    tmp_path: Path,
) -> None:
    """The gate is overall precision and stays overall precision.

    P@0.8 is greater than or equal to overall precision for any model whose
    confidence carries signal, so gating on it would let a type ship on the
    strength of the subset the report already privileges - while the sub-0.8
    findings the same report prints go entirely ungated.
    """
    path = _gate_file(
        tmp_path,
        {
            "scored": True,
            "headline": {
                "f1_macro": 0.95,
                "by_type": {
                    "rust_corrosion": {
                        "precision": 0.40,
                        "recall": 0.99,
                        "f1": 0.95,
                        "n_predictions": 400,
                    }
                },
            },
            "high_confidence": {
                "precision": 0.99,
                "by_type": {"rust_corrosion": {"precision": 0.99, "n_predictions": 200}},
            },
        },
    )
    spec = _with_measurements(FINDING_TYPES, path)["rust_corrosion"]

    assert spec.measured_precision == 0.40
    assert spec.n == 400
    assert spec.enabled_for_paid is False
    assert spec.status == "below gate"


def test_the_gate_does_not_read_f1(tmp_path: Path) -> None:
    """An F1 without a precision beside it is not a measurement the gate accepts."""
    path = _gate_file(
        tmp_path,
        {"headline": {"by_type": {"rust_corrosion": {"f1": 0.99, "n_predictions": 400}}}},
    )
    spec = _with_measurements(FINDING_TYPES, path)["rust_corrosion"]

    assert spec.measured_precision is None
    assert spec.enabled_for_paid is False
    assert spec.status == "not measured"


def test_the_gate_does_not_read_the_high_confidence_block(tmp_path: Path) -> None:
    """A precision in the high-confidence block alone gates nothing."""
    path = _gate_file(
        tmp_path,
        {
            "headline": {"by_type": {}},
            "high_confidence": {
                "by_type": {"rust_corrosion": {"precision": 0.99, "n_predictions": 400}}
            },
        },
    )
    spec = _with_measurements(FINDING_TYPES, path)["rust_corrosion"]

    assert spec.measured_precision is None
    assert spec.enabled_for_paid is False
