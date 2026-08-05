# EVAL METHODOLOGY

How TIREKICK measures itself. Written at P0 so that the method is fixed *before* we
see any results and get tempted.

**Read this as two documents.** Everything marked *built* below exists in
`packages/engines/src/tirekick_engines/bench.py` and runs today against an empty
label set. Everything marked *not built* is method we committed to at P0 and have
not implemented, and saying so here is cheaper than letting a reader assume the
harness computes a number it has never computed. The split was invisible until P10:
this page described calibration plots and severity matrices in the present tense
next to precision and recall, which are the only two things the harness has ever
produced.

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

*Not built:* a severity in {cosmetic, moderate, significant}, a
**labeler-confidence** flag, and an `ambiguous` class scored separately. This page
has described all three since P0 and `bench.py` reads none of them - `Label` carries
`asset_id`, `type`, `box` and `note`, and nothing else. The `ambiguous` idea is the
one worth keeping: a model that is uncertain exactly where a human is uncertain is a
good model, and a harness with nowhere to put those cases either drops them silently
or scores them as failures. Neither is what this section promised.

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

*Not built*, and each one is a number this page has implied we have:

- **F1.** Both inputs exist; nothing combines them.
- **Precision-at-high-confidence (>= 0.8)** - described here as "the number that
  matters most, because the report visually privileges high-confidence findings",
  and never computed. The harness reads `confidence` only to order greedy matching.
- **Severity confusion matrix.** Over-calling severity is its own failure and should
  be measured separately from detection. It cannot be: labels carry no severity.
- **Calibration.** Bucket findings by stated confidence and compare to observed
  correctness. A model that says 0.9 and is right 60% of the time is lying to the
  buyer even when the finding is real. There is no reliability plot in `bench/` and
  no code that would produce one.

The gap has cost nothing so far because there is nothing to score. It becomes real
the day the first labeled session lands, and the honest order is to close it before
then rather than discover mid-measurement that the metric we called most important
was never implemented.

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

It writes `bench/results/latest.json` and prints a fixed-width summary table. It does
**not** emit markdown. What makes the published page generated rather than typed is
the direction of the data: `registry.py` reads `latest.json`, computes
`enabled_for_paid` from it, and `docs/ACCURACY.md` publishes what the registry
computes. There is no second place a precision figure can originate.

## Anti-gaming rules

- No threshold tuning on the eval set after seeing per-image results; tuning happens
  on a separate dev split.
- No removing an image because the model does badly on it.
- Any change to the eval set is a commit that touches only the eval set, with a reason.
