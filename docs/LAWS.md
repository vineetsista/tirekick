# TIREKICK LAWS

These are not guidelines. They are constraints that hold even when they cost us a
sale, a demo, or a launch date. Where a law can be expressed as code or as a test,
it is expressed as code or as a test, and the location is named here.

---

## LAW 1 - TRUTH

Every finding cites its evidence, and that evidence is visible in the report.

- A finding carries at least one `Evidence` object: an image region (asset + bounding
  box), an audio segment (asset + start/end timestamp), or a data record (source,
  record id, retrieved-at).
- A finding with zero evidence is not a weak finding. It is not a finding. It is
  rejected at construction time.
- Every finding carries a confidence in [0, 1] and a stated basis for that confidence.
- `cannot_determine` is a first-class verdict with equal visual weight in the report.
  A section that says "the photos do not show this" is a correct section, not a gap.
- We never infer a finding from a fact the buyer gave us and then present it back as
  something we observed.

**Enforced in code:** `packages/engines/src/tirekick_engines/models.py` - `Finding`
requires `evidence` with `min_length=1`; empty evidence raises `ValidationError`.
**Tested in:** `packages/engines/tests/test_laws.py::test_truth_law_*`

## LAW 2 - SAFETY-CRITICAL

Brakes, airbags/restraints, frame and structure, and steering are never cleared
remotely. Ever. Not at high confidence, not on a clean car, not for a friend.

- These systems are hard-locked to a single output: **not remotely verifiable -
  independent mechanic required**.
- The lock is applied *after* every engine has run, as a final pass over the report.
  A model that returns "brakes look fine, confidence 0.98" gets clamped and its claim
  is dropped, not displayed.
- The lock is one-directional in exactly one respect: we may still surface an
  *observation* that argues for more scrutiny (visible fluid at a wheel, a lit ABS
  lamp) as a `mechanic_referral` item, because warning a buyer is not the same as
  clearing them. We never convert such an observation into a pass, a grade, or a
  severity score for the locked system.
- We are decision support for a conversation with a mechanic. We are not an
  inspection, a certification, a warranty, or a substitute for either.

**Enforced in code:** `packages/engines/src/tirekick_engines/safety.py` -
`LOCKED_SYSTEMS` and `apply_safety_law()`.
**Tested in:** `packages/engines/tests/test_laws.py::test_safety_law_*` - including an
adversarial test that feeds a fabricated high-confidence "brakes are good" finding
through the pipeline and asserts it never reaches the report.

## LAW 3 - NO SCRAPE

User-provided media and identifiers only.

- No bulk marketplace scraping. No automated listing harvesting. No crawler, no
  headless browser walking a classifieds site, not now and not as a "temporary" way
  to build an eval set.
- Comparable listings are pasted in by the user, one at a time, deliberately.
- Demo and eval media come from our own cameras or from public media saved manually,
  one file at a time, with provenance recorded per file.
- Public APIs offered by the issuing body for this purpose (NHTSA vPIC, NHTSA
  recalls/complaints) are used within their documented terms, cached, and cited.

**Enforced in practice:** `fixtures/PROVENANCE.md` and `bench/PROVENANCE.md` record
the origin of every media file. No HTTP client in this repo targets a marketplace
domain; the allowed-host list lives in
`packages/engines/src/tirekick_engines/net.py`.

## LAW 4 - EVAL GATE

No finding type reaches a paid report before it clears its precision threshold on the
labeled eval set.

- Each finding type has a declared threshold and a measured score. Both live in
  `docs/ACCURACY.md`.
- A finding type is enabled by a registry flag, not by whether the code happens to
  run. Below threshold means disabled in paid output, even if it works "most of the
  time."
- `docs/ACCURACY.md` publishes the misses. The false positives, the classes we are
  bad at, and the sample sizes that are too small to conclude anything from.
- Sample size is reported with every number. "3 of 3 correct" is written as
  "3/3, n=3, not meaningful."

**Enforced in code:** `packages/engines/src/tirekick_engines/registry.py` -
`FINDING_TYPES` with `enabled_for_paid` per type.

## LAW 5 - COGS VISIBLE

Every run prints what it cost us.

- Vision tokens, text tokens, audio processing seconds, storage bytes, and the dollar
  total, per report, on stdout and in the report JSON under `cost`.
- Fixture runs print $0.00 and say why - a cached run that hides its zero is worse
  than useless, because it trains us to ignore the number.
- Unit economics live in `docs/UNIT_ECONOMICS.md` and are updated with measured
  numbers, not estimates, from the moment real API calls start.

**Enforced in code:** `packages/engines/src/tirekick_engines/cogs.py` - `CostMeter`.

## LAW 6 - AI-NATIVE, SAID OUT LOUD

We market the machine. We never oversell it.

- Product copy names the AI in plain words. No "our proprietary technology," no
  "certified," no "inspection" as a bare noun for what we do.
- Confidence bars are shown to the buyer, not hidden behind a summary grade.
- Every report links to `docs/ACCURACY.md` - the same page, with the same misses on
  it, that we would rather a customer not read. That link is not in a footer at 9px.
- Claims in marketing are traceable to a measured number in ACCURACY.md or they do
  not ship.

## LAW 7 - GREEN GATES

Tests and CI gate every phase.

- Engine golden fixtures: committed media + VIN samples produce expected structured
  findings, byte-comparable.
- Overlay render tests, report snapshot tests, and an e2e upload -> paid dossier test.
- TypeScript strict, ruff, mypy. A phase does not end with a red gate; it ends with a
  tag.
- CI runs with **no** `ANTHROPIC_API_KEY`. Fixture mode is the default, so a fork with
  no secrets gets a green build.

---

## Amending a law

A law changes only by editing this file, in a commit that does nothing else, with a
`DECISIONS.md` entry stating what changed and what it costs the buyer. If a law ever
gets in the way of shipping, the law wins and the ship date moves.
