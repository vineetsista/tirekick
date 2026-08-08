# EVAL METHODOLOGY

How TIREKICK measures itself. Written at P0 so that the method is fixed *before* we
see any results and get tempted.

**Read this as two documents.** Everything marked *built* below exists in
`packages/engines/src/tirekick_engines/bench.py` and runs today against an empty
label set. Everything marked *not built* is method we committed to at P0 and have
not implemented, and saying so here is cheaper than letting a reader assume the
harness computes a number it has never computed. The split was invisible until P10:
this page described calibration plots and severity matrices in the present tense
next to precision and recall, which are the only two things the harness had ever
produced.

P11 built the four. That closes the gap in the direction the gap should close, and
it introduced the opposite risk immediately, because all four are ratios and the
eval set is empty: an F1 over nothing, a precision over nothing, a severity
agreement rate over nothing and — the dangerous one — an expected calibration error
over nothing, which written the obvious way comes out as **0.0 and reads as
perfectly calibrated**. So the governing rule of the harness is now one line:

> A rate whose denominator is zero is `null`. Never `0.0`, never `1.0`, and always
> published beside the integer count it came from.

and above it, `bench/results/latest.json` carries `"scored": false` and a refusal
sentence, which `render()` prints **instead of** a table. A table of dashes is
still a table, and a screenshot of one is a claim.

## Principles

1. **Label before you measure.** The eval set is labeled by a human against a written
   rubric, and labeling happens without looking at model output for that image.
2. **The eval set is not the training set, and it is not the demo set.** Media used to
   debug a prompt is burned and cannot be scored on.
3. **Report n, always.** Small n is fine to act on internally and never fine to
   publish as a rate.
4. **Publish the misses** (LAW 4). A page of only good numbers is a marketing page.
5. **Frozen splits.** Once a split is fixed, it stays fixed; new media extends the set,
   it does not replace the awkward parts of it.

## The eval set - not built

Planned for P2. P2 through P9 shipped without it, and `bench/` still contains no
media at all (`bench/PROVENANCE.md` is the record of that). This is the single
reason every finding type is disabled for paid reports; the engines were never the
hard part.

Target: >= 150 images spanning the damage classes, from our own photography and
manually saved public photos, per LAW 3. Composition targets:

| Class | Target images | Why |
|---|---|---|
| clean panels (negatives) | 40 | precision is meaningless without negatives |
| dents / creases | 25 | |
| scratches / scuffs | 20 | most common, least severe - easy to over-report |
| rust - surface | 15 | |
| rust - structural/perforation | 10 | the expensive one to miss |
| repaint / panel mismatch cues | 15 | |
| tires (tread visible) | 15 | |
| dash clusters with lit lamps | 15 | |
| odometers | 15 | |
| interiors (wear range) | 15 | |

Deliberately included hard cases: low light, wet paint, direct sun, dirty panels,
aftermarket trim, phone HDR, and photos taken at the angle sellers actually use.

## Labeling rubric

*Built:* each image gets class label(s) and a bounding box per instance, plus a free
text `note`. An asset with an empty label list means a human looked and there is
nothing to report, and it is the only way a false positive can be counted; an absent
asset means nobody looked, and predictions on it are ignored rather than counted
wrong. `bench/labels/TEMPLATE.json` is the shape.

*Built:* an optional `severity` per label, which is what the confusion matrix below
scores against. The vocabulary is `models.Severity` — **info, minor, major,
critical** — read out of the type with `get_args` rather than retyped, so a fifth
value cannot exist in one place and not the other.

This page promised {cosmetic, moderate, significant} from P0 until P11: a third
severity vocabulary, matching neither the models, nor the report, nor the finding
cards a buyer reads. Nothing translated between them because nothing implemented
either. Adopting the code's four was the only choice that does not create a second
place where a severity is typed — and a translation table between two vocabularies
would have hidden exactly the over-call the matrix exists to measure. It cost
nothing to change now and would have cost a relabelling later, which is the whole
argument for closing this gap before the first session lands rather than after.

A label with no severity is counted as *missing*, never imputed from the prediction,
and an unrecognised severity string is a hard error at load rather than a silent
`None` — a typo that reads as "unlabelled" quietly shrinks the matrix.

*Not built:* a **labeler-confidence** flag, and an `ambiguous` class scored
separately. The `ambiguous` idea is the one worth keeping: a model that is uncertain
exactly where a human is uncertain is a good model, and a harness with nowhere to
put those cases either drops them silently or scores them as failures.

Boxes count as a hit at IoU >= 0.4 (`HEADLINE_IOU`). The threshold is deliberately
loose: for a buyer, "there is rust on this rocker panel" is the useful claim, and
pixel-exact localization is not what they are paying for. The stricter 0.5 figure
(`STRICT_IOU`) is computed on the same run and published beside it, so the choice
stays visible rather than hidden (D-008). Matching is greedy by confidence and a
label can be claimed only once: two boxes over one dent is one true positive and one
false positive, never two true positives.

## Metrics

*Built*, per finding type, at both IoU thresholds: true positives, false positives,
false negatives, precision, recall, and the sample size behind each. Locked-system
referrals are counted and never scored - we have said in writing that we cannot
assess brakes, restraints, structure or steering from a photograph, and scoring them
would mean asserting ground truth we have disclaimed (LAW 2). Their volume is
reported so it stays visible.

