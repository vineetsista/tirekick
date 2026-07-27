# BENCH - the labeled eval set

This directory decides what TIREKICK is allowed to sell.

Under LAW 4, no finding type appears in a paid report until its measured precision
clears its threshold here. Nothing else in the codebase can put a precision number
in front of a buyer: `docs/ACCURACY.md` and the gate table both read
`bench/results/latest.json`, and that file is written only by `tirekick bench`.

As of P2 it is **empty**, which is why 0 of 16 finding types are enabled.

```
bench/
  labels/      one JSON file per capture session - the ground truth
  inspections/ manifests + media for each capture session
  reports/     generated output, scored against labels
  results/     latest.json, read by the eval gate
```

Run it:

```bash
packages/engines/.venv/bin/python -m tirekick_engines.cli bench \
    --inspections bench/inspections
```

---

## Capturing

The eval set is only as honest as the photographs in it, and the failure mode is
subtle: **a set of nothing but damaged cars measures enthusiasm, not precision.**
A model that reports rust on every image scores perfectly against a set where
every image has rust. So the set needs cars in good condition, and photographs
where the correct answer is that there is nothing to report.

Per vehicle, eight photographs:

| # | Shot | Why it is in the set |
|---|---|---|
| 1 | Front three-quarter | damage, repaint, panel gaps |
| 2 | Rear three-quarter | same, plus the panel most often replaced |
| 3 | Driver side, square on | rocker panel - where rust actually starts |
| 4 | Passenger side, square on | the side sellers photograph less |
| 5 | Interior, driver's seat and wheel | wear, and the odometer-mismatch check |
| 6 | Dash, **engine running** | warning lamps. Not the ignition self-test |
| 7 | Odometer, filling the frame | OCR, at the strictest gate we have (0.95) |
| 8 | One tire, tread facing camera | tread and wear pattern |

Rules that matter more than they look:

- **Daylight, overcast if possible.** Direct sun creates shadows that read as
  dents, and this is the single largest source of false positives we expect.
- **Do not clean the car first.** A washed car hides exactly what we are testing.
- **Shoot the bad side too.** The instinct is to photograph what looks good.
- **Photograph at least one car you would describe as being in good condition.**
  Without it, precision cannot be measured at all.
- Engine bay only when it is safe and the engine is cool.
- No editing, no filters, no HDR retouching. Phone default is right.
- Plates and faces get blurred before anything is committed.

## What to write down at the same time

For each vehicle: year, make, model, VIN, indicated mileage, and - this is the
part that matters - **everything you know to be true about its condition**,
including things a photograph cannot show. What the seller said. What a mechanic
found. What you can feel with a hand on the panel but cannot see.

The things a photograph cannot show do not become labels. They go in the notes,
and they are how we find out what this product is structurally blind to.

## Labeling

One file per capture session in `labels/`. Copy `labels/TEMPLATE.json`.

```json
{
  "session": "capture-01",
  "labeled_by": "vineet",
  "labeled_at": "2026-08-01",
  "vehicle": "2015 Subaru Outback, VIN masked, 96k indicated",
  "assets": {
    "photo_01": {
      "labels": [
        {
          "type": "rust_corrosion",
          "box": { "x": 0.11, "y": 0.62, "w": 0.24, "h": 0.09 },
          "note": "bubbling along driver rocker, paint lifting"
        }
      ]
    },
    "photo_02": { "labels": [] }
  }
}
```

`"labels": []` is not the same as leaving the asset out.

- **Empty list** - a human looked at this photograph and there is nothing to
  report. Any finding here is a false positive. **This is the only way a false
  positive can be counted, so most of the set should look like this.**
- **Absent** - nobody looked. Predictions on it are ignored entirely, because we
  do not know whether they are right.

Boxes are normalized: `x`,`y` is the top-left corner, all four values between 0
and 1. They do not need to be tight. A box matches at IoU 0.4 because the useful
claim is "there is rust on this rocker panel", not pixel-exact localization
(D-008). The stricter 0.5 figure is computed on the same run and published beside
it, so the choice stays visible.

### Label what is there, not what we can find

Label every instance you can see, including ones you expect the model to miss.
That is what makes recall mean something. A label set trimmed to what the model
finds is a label set that says the model is perfect.

### Locked systems

Do not label brakes, airbags, structure, or steering. We have said in writing
that we cannot assess them from a photograph, and scoring them would mean
asserting ground truth we have disclaimed. Observations near them leave the
pipeline as mechanic referrals, and the harness counts those and reports them as
unscored (LAW 2).

## Anti-gaming rules

Fixed in P0, before any results existed (`docs/EVAL.md`):

1. **Label before you run.** Writing labels after seeing model output turns the
   eval into a description of the model.
2. **Never edit a label because the model disagreed with it.** If the model is
   right and the label is wrong, fix it and write down that you did, in the
   session file's notes.
3. **Thresholds do not move to make a number pass.** Changing `HEADLINE_IOU` or a
   precision gate needs a DECISIONS entry explaining what it now means.
4. **Publish the misses.** `docs/ACCURACY.md` carries recall and known failures,
   not just precision.

## Privacy

Real vehicle media in this repository means the repository stays **private** until
a plate-and-face blur step exists and has been run over everything here (D-022).
Committing one unblurred plate publishes a stranger's identifier permanently, and
`git rm` does not undo it.
