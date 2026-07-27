"""LAW 4 - the eval harness.

This module turns a folder of labeled photographs and a folder of generated
reports into the numbers on docs/ACCURACY.md. Nothing else in the codebase is
allowed to put a precision figure in front of a buyer; the registry reads what
this writes, so a published number and a measured number cannot diverge.

The rules were fixed in P0, before any results existed, precisely so that they
could not be tuned afterwards to flatter a run (docs/EVAL.md):

- A box matches at IoU 0.4, because the useful claim is "there is rust on this
  rocker panel" rather than pixel-exact localization. The stricter 0.5 figure is
  computed on the same run and published beside it, so the choice is visible
  rather than hidden (D-008).
- Matching is greedy by confidence, and a label can only be claimed once. Two
  boxes over one dent is one true positive and one false positive, not two
  true positives.
- A prediction on an unlabeled region is a false positive. This is the whole
  point: an eval set of nothing but damaged cars measures enthusiasm, not
  precision, so the set must contain photographs whose correct answer is silence.

One category is deliberately not scored. Observations near brakes, restraints,
structure and steering leave the pipeline as mechanic referrals, and scoring them
would mean asserting ground truth about systems we have said in writing we cannot
assess from a photograph (LAW 2). We do not get to have it both ways. They are
counted and reported as unscored, so their volume stays visible.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .models import LOCKED_SYSTEMS, BoundingBox

#: Fixed in P0. Changing either of these is a change to what our numbers mean and
#: needs a DECISIONS entry saying so.
HEADLINE_IOU = 0.4
STRICT_IOU = 0.5


@dataclass(frozen=True)
class Label:
    """One thing a human says is really in a photograph."""

    asset_id: str
    type: str
    box: BoundingBox
    note: str = ""


@dataclass(frozen=True)
class Prediction:
    asset_id: str
    type: str
    box: BoundingBox
    confidence: float
    finding_id: str


@dataclass
class TypeScore:
    type: str
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0

    @property
    def predictions(self) -> int:
        """Positive predictions - the n behind a precision figure."""
        return self.true_positives + self.false_positives

    @property
    def labels(self) -> int:
        return self.true_positives + self.false_negatives

    @property
    def precision(self) -> float | None:
        if self.predictions == 0:
            return None
        return self.true_positives / self.predictions

    @property
    def recall(self) -> float | None:
        if self.labels == 0:
            return None
        return self.true_positives / self.labels

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "n_predictions": self.predictions,
            "n_labels": self.labels,
            "precision": self.precision,
            "recall": self.recall,
        }


@dataclass
class BenchResult:
    iou: float
    by_type: dict[str, TypeScore] = field(default_factory=dict)
    #: Referrals on locked systems. Counted, never scored. See the module docstring.
    unscored_referrals: int = 0
    assets_evaluated: int = 0
    reports_evaluated: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "iou": self.iou,
            "assets_evaluated": self.assets_evaluated,
            "reports_evaluated": self.reports_evaluated,
            "unscored_referrals": self.unscored_referrals,
            "by_type": {k: v.to_dict() for k, v in sorted(self.by_type.items())},
        }


def iou(a: BoundingBox, b: BoundingBox) -> float:
    """Intersection over union of two normalized boxes."""
    left = max(a.x, b.x)
    top = max(a.y, b.y)
    right = min(a.x + a.w, b.x + b.w)
    bottom = min(a.y + a.h, b.y + b.h)
    if right <= left or bottom <= top:
        return 0.0
    overlap = (right - left) * (bottom - top)
    union = a.w * a.h + b.w * b.h - overlap
    if union <= 0:
        return 0.0
    return overlap / union


def _box(raw: dict[str, Any]) -> BoundingBox:
    return BoundingBox(x=raw["x"], y=raw["y"], w=raw["w"], h=raw["h"])


def load_labels(labels_dir: Path) -> list[Label]:
    """Read every label file. One file per capture session."""
    labels: list[Label] = []
    for path in sorted(labels_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for asset_id, entry in (data.get("assets") or {}).items():
            for raw in entry.get("labels") or []:
                labels.append(
                    Label(
                        asset_id=asset_id,
                        type=raw["type"],
                        box=_box(raw["box"]),
                        note=raw.get("note", ""),
                    )
                )
    return labels


def labeled_assets(labels_dir: Path) -> set[str]:
    """Every asset a human actually looked at.

    An asset with an empty label list is still labeled - it is the case where the
    correct answer is silence, and it is the only way a false positive can be
    counted. Predictions on assets nobody labeled are ignored entirely rather
    than counted as errors, because we do not know what is in them.
    """
    seen: set[str] = set()
    for path in sorted(labels_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        seen.update((data.get("assets") or {}).keys())
    return seen


def load_predictions(reports_dir: Path) -> tuple[list[Prediction], int, int]:
    """Pull image-region findings out of generated reports."""
    predictions: list[Prediction] = []
    referrals = 0
    reports = 0
    for path in sorted(reports_dir.glob("*.json")):
        report = json.loads(path.read_text(encoding="utf-8"))
        if "findings" not in report:
            continue
        reports += 1
        for finding in report["findings"]:
            for evidence in finding["evidence"]:
                if evidence.get("kind") != "image_region":
                    continue
                predictions.append(
                    Prediction(
                        asset_id=evidence["assetId"],
                        type=finding["type"],
                        box=_box(evidence["box"]),
                        confidence=finding["confidence"],
                        finding_id=finding["id"],
                    )
                )
        for referral in report.get("mechanicReferrals", []):
            if referral["system"] in LOCKED_SYSTEMS:
                referrals += 1
    return predictions, referrals, reports


def score(
    predictions: list[Prediction],
    labels: list[Label],
    *,
    threshold: float = HEADLINE_IOU,
    evaluated_assets: set[str] | None = None,
    unscored_referrals: int = 0,
    reports: int = 0,
) -> BenchResult:
    """Greedy confidence-ordered matching, per asset and per finding type."""
    if evaluated_assets is None:
        evaluated_assets = {label.asset_id for label in labels}

    result = BenchResult(
        iou=threshold,
        unscored_referrals=unscored_referrals,
        assets_evaluated=len(evaluated_assets),
        reports_evaluated=reports,
    )

    # Only predictions on assets a human labeled can be judged at all.
    judged = [p for p in predictions if p.asset_id in evaluated_assets]

    by_key: dict[tuple[str, str], list[Label]] = {}
    for label in labels:
        by_key.setdefault((label.asset_id, label.type), []).append(label)

    claimed: set[int] = set()
    # Highest confidence first: when two predictions could claim one label, the
    # one we were most sure of gets it, and the other is the false positive.
    for prediction in sorted(judged, key=lambda p: -p.confidence):
        entry = result.by_type.setdefault(prediction.type, TypeScore(prediction.type))
        candidates = by_key.get((prediction.asset_id, prediction.type), [])

        best_index: int | None = None
        best_iou = threshold
        for index, label in enumerate(candidates):
            key = id(label)
            if key in claimed:
                continue
            overlap = iou(prediction.box, label.box)
            if overlap >= best_iou:
                best_iou = overlap
                best_index = index

        if best_index is None:
            entry.false_positives += 1
        else:
            claimed.add(id(candidates[best_index]))
            entry.true_positives += 1

    for label in labels:
        if id(label) not in claimed:
            entry = result.by_type.setdefault(label.type, TypeScore(label.type))
            entry.false_negatives += 1

    return result


def run(labels_dir: Path, reports_dir: Path) -> dict[str, Any]:
    """Score at both thresholds and return the publishable result."""
    labels = load_labels(labels_dir)
    predictions, referrals, reports = load_predictions(reports_dir)
    assets = labeled_assets(labels_dir)

    headline = score(
        predictions,
        labels,
        threshold=HEADLINE_IOU,
        evaluated_assets=assets,
        unscored_referrals=referrals,
        reports=reports,
    )
    strict = score(
        predictions,
        labels,
        threshold=STRICT_IOU,
        evaluated_assets=assets,
        unscored_referrals=referrals,
        reports=reports,
    )
    return {
        "_note": (
            "Written by tirekick bench. docs/ACCURACY.md and the eval gate read "
            "this file; do not hand-edit it. Regenerate it instead."
        ),
        "headline": headline.to_dict(),
        "strict": strict.to_dict(),
    }


def render(result: dict[str, Any]) -> str:
    """The table printed after a bench run."""
    headline = result["headline"]
    strict = result["strict"]
    lines = [
        f"  EVAL RESULT - {headline['reports_evaluated']} report(s), "
        f"{headline['assets_evaluated']} labeled asset(s)",
        "",
        "  TYPE                       TP   FP   FN   PRECISION  RECALL   P@0.5",
    ]
    for name, row in headline["by_type"].items():
        strict_row = strict["by_type"].get(name, {})
        precision = "     -" if row["precision"] is None else f"{row['precision']:6.2f}"
        recall = "     -" if row["recall"] is None else f"{row['recall']:6.2f}"
        strict_precision = (
            "     -"
            if strict_row.get("precision") is None
            else f"{strict_row['precision']:6.2f}"
        )
        lines.append(
            f"  {name:<24} {row['true_positives']:>4} {row['false_positives']:>4} "
            f"{row['false_negatives']:>4}     {precision}  {recall}  {strict_precision}"
        )
    if not headline["by_type"]:
        lines.append("  (nothing to score - no labels and no predictions)")
    lines.append("")
    lines.append(
        f"  {headline['unscored_referrals']} locked-system referral(s) were counted "
        f"and not scored (LAW 2)."
    )
    return "\n".join(lines)


__all__ = [
    "HEADLINE_IOU",
    "STRICT_IOU",
    "BenchResult",
    "Label",
    "Prediction",
    "TypeScore",
    "asdict",
    "iou",
    "load_labels",
    "load_predictions",
    "render",
    "run",
    "score",
]
