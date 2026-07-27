# TIREKICK ACCURACY

**As of P2: there are still no accuracy numbers, because there have still been no
measurements.**

P2 built the machinery that will produce them - the vision engine, the prompts, and
the eval harness that scores model output against human labels. What it did not
build is a labeled set, because that needs photographs of real cars and those do
not exist yet. The harness runs, correctly reports that it has nothing to score,
and every finding type stays disabled.

This page is generated from `bench/results/latest.json`. There is no second place
to type a precision figure, so a number here that is not in that file cannot
happen.

That sentence is the important one on this page, and we would rather publish it than
publish an estimate. Numbers appear here in P2 (vision) and P3 (audio), measured on a
labeled eval set, with sample sizes and misses included.

P1 wired in the federal data - VIN decode, recalls, owner complaints, and a scan of
history documents you upload. None of it moved a single number in the table below,
and the reason is worth stating plainly, because it is the sort of thing a product
would normally quietly skip.

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
| fluid_leak_indicator | 0.75 | not measured | 0 | disabled - awaiting P2 |
| dash_warning_light | 0.90 | not measured | 0 | disabled - awaiting P2 |
| odometer_reading | 0.95 | not measured | 0 | disabled - awaiting P2 |
| odometer_wear_mismatch | 0.80 | not measured | 0 | disabled - awaiting P2 |
| audio_anomaly | 0.70 | not measured | 0 | disabled - awaiting P3 |
| vin_decode | 0.99 | not measured | 0 | disabled - awaiting P1 |
| open_recall | 0.99 | not measured | 0 | disabled - awaiting P1 |
| complaint_pattern | n/a - summary only | n/a | 0 | disabled - not measured |
| title_brand_indicator | 0.90 | not measured | 0 | disabled - awaiting a labeled document set |
| price_comparison | n/a - arithmetic on user comps | n/a | 0 | disabled - awaiting P5 |

A measurement also has to be big enough to mean anything. Since P1 each finding type
carries a minimum sample size (50 by default) that a measurement must reach before it
can clear its gate at all. Five correct answers out of five is not evidence; the
confidence interval on it runs down to about 0.55.

## What P1 checked, and why it is not on the table above

P1 runs five real VINs end to end against a committed snapshot of what NHTSA
returned. Every field we render matches the federal source, and all 39 recall
campaigns across those five vehicles are reproduced faithfully.

**That is a plumbing check, not an accuracy measurement, and we are not going to
print it as one.** It answers "did we copy the database correctly", which is a
question about our code. It does not answer "is this finding true of the car in
front of you", which is the question you are paying us to answer. Putting a 1.00 in
the precision column for recalls would be technically defensible and would be read
by every single person as "TIREKICK is 100% accurate about recalls" - which would
imply we know those recalls are outstanding on your car. We do not, and we cannot.
See the recall note below.

The title-brand scanner is tested against fifteen hand-written document lines, nine
of which deny a brand. It gets all fifteen right. That number is also not on the
table, for a blunter reason: we wrote those lines ourselves, and a scanner scored
against its author's own examples is measuring nothing. A labeled set of real
history documents is what would count, and we do not have one yet.

The same objection applies with more force to the vision engine, so P2 did not
score it at all. Running the model against our own synthetic fixture drawings would
produce a number, and the number would describe how well the model reads pictures we
drew for it to read.

## How the numbers will be produced

`bench/README.md` is the protocol, and two rules in it decide whether any of this
means anything.

**The set must contain cars in good condition.** A model that reports rust on every
photograph scores perfectly against a set where every photograph has rust. Precision
cannot be measured without images whose correct answer is silence.

**Labels are written before the model runs, and are never edited because the model
disagreed.** If a label turns out to be wrong, it gets fixed and the fix gets
recorded in the session file. An eval set quietly reconciled with model output is a
description of the model.

Both were fixed in P0's `docs/EVAL.md`, before there was anything to be tempted by.

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
- **Whether a recall was actually performed on your car.** NHTSA publishes recall
  campaigns for a make, model and year. It publishes no public record of whether the
  work was done on any individual vehicle. So when this report lists recalls, it is
  listing what *could* apply to a car like yours - not what is outstanding on yours.
  Any dealer will check by VIN over the phone, and recall work is free.
- **Your title status.** We query no title registry. NMVTIS, the federal title
  database, is not openly queryable, and the commercial reports built on it are
  licensed products we do not resell. When this report names a title brand, it is
  quoting a document *you* uploaded, with the line shown so you can check it.
  Confirm any brand with your state motor vehicle agency before you buy.
- **A document we could not read.** Scanned or photographed paperwork is not scanned
  for title brands yet - that needs OCR, which arrives with the vision work. An
  unreadable document is reported as unread, never as clean.

## Known failure modes

Populated with real, observed failures starting in P2. Placeholder categories we
expect to have to write about honestly: wet paint read as gloss defect, shadow read as
dent, aftermarket trim read as damage, low-light interiors, phone HDR artifacts, and
the general problem that a seller photographs the good side.

---

*No number appears on this page that is not reproducible from `bench/`.*