*Built in P11*, and each one was a number this page implied we had for ten phases:

- **F1**, per type, at both thresholds, plus a macro. `None` when precision or
  recall is undefined; **`0.0` when the type predicted and matched nothing**. Those
  two cases must stay distinguishable: a type that predicted nothing is unmeasured,
  a type that predicted and missed is bad, and collapsing them into one number is
  how a zero gets read as an absence. The macro ships with `f1_macro_types` and
  `f1_macro_n_types` beside it, because a macro over 2 of 16 registered types is the
  classic flattering number and naming its denominator is what stops it reading as a
  score for the system.

- **Precision at high confidence**, `HIGH_CONFIDENCE = 0.80`, inclusive. That figure
  is not chosen now — this page has said ">= 0.8" since P0, and adopting the number
  written down before there were results, rather than one picked after seeing them,
  is the anti-gaming rule at the bottom of this page doing its job.
  **No recall is published in that block.** A label found only by a 0.5-confidence
  prediction becomes a false negative once the filter is applied, so a recall over a
  confidence-filtered set is not the system's recall; the key is emitted as `null`
  with the reason beside it, because publishing it would understate the product and
  that is still publishing something untrue.

- **Severity confusion matrix**, over matched pairs only — never false positives
  (no labelled severity exists) and never false negatives (no predicted severity
  exists). Severity is **not** a match criterion: a correctly located rust patch
  called `critical` where a human said `minor` is a true positive with a severity
  error, and folding the two axes together would let a severity mistake destroy a
  detection number. The payload carries `matrix[labelled][predicted]` and an
  `_orientation` key naming that direction, because a transposed confusion matrix
  reads as the precise opposite failure — over-calling instead of under-calling —
  and this is the one number where getting the direction backwards inverts the
  ethical claim.

- **Calibration**, as data plus a printed reliability table. No image and no
  plotting dependency. Ten bins, half-open, with the last one **closed** so a
  confidence of exactly 1.0 lands in a bin instead of off the end. `gap =
  mean_confidence - observed_precision`, and a positive gap means overconfident —
  stated in a `_gap_sign` key for the same reason as the matrix orientation. The
  expected calibration error is population-weighted across populated bins and ships
  beside `n` and `bins_populated`, so an ECE derived from one bin is visibly an ECE
  derived from one bin. It is `null` on an empty run, and that is the single most
  important null in this file: an accumulator initialised to `0.0` reports **perfect
  calibration** for a harness that has never seen a photograph.

Calibration is pooled across types. Per-type calibration on the sub-fifty samples a
first capture session produces is noise, and it is named as deferred here rather
than left for a reader to assume — which is the exact failure this whole section
was.

None of this changes what ships. `registry.py` reads overall precision at IoU 0.4
and the unfiltered `n`, and it still does; every key above is additive. Swapping the
gate to precision-at-0.8 would silently loosen LAW 4, because that figure is >= overall
precision by construction for any model whose confidence carries signal — a type
would ship on the strength of the subset the report already privileges while the
findings below the threshold, which it also prints, went entirely ungated. Swapping
it to F1 would let recall buy off precision, which is the direction ACCURACY.md says
costs a buyer a good car. Both are pinned by tests rather than by this paragraph.

## Audio (P3)

A separate, smaller, and more honest exercise. Labeled clip set with the true
condition established by something other than listening - a mechanic's diagnosis, a
known-fault vehicle, or a documented repair. Clips where "the label" is just someone's
opinion of the sound are not ground truth and are excluded.

Expectation set in advance: this engine will be the weakest, its limits go at the top
of ACCURACY.md, and if precision does not clear 0.70 it ships as
"listen for yourself, here is the spectrogram and here is what to ask" with no
anomaly claims at all.

That is what shipped in P3, and the gate is still 0.70 in
`registry.py::audio_anomaly`. It shipped that way not because it was measured below
threshold but because it has never been measured at all, which is a weaker reason
reaching the same output - see D-027. The clip set described above does not exist
either.

## Running

```
pnpm bench                                    # scores bench/reports against bench/labels
tirekick bench --inspections bench/inspections # ...and runs the inspections first
```

Defaults: `--labels bench/labels`, `--reports bench/reports`,
`--out bench/results/latest.json`. Passing `--inspections` runs every inspection
under that directory into `--reports` before scoring, so a capture session goes from
media to a number in one command.

It writes `bench/results/latest.json` and prints a fixed-width summary table — or,
on a run with nothing to score, the refusal instead of the table. It does **not**
emit markdown. What makes the published page generated rather than typed is the
direction of the data: `registry.py` reads `latest.json`, computes
`enabled_for_paid` from it, and `docs/ACCURACY.md` publishes what the registry
computes. There is no second place a precision figure can originate.

`latest.json` is committed, and a gate regenerates it and diffs the result, so a
figure edited into it by hand fails the build. While `bench/labels/` is empty that
gate pins only the shape of the refusal — which is precisely the thing that must
not quietly become `0.0` — and it starts pinning real numbers the day the first
labelled session lands.

## Anti-gaming rules

- No threshold tuning on the eval set after seeing per-image results; tuning happens
  on a separate dev split.
- No removing an image because the model does badly on it.
- Any change to the eval set is a commit that touches only the eval set, with a reason.
