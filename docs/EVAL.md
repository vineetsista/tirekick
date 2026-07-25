# EVAL METHODOLOGY

How TIREKICK measures itself. Written at P0 so that the method is fixed *before* we
see any results and get tempted.

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

## The eval set (built in P2)

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

Each image gets: class label(s), a bounding box per instance, a severity in
{cosmetic, moderate, significant}, and a **labeler-confidence** flag. Images where the
labeler cannot tell are labeled `ambiguous` and scored separately - they are not
quietly dropped, because a model that is uncertain exactly where a human is uncertain
is a good model, and hiding those cases would conceal that.

Boxes count as a hit at IoU >= 0.4. The threshold is deliberately loose: for a buyer,
"there is rust on this rocker panel" is the useful claim, and pixel-exact
localization is not what they are paying for. A tighter IoU is reported alongside as a
secondary number.

## Metrics

- Per finding type: precision, recall, F1, at the configured confidence threshold.
- Precision-at-high-confidence (>= 0.8): the number that matters most, because the
  report visually privileges high-confidence findings.
- Severity confusion matrix: over-calling severity is its own failure and is measured
  separately from detection.
- **Calibration**: bucket findings by stated confidence and compare to observed
  correctness. A model that says 0.9 and is right 60% of the time is lying to the
  buyer even when the finding is real. Reliability plot in `bench/`.

## Audio (P3)

A separate, smaller, and more honest exercise. Labeled clip set with the true
condition established by something other than listening - a mechanic's diagnosis, a
known-fault vehicle, or a documented repair. Clips where "the label" is just someone's
opinion of the sound are not ground truth and are excluded.

Expectation set in advance: this engine will be the weakest, its limits go at the top
of ACCURACY.md, and if precision does not clear 0.70 it ships as
"listen for yourself, here is the spectrogram and here is what to ask" with no
anomaly claims at all.

## Running

```
pnpm run bench          # (P2+) scores the eval set, writes bench/results/
```

Outputs a machine-readable results file and the exact markdown tables that go into
ACCURACY.md - so the published page is generated, not typed.

## Anti-gaming rules

- No threshold tuning on the eval set after seeing per-image results; tuning happens
  on a separate dev split.
- No removing an image because the model does badly on it.
- Any change to the eval set is a commit that touches only the eval set, with a reason.
