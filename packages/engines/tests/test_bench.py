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
) -> bench.Prediction:
    return bench.Prediction(
        asset_id=asset,
        type=type_,
        box=b or box(0.1, 0.1, 0.2, 0.2),
        confidence=confidence,
        finding_id=finding_id,
    )


def label(
    asset: str = "photo_01",
    type_: str = "rust_corrosion",
    b: BoundingBox | None = None,
) -> bench.Label:
    return bench.Label(asset_id=asset, type=type_, box=b or box(0.1, 0.1, 0.2, 0.2))


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
