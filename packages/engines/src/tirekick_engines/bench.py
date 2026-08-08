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

P10 added the four metrics docs/EVAL.md has described since P0 and this file has
never computed: F1, precision at high confidence, a severity confusion matrix and
calibration. They were built against an eval set of nothing, which is the reason
for most of the code below.

Every one of the four fails toward flattery if written the obvious way, because
every one of them is a ratio and every denominator here is currently zero:

- precision at high confidence, guarded as 0/0 -> 1.0, reads as "we were right
  about all zero of them";
- severity agreement as exact/max(n, 1) -> 1.0, perfect agreement with a human
  who has never labeled anything;
- expected calibration error as an accumulator that starts at 0.0 and is never
  divided -> 0.0, which reads as *perfectly calibrated* and is the single worst
  number this file could publish.

So the rule this module holds itself to: **a rate whose denominator is zero is
null - never 0.0 and never 1.0 - and every rate ships beside the integer count it
came from.** Above that sits a refusal, because a consumer that ignores nulls
would otherwise still find numbers here to quote, and render() prints the refusal
instead of a table of dashes: a table of dashes is still a table, and a
screenshot of one is a claim.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, get_args

from .models import LOCKED_SYSTEMS, BoundingBox, Severity

#: Fixed in P0. Changing either of these is a change to what our numbers mean and
#: needs a DECISIONS entry saying so.
HEADLINE_IOU = 0.4
STRICT_IOU = 0.5

#: docs/EVAL.md has said ">= 0.8" since P0 and calls it "the number that matters
#: most, because the report visually privileges high-confidence findings". This
#: constant is that sentence, not a threshold picked after seeing a run - which is
#: EVAL.md's own anti-gaming rule doing its job. Changing it is a change to what
#: our numbers mean and needs a DECISIONS entry saying so.
HIGH_CONFIDENCE = 0.80

#: Ten equal-width reliability bins. Changing this changes what an ECE from this
#: file means and needs a DECISIONS entry saying so.
CALIBRATION_BINS = 10

#: The severity vocabulary, read off models.Severity rather than retyped, so that
#: a fifth severity cannot exist in the product and be invisible to the harness.
#:
#: docs/EVAL.md promises {cosmetic, moderate, significant} - a third vocabulary,
#: matching neither the models nor anything the engines emit. The code's four win
#: because they are the ones a finding actually carries; EVAL.md is wrong and
#: needs correcting separately.
#:
#: Declaration order is load-bearing: it is the ordinal scale that decides whether
#: a disagreement was an over-call or an under-call, and reversing it inverts the
#: ethical claim of the whole matrix.
SEVERITY_VOCABULARY: tuple[str, ...] = get_args(Severity)


@dataclass(frozen=True)
class Label:
    """One thing a human says is really in a photograph."""

    asset_id: str
    type: str
    box: BoundingBox
    note: str = ""
    #: Added in P10. None means the labeler did not record one, which is counted
    #: as missing and never filled in from what we predicted - imputing the label
    #: from the prediction would score the model against its own answer.
    severity: str | None = None


@dataclass(frozen=True)
class Prediction:
    asset_id: str
    type: str
    box: BoundingBox
    confidence: float
    finding_id: str
    #: What we called it. Never a match criterion: a correctly located rust patch
    #: called critical when a human said minor is a true positive with a severity
    #: error, and collapsing those two failures into one hides both.
    severity: str | None = None


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

    @property
    def f1(self) -> float | None:
        """The harmonic mean of precision and recall, or nothing.

        Three states, and the middle one is the one that gets lost. Undefined
        (None) means we could not compute it - no predictions, or no labels, so
        one of the two inputs does not exist. Zero means we computed it and the
        model got nothing right on a type where both predictions and labels were
        present. A harness that reports the first as 0.0 makes an unmeasured type
        look measured and terrible; one that reports the second as None makes a
        type that failed look untested.

        The arithmetic mean is the tempting mistake here: 1.0 precision with 0.02
        recall averages to a respectable 0.51 and harmonises to 0.04, and the
        second number is the one that describes a model that finds one dent in
        fifty and is smug about it.
        """
        precision = self.precision
        recall = self.recall
        if precision is None or recall is None:
            return None
        if precision + recall == 0:
            return 0.0
        return 2 * precision * recall / (precision + recall)

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
            "f1": self.f1,
        }


