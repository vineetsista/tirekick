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

**Enforced in code:** `packages/engines/src/tirekick_engines/net.py` - every outbound
request passes `assert_allowed()`, and `ALLOWED_HOSTS` contains only the federal
APIs above. Adding a host is an edit to that file with a DECISIONS entry.
**Tested in:** `packages/engines/tests/test_net.py` - including a case that names
marketplace domains and asserts each is refused, and one that fails if the allowlist
grows past a handful of hosts.

**Recorded by hand, and checked by nothing:** `fixtures/PROVENANCE.md` and
`bench/PROVENANCE.md` are supposed to carry a row per media file. No test walks
either directory and compares it against the document, so the two can disagree
silently - and did. The fixture record omitted the spectrogram from P3 and the
walkaround video and its five extracted frames from P7, and was still omitting all
seven at P10, while the front page claimed every committed file was synthetic. Each
gap opened in the commit that added the artifact and closed in none of the phase
gates after it. This half of LAW 3 is a promise about our
own diligence, which is exactly the kind of claim the rest of this file exists to
stop us from making. It is written down as unenforced rather than dressed up as
enforced.

## LAW 4 - EVAL GATE

No finding type reaches a paid report before it clears its precision threshold on the
labeled eval set.

- Each finding type has a declared threshold and a measured score. The threshold is
  declared in `packages/engines/src/tirekick_engines/registry.py`; the score comes
  from `bench/results/latest.json`, written only by the eval harness. Both are
  published on `docs/ACCURACY.md`, which is where a buyer reads them and where they
  are derived rather than typed.
- A finding type is enabled by a registry flag, not by whether the code happens to
  run. Below threshold means disabled in paid output, even if it works "most of the
  time."
- `docs/ACCURACY.md` publishes the misses. The false positives, the classes we are
  bad at, and the sample sizes that are too small to conclude anything from.
- Sample size is reported with every number. "3 of 3 correct" is written as
  "3/3, n=3, not meaningful."

**Enforced in code:** `packages/engines/src/tirekick_engines/registry.py` -
`FINDING_TYPES` with `enabled_for_paid` per type, and `withheld_types()`, which the
dossier reads so that a measured failure is dropped from the paid report rather than
merely printed as "NO" in a console table.
**Tested in:** `packages/engines/tests/test_dossier.py` - a type is forced to a
measured 0.40 against its 0.85 gate and the report must not carry it. Unmeasured
types are a different state and ship with a generated sentence saying so (D-056).

## LAW 5 - COGS VISIBLE

Every run prints what it cost us.

- Vision tokens, text tokens, audio processing seconds, storage bytes, and the dollar
  total, per report, on stdout and in the report JSON under `cost`.
- Fixture runs print $0.00 and say why - a cached run that hides its zero is worse
  than useless, because it trains us to ignore the number.
- Unit economics live in `docs/UNIT_ECONOMICS.md` and are updated with measured
  numbers, not estimates, from the moment real API calls start.

**Enforced in code:** `packages/engines/src/tirekick_engines/cogs.py` - `CostMeter`.
**Tested in:** `packages/engines/tests/test_cogs.py` - a fixture run must report zero
*and* say why, a live run must price its tokens against the configured model, and an
unpriced model must be charged at the most expensive rate we know of with the figure
labelled an upper bound. What no test can check is whether the per-MTok numbers in
`MODEL_PRICES` still match Anthropic's published prices; that is a dated comment in
the file and a human re-checking it.

## LAW 6 - AI-NATIVE, SAID OUT LOUD

We market the machine. We never oversell it.

- Product copy names the AI in plain words. No "our proprietary technology," no
  "certified," no "inspection" as a bare noun for what we do.
- Confidence bars are shown to the buyer, not hidden behind a summary grade.
- Every report links to `docs/ACCURACY.md` - the same page, with the same misses on
  it, that we would rather a customer not read. That link is not in a footer at 9px.
- Claims in marketing are traceable to a measured number in ACCURACY.md or they do
  not ship.

**Enforced in code:** `packages/engines/src/tirekick_engines/copy_rules.py` - the
banned-phrase scan, which covers "certified", "we inspected", "inspected by" and the
rest of LIABILITY section 5, across prompts, engine strings and web copy.
**Tested in:** `packages/engines/tests/test_liability_copy.py` (the scan runs over
real source files, and a guard-on-the-guard stops the exemption list swallowing
product code); `apps/web/src/components/Marketing.test.tsx` (the landing page is
checked against what the report actually does, not merely for banned words - D-037);
`apps/web/src/components/ReportView.test.tsx` (the report links `/accuracy`).

**Not checked by anything:** that the accuracy link is not "in a footer at 9px" -
nothing asserts its size or position - and the last clause above. There are no
measured numbers yet, so "traceable to a measured number" is currently satisfied by
there being no accuracy claims to trace; when the first number exists, this becomes
a rule with nothing enforcing it.

## LAW 7 - GREEN GATES

Tests and CI gate every phase.

- Engine golden fixtures: committed media + VIN samples produce expected structured
  findings, byte-comparable.
- Overlay render tests, report snapshot tests, and an e2e upload -> paid dossier test.
- TypeScript strict, ruff, mypy. A phase does not end with a red gate; it ends with a
  tag.
- CI runs with **no** `ANTHROPIC_API_KEY`. Fixture mode is the default, so a fork with
  no secrets gets a green build.

**Enforced in code:** `scripts/gates.sh` - the one command CI runs, so a green local
run and a green CI run mean the same thing. The `fixture:clean` gate is what makes
"byte-comparable" true: it regenerates the report and the teaser and fails on any
diff.
**Tested in:** `packages/engines/tests/test_laws_are_kept.py` - this file is parsed,
every path it names must exist, every law must still say the thing it cannot lose,
and `scripts/gates.sh` must still invoke the suites the laws rely on. It was written
because LAW 7 promised an e2e test that did not exist for six tagged phases and
nothing noticed (D-042). It cannot tell whether a test is any good; it can tell
whether a law is pointing at something real.

---

## Amending a law

A law changes only by editing this file, in a commit that does nothing else, with a
`DECISIONS.md` entry stating what changed and what it costs the buyer. If a law ever
gets in the way of shipping, the law wins and the ship date moves.
