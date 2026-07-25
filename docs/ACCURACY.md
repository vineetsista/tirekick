# TIREKICK ACCURACY

**As of P0: there are no accuracy numbers, because there have been no measurements.**

That sentence is the whole page right now, and we would rather publish it than
publish an estimate. Numbers appear here in P2 (vision) and P3 (audio), measured on a
labeled eval set, with sample sizes and misses included.

This page is linked from the product itself (LAW 6). It is written for the buyer, not
for us.

---

## How to read this page, once it has numbers

- **Precision** answers: when TIREKICK says it sees rust, how often is there rust?
  This is the number that protects you from being scared off a good car.
- **Recall** answers: of the rust that is really there, how much does TIREKICK find?
  This is the number that tells you how much a clean report is worth. It will always
  be the weaker of the two, because a photograph does not show what is under the car.
- **n** is how many examples the number came from. A number with a small n is a hint,
  not a fact, and we label it that way.

## Finding types and their gates

Each finding type must clear its precision threshold on the labeled eval set before it
appears in a paid report (LAW 4). Types below threshold stay disabled.

| Finding type | Precision gate | Measured | n | Status |
|---|---|---|---|---|
| exterior_damage | 0.85 | not measured | 0 | disabled - awaiting P2 |
| rust_corrosion | 0.85 | not measured | 0 | disabled - awaiting P2 |
| repaint_indicator | 0.75 | not measured | 0 | disabled - awaiting P2 |
| tire_tread_estimate | 0.80 | not measured | 0 | disabled - awaiting P2 |
| interior_wear | 0.80 | not measured | 0 | disabled - awaiting P2 |
| dash_warning_light | 0.90 | not measured | 0 | disabled - awaiting P2 |
| odometer_reading | 0.95 | not measured | 0 | disabled - awaiting P2 |
| odometer_wear_mismatch | 0.80 | not measured | 0 | disabled - awaiting P2 |
| audio_anomaly | 0.70 | not measured | 0 | disabled - awaiting P3 |
| vin_decode | 0.99 | not measured | 0 | disabled - awaiting P1 |
| open_recall | 0.99 | not measured | 0 | disabled - awaiting P1 |
| complaint_pattern | n/a - summary only | n/a | 0 | disabled - awaiting P1 |
| price_comparison | n/a - arithmetic on user comps | n/a | 0 | disabled - awaiting P5 |

Thresholds were set at P0 by asking, per type, "at what error rate would this finding
cost a buyer real money or a real car?" The rationale per threshold is in
`docs/EVAL.md`. They are stricter for readings we present as facts (odometer OCR,
recall lookups) than for judgments we present as opinions (repaint cues).

## What we cannot assess at all

This section will never be empty, and it is the most important section on the page.

- Brakes, airbags and restraints, frame and structural integrity, steering. Hard-locked
  off (LAW 2). Not a limitation we intend to remove.
- Anything requiring a lift, wheels off, a scan tool, a test drive, or a fluid sample.
- Transmission behavior under load. Engine internals. Head gasket condition.
- Flood damage that has been cleaned up competently.
- Whether the seller is telling the truth.

## Known failure modes

Populated with real, observed failures starting in P2. Placeholder categories we
expect to have to write about honestly: wet paint read as gloss defect, shadow read as
dent, aftermarket trim read as damage, low-light interiors, phone HDR artifacts, and
the general problem that a seller photographs the good side.

---

*No number appears on this page that is not reproducible from `bench/`.*