@dataclass(frozen=True)
class Judgement:
    """One prediction and the label it claimed, if any.

    Kept because precision and recall throw away which prediction was right, and
    both the confusion matrix and the reliability table need exactly that: the
    matrix pairs a predicted severity with the labeled one it matched, and
    calibration asks whether the findings we were sure about were the correct
    ones.
    """

    prediction: Prediction
    label: Label | None

    @property
    def correct(self) -> bool:
        return self.label is not None


@dataclass
class BenchResult:
    iou: float
    by_type: dict[str, TypeScore] = field(default_factory=dict)
    #: Referrals on locked systems. Counted, never scored. See the module docstring.
    unscored_referrals: int = 0
    assets_evaluated: int = 0
    reports_evaluated: int = 0
    #: Every judged prediction with its outcome, in matching order. Working data
    #: for the derived metrics; deliberately not serialized - latest.json is the
    #: gate's input, not a dump of the run.
    judgements: list[Judgement] = field(default_factory=list, repr=False)

    @property
    def matches(self) -> list[Judgement]:
        return [j for j in self.judgements if j.label is not None]

    def macro_f1(self) -> dict[str, Any]:
        """Unweighted mean F1 across the types that have one, with its denominator.

        A macro average over 2 of the 16 registered finding types is the classic
        flattering number: it reads as a system score and is a score on the two
        types that happened to have both labels and predictions. Naming the types
        and their count beside the figure is what stops it reading that way, so
        the three keys are emitted together or not at all.
        """
        scored = {name: s.f1 for name, s in self.by_type.items() if s.f1 is not None}
        names = sorted(scored)
        if not names:
            # Not 0.0. There is no F1 here to be bad at.
            return {"f1_macro": None, "f1_macro_types": [], "f1_macro_n_types": 0}
        return {
            "f1_macro": sum(scored[n] for n in names) / len(names),
            "f1_macro_types": names,
            "f1_macro_n_types": len(names),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "iou": self.iou,
            "assets_evaluated": self.assets_evaluated,
            "reports_evaluated": self.reports_evaluated,
            "unscored_referrals": self.unscored_referrals,
            **self.macro_f1(),
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


def _severity(raw: Any, where: str) -> str | None:
    """Validate a severity string, or refuse to load the file.

    A typo'd severity read as None would quietly leave the pair out of the
    confusion matrix, and the matrix would then report agreement over the subset
    of labels that happened to be spelled correctly - a smaller, cleaner number
    with nothing announcing that it is smaller. Missing is a state; misspelled is
    a mistake, and the two must not arrive at the same place.
    """
    if raw is None:
        return None
    if raw not in SEVERITY_VOCABULARY:
        raise ValueError(
            f"{where}: severity {raw!r} is not one of {list(SEVERITY_VOCABULARY)}. "
            f"docs/EVAL.md describes a different vocabulary "
            f"({{cosmetic, moderate, significant}}); the code's is the real one."
        )
    return str(raw)


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
                        severity=_severity(raw.get("severity"), f"{path.name}:{asset_id}"),
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
            severity = _severity(finding.get("severity"), f"{path.name}:{finding['id']}")
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
                        severity=severity,
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
    # finding_id and asset_id break confidence ties, because dict iteration order
    # deciding which of two equally confident boxes is the true positive would
    # make four derived metrics wobble between runs on the same data.
    for prediction in sorted(judged, key=lambda p: (-p.confidence, p.finding_id, p.asset_id)):
        entry = result.by_type.setdefault(prediction.type, TypeScore(prediction.type))
        candidates = by_key.get((prediction.asset_id, prediction.type), [])

        best_index: int | None = None
        best_iou = -1.0
        for index, label in enumerate(candidates):
            key = id(label)
            if key in claimed:
                continue
            overlap = iou(prediction.box, label.box)
            if overlap < threshold:
                continue
            # Strictly better, not merely as good: the old `>=` handed the label
            # to whichever tying candidate the file happened to list last, so the
            # severity a matched pair contributes to the matrix depended on label
            # ordering rather than on geometry.
            if overlap > best_iou:
                best_iou = overlap
                best_index = index

        if best_index is None:
            entry.false_positives += 1
            result.judgements.append(Judgement(prediction=prediction, label=None))
        else:
            matched = candidates[best_index]
            claimed.add(id(matched))
            entry.true_positives += 1
            result.judgements.append(Judgement(prediction=prediction, label=matched))

    for label in labels:
        if id(label) not in claimed:
            entry = result.by_type.setdefault(label.type, TypeScore(label.type))
            entry.false_negatives += 1

    return result


def high_confidence_block(result: BenchResult) -> dict[str, Any]:
    """Precision over the findings the report visually privileges.

    docs/EVAL.md calls this the number that matters most, and it is also the
    number most likely to be quoted alone: P@0.8 is greater than or equal to
    overall precision for any model whose confidence carries signal, so a gate
    pointed at it would let a type ship on the strength of the subset the report
    already puts at the top of the page while the sub-0.8 findings it also prints
    go entirely ungated. It is published and it does not gate anything - the
    registry reads headline.by_type precision, and that is deliberate.

    No recall here, at any level. A real dent found only by a 0.5-confidence
    prediction becomes a false negative the moment the filter is applied, so a
    "recall" computed over a confidence-filtered set is not this system's recall;
    it is the recall of a system we do not ship, and it would be lower for
    reasons that have nothing to do with what we missed. F1 goes with it, because
    F1 is half recall.
    """
    true_positives = sum(s.true_positives for s in result.by_type.values())
    false_positives = sum(s.false_positives for s in result.by_type.values())
    n_predictions = true_positives + false_positives
    return {
        "threshold": HIGH_CONFIDENCE,
        "iou": result.iou,
        "_note": (
            f"Precision over judged predictions with confidence >= "
            f"{HIGH_CONFIDENCE}. Published, never gated: the eval gate reads "
            f"headline.by_type precision, which includes every finding the "
            f"report prints."
        ),
        "recall": None,
        "_recall_note": (
            "Not published, and null rather than absent so its absence is "
            "visible. A label found only by a low-confidence prediction becomes "
            "a false negative under this filter, so recall over a "
            "confidence-filtered set is not the system's recall."
        ),
        "f1": None,
        "_f1_note": "Not published: F1 needs a recall, and this block has none.",
        "true_positives": true_positives,
        "false_positives": false_positives,
        "n_predictions": n_predictions,
        # None, not 1.0. "We were right about all zero of the findings that
        # cleared 0.8" is the flattering reading of an empty filter.
        "precision": _rate(true_positives, n_predictions),
        "by_type": {
            name: {
                "type": s.type,
                "true_positives": s.true_positives,
                "false_positives": s.false_positives,
                "n_predictions": s.predictions,
                "precision": s.precision,
                "recall": None,
                "f1": None,
            }
            for name, s in sorted(result.by_type.items())
        },
    }


def clears_high_confidence(prediction: Prediction) -> bool:
    """Whether a finding belongs in the high-confidence population.

    A function rather than an inline comparison so that the boundary has one
    definition and a test can reach it. `>` instead of `>=` here drops every
    finding stated at exactly 0.80 - a value models emit constantly - and quietly
    shrinks the population of the number EVAL.md calls the one that matters most,
    with nothing in the output announcing the change.
    """
    return prediction.confidence >= HIGH_CONFIDENCE


def _rate(numerator: int, denominator: int) -> float | None:
    """A rate, or nothing at all.

    The one-line version of this module's governing rule. Guarding 0/0 to 1.0
    claims we were right about all zero of them; guarding it to 0.0 claims we
    were wrong about all zero of them. Both are claims, and we have not measured
    anything.
    """
    if denominator == 0:
        return None
    return numerator / denominator


def severity_confusion(matches: list[Judgement]) -> dict[str, Any]:
    """How wrong we were about how bad it was, given that we found it.

    Detection and grading are different failures and this repository keeps saying
    so, so they are measured apart. The domain is matched pairs only: a false
    positive has no labeled severity to disagree with, and a false negative has
    no predicted one, and sweeping either into the matrix would turn a detection
    error into a grading error.

    Direction is the whole point. Calling a minor rust patch critical talks a
    buyer out of a good car (D-017); calling a critical one minor sells them a
    bad one. Those are opposite failures with opposite fixes, and a transposed
    matrix reports each as the other - which is why the orientation is stated in
    the payload next to the counts rather than left for a reader to infer.
    """
    matrix: dict[str, dict[str, int]] = {
        labeled: dict.fromkeys(SEVERITY_VOCABULARY, 0) for labeled in SEVERITY_VOCABULARY
    }
    order = {name: i for i, name in enumerate(SEVERITY_VOCABULARY)}

    n_matched = len(matches)
    missing_label = 0
    missing_predicted = 0
    exact = 0
    over_called = 0
    under_called = 0

    for judgement in matches:
        if judgement.label is None:
            continue  # not a matched pair; BenchResult.matches has filtered these
        labeled = judgement.label.severity
        predicted = judgement.prediction.severity
        if labeled is None:
            # Counted as missing, never imputed from what we said. Filling the
            # human's blank with our own answer scores the model against itself.
            missing_label += 1
            continue
        if predicted is None:
            missing_predicted += 1
            continue
        matrix[labeled][predicted] += 1
        if order[predicted] > order[labeled]:
            over_called += 1
        elif order[predicted] < order[labeled]:
            under_called += 1
        else:
            exact += 1

    n_scored = exact + over_called + under_called
    return {
        "_orientation": (
            "matrix[labelled][predicted]. The outer key is the severity a human "
            "wrote down; the inner key is the severity we called it. Transposed, "
            "over-calling reads as under-calling, which is the opposite claim "
            "about who this product hurts."
        ),
        "_domain": (
            f"Matched findings at IoU {HEADLINE_IOU} only. False positives have "
            f"no labelled severity and false negatives have no predicted one; "
            f"neither is a grading error and neither is counted here. Severity "
            f"is not a match criterion - a correctly located finding graded "
            f"wrongly is a true positive with a severity error."
        ),
        "vocabulary": list(SEVERITY_VOCABULARY),
        "matrix": matrix,
        "n_matched": n_matched,
        "n_matched_with_label_severity": n_matched - missing_label,
        "n_matched_missing_label_severity": missing_label,
        "n_matched_missing_predicted_severity": missing_predicted,
        "n_scored": n_scored,
        "exact": exact,
        "over_called": over_called,
        "under_called": under_called,
        "exact_rate": _rate(exact, n_scored),
        "over_called_rate": _rate(over_called, n_scored),
        "under_called_rate": _rate(under_called, n_scored),
    }


def _bin_index(confidence: float) -> int:
    """Which reliability bin a stated confidence falls in.

    Half-open [0.0,0.1) ... [0.8,0.9), and the last one closed [0.9,1.0] so that
    a confidence of exactly 1.0 lands in a bin instead of off the end of the
    array - the most confident finding the model can emit is the last one that
    should go uncounted.

    int(confidence * 10) is the short version and it returns 10 for a confidence
    of 1.0, which is one past the end of a ten-element list. Where that index is
    used to look a bin up it raises; where it is used to filter, as it is here,
    the finding lands in no bin at all and the reliability table quietly stops
    summing to n.

    Written out as edge comparisons rather than clamped arithmetic because the
    bins are half-open at one end and closed at the other, and that asymmetry
    should be legible in the code that implements it rather than recovered from a
    min() call. It is not a claim about floating point: int(0.7 * 10) is 7 in
    CPython, and a check of every value with three decimal places finds no bin
    the two approaches disagree about.
    """
    if confidence >= 1.0:
        return CALIBRATION_BINS - 1
    for index in range(CALIBRATION_BINS):
        if confidence < (index + 1) / CALIBRATION_BINS:
            return index
    return CALIBRATION_BINS - 1


def calibration(judgements: list[Judgement]) -> dict[str, Any]:
    """Whether a stated confidence means anything.

    A model that says 0.9 and is right 60% of the time is lying to the buyer even
    when the finding is real, and precision alone cannot see it: a model can hold
    0.85 precision overall while its confidences are noise.

    Population is judged predictions at the headline threshold, all types pooled
    - the same universe precision uses, so a prediction on an asset nobody
    labeled appears in no bin rather than in the bin for "probably fine". Pooled
    only: per-type calibration on the sample sizes this project will have first
    is noise dressed as a diagnosis, so it is not built and nothing here implies
    it exists.

    ECE is null when the population is empty. Written as an accumulator starting
    at 0.0 that is never divided - the natural way to write it - it comes out as
    0.0 on an empty run, and 0.0 is the number that means *perfectly calibrated*.
    That is the single most flattering thing this file could print about a model
    that has never been run.
    """
    populated: list[dict[str, Any]] = []
    bins: list[dict[str, Any]] = []
    for index in range(CALIBRATION_BINS):
        lo = index / CALIBRATION_BINS
        hi = (index + 1) / CALIBRATION_BINS
        members = [j for j in judgements if _bin_index(j.prediction.confidence) == index]
        n = len(members)
        true_positives = sum(1 for j in members if j.correct)
        observed = _rate(true_positives, n)
        mean_confidence = None if n == 0 else sum(j.prediction.confidence for j in members) / n
        gap = (
            None if mean_confidence is None or observed is None else mean_confidence - observed
        )
        row = {
            "lo": lo,
            "hi": hi,
            "closed": index == CALIBRATION_BINS - 1,
            "n": n,
            "true_positives": true_positives,
            "observed_precision": observed,
            "mean_confidence": mean_confidence,
            "gap": gap,
        }
        bins.append(row)
        if n:
            populated.append(row)

    total = len(judgements)
    # Null on an empty population, not 0.0. Zero calibration error is the score a
    # perfectly calibrated model gets, and it is one dropped guard away from here.
    ece: float | None = (
        None if total == 0 else sum((row["n"] / total) * abs(row["gap"]) for row in populated)
    )

    return {
        "_gap_sign": (
            "gap = mean_confidence - observed_precision. Positive means "
            "OVERCONFIDENT: we said more than we delivered. Negative means we "
            "were right more often than we claimed."
        ),
        "_population": (
            f"Judged predictions at IoU {HEADLINE_IOU}, all finding types pooled. "
            f"A prediction on an asset nobody labelled is in no bin. Per-type "
            f"calibration is not computed - on the sample sizes this project has "
            f"it would be noise."
        ),
        "n": total,
        "bins_populated": len(populated),
        "expected_calibration_error": ece,
        "bins": bins,
    }


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
    high = score(
        [p for p in predictions if clears_high_confidence(p)],
        labels,
        threshold=HEADLINE_IOU,
        evaluated_assets=assets,
        unscored_referrals=referrals,
        reports=reports,
    )

    n_judged = len(headline.judgements)
    # Something was scored only if a human wrote a label or we made a claim on an
    # asset a human looked at. Anything less and every figure below is a null or
    # an empty dict, and the file needs to say so louder than a null can.
    scored = bool(labels) or bool(n_judged)
    refusal = (
        None
        if scored
        else (
            f"Not a measurement. {len(assets)} labeled assets, {len(labels)} "
            f"labels, {n_judged} judged predictions on the eval set. No figure "
            f"in this file is a result."
        )
    )

    return {
        "_note": (
            "Written by tirekick bench. docs/ACCURACY.md and the eval gate read "
            "this file; do not hand-edit it. Regenerate it instead."
        ),
        "scored": scored,
        "refusal": refusal,
        "headline": headline.to_dict(),
        "strict": strict.to_dict(),
        "high_confidence": high_confidence_block(high),
        "severity_confusion": severity_confusion(headline.matches),
        "calibration": calibration(headline.judgements),
    }


def _fmt(value: float | None, width: int = 6) -> str:
    return "-".rjust(width) if value is None else f"{value:{width}.2f}"


def _render_refusal(result: dict[str, Any]) -> str:
    """What gets printed when there is nothing to print.

    Not a table of dashes. A table of dashes is a table: it has the shape of a
    result, it screenshots like a result, and a reader who does not stop to
    notice that every cell is empty comes away believing this was measured.
    """
    return "\n".join(
        [
            "  EVAL RESULT - NOT A MEASUREMENT",
            "",
            f"  {result['refusal']}",
            "",
            "  No table is printed here on purpose. A table of dashes is still a",
            "  table, and a screenshot of one is a claim.",
            "",
            f"  {result['headline']['unscored_referrals']} locked-system "
            f"referral(s) were counted and not scored (LAW 2).",
        ]
    )


def render(result: dict[str, Any]) -> str:
    """The table printed after a bench run."""
    if not result.get("scored"):
        return _render_refusal(result)

    headline = result["headline"]
    strict = result["strict"]
    lines = [
        f"  EVAL RESULT - {headline['reports_evaluated']} report(s), "
        f"{headline['assets_evaluated']} labeled asset(s)",
        "",
        "  TYPE                       TP   FP   FN   PRECISION  RECALL   P@0.5      F1",
    ]
    for name, row in headline["by_type"].items():
        strict_row = strict["by_type"].get(name, {})
        lines.append(
            f"  {name:<24} {row['true_positives']:>4} {row['false_positives']:>4} "
            f"{row['false_negatives']:>4}     {_fmt(row['precision'])}  "
            f"{_fmt(row['recall'])}  {_fmt(strict_row.get('precision'))}  "
            f"{_fmt(row['f1'])}"
        )
    if not headline["by_type"]:
        lines.append("  (nothing to score - no labels and no predictions)")

    lines.append("")
    macro = headline["f1_macro"]
    if macro is None:
        lines.append("  Macro F1: - (no type has both a precision and a recall)")
    else:
        lines.append(
            f"  Macro F1: {macro:.2f} - unweighted, over "
            f"{headline['f1_macro_n_types']} of {len(headline['by_type'])} "
            f"type(s) with data: {', '.join(headline['f1_macro_types'])}"
        )

    high = result["high_confidence"]
    lines.append(
        f"  P@{high['threshold']:.2f} confidence: {_fmt(high['precision'], 5).strip()} "
        f"on n={high['n_predictions']} (no recall published - see _recall_note)"
    )

    lines.append("")
    lines.extend(_render_severity(result["severity_confusion"]))
    lines.append("")
    lines.extend(_render_calibration(result["calibration"]))

    lines.append("")
    lines.append(
        f"  {headline['unscored_referrals']} locked-system referral(s) were counted "
        f"and not scored (LAW 2)."
    )
    return "\n".join(lines)


def _render_severity(block: dict[str, Any]) -> list[str]:
    vocabulary = block["vocabulary"]
    header = "".join(f"{name:>10}" for name in vocabulary)
    lines = [
        f"  SEVERITY - matched findings only, IoU {HEADLINE_IOU}. "
        f"Rows: human. Columns: us.",
        f"  {'LABELLED':<12}{header}",
    ]
    for labeled in vocabulary:
        cells = "".join(f"{block['matrix'][labeled][p]:>10}" for p in vocabulary)
        lines.append(f"  {labeled:<12}{cells}")
    lines.append(
        f"  exact {block['exact']}, over-called {block['over_called']}, "
        f"under-called {block['under_called']} of {block['n_scored']} graded pair(s); "
        f"{block['n_matched_missing_label_severity']} matched finding(s) had no "
        f"labelled severity."
    )
    return lines


def _render_calibration(block: dict[str, Any]) -> list[str]:
    lines = [
        "  CALIBRATION - judged predictions, all types pooled. "
        "Positive gap = overconfident.",
        f"  {'BIN':<12}{'n':>6}{'TP':>6}{'OBSERVED':>10}{'MEAN CONF':>11}{'GAP':>9}",
    ]
    for row in block["bins"]:
        edge = "]" if row["closed"] else ")"
        span = f"[{row['lo']:.1f},{row['hi']:.1f}{edge}"
        lines.append(
            f"  {span:<12}{row['n']:>6}{row['true_positives']:>6}"
            f"{_fmt(row['observed_precision']):>10}"
            f"{_fmt(row['mean_confidence']):>11}{_fmt(row['gap']):>9}"
        )
    ece = block["expected_calibration_error"]
    ece_text = "not computed (no judged predictions)" if ece is None else f"{ece:.3f}"
    lines.append(
        f"  ECE {ece_text} over {block['bins_populated']} populated bin(s), " f"n={block['n']}."
    )
    return lines


__all__ = [
    "CALIBRATION_BINS",
    "HEADLINE_IOU",
    "HIGH_CONFIDENCE",
    "SEVERITY_VOCABULARY",
    "STRICT_IOU",
    "BenchResult",
    "Judgement",
    "Label",
    "Prediction",
    "TypeScore",
    "asdict",
    "calibration",
    "clears_high_confidence",
    "high_confidence_block",
    "iou",
    "load_labels",
    "load_predictions",
    "render",
    "run",
    "score",
    "severity_confusion",
]
