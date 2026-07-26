# DECISIONS

Every judgment call made without asking. Newest at the bottom. Format: what was
ambiguous, what was chosen, what it costs.

---

### D-001 - Python 3.12 instead of 3.11
**P0.** The brief specifies Python 3.11; the WSL install ships 3.12.3 and no 3.11 is
present. Adding a 3.11 via deadsnakes/pyenv costs setup time and a second toolchain to
keep alive, and nothing in the planned dependency set (pydantic, pillow, numpy,
librosa, anthropic) requires 3.11. Chose 3.12.3, pinned in `pyproject.toml` as
`requires-python = ">=3.12"` and in CI so local and CI cannot drift. Cost: if a future
dependency is 3.11-only we pay the pyenv setup then instead of now.

### D-002 - Contract sync: Pydantic emits, zod validates, CI enforces
**P0.** Two languages need one schema, and the two ways to do it are code generation
(one source, generated other side) or dual definition with a drift test. Generation
means a build step, a generator dependency, and generated files in review diffs.
Chose **dual definition with a hard drift gate**: Python Pydantic models are the
emitter, TypeScript zod schemas are the consumer, and a CI test runs the fixture
inspection in Python and validates the emitted JSON against the zod schemas. Drift
fails the build at the exact point it would have hurt - the report the web app has to
render. Cost: a schema change is edited in two files. That is a real cost and it is
accepted because the failure mode is loud, immediate, and impossible to ignore.

### D-003 - Laws are code and tests, not prose
**P0.** A law in a markdown file is a suggestion. Each law that can be mechanized was
mechanized: TRUTH as a Pydantic validator that refuses evidence-free findings,
SAFETY-CRITICAL as a post-pipeline clamp with an adversarial test, BANNED LANGUAGE as
a test that scans copy and prompt files, COGS as a meter that prints on every run.
`docs/LAWS.md` names the file and test for each. Cost: some rigidity - a genuinely
evidence-free finding type would need a law amendment to ship. That rigidity is the
point.

### D-004 - Safety lock is a post-pass clamp, not a prompt instruction
**P0.** The safety-critical lock could be implemented by telling the model not to
assess brakes. Prompt instructions are probabilistic; a clamp is not. Chose to let the
model say whatever it says and then **discard** any finding touching a locked system
in a deterministic final pass, replacing the section with the fixed mechanic-required
output. The prompt *also* says not to, as defense in depth, but the guarantee lives in
`safety.py`. This is what makes the claim in LIABILITY section 3 demonstrable in a
test rather than merely intended.

### D-005 - Locked-system observations survive as referrals, but never as verdicts
**P0.** Strictly dropping every locked-system output would also drop "there is fluid
pooled behind the front wheel," which is precisely what a buyer needs to hear. Chose
an asymmetric rule: an observation near a locked system may be surfaced as a
`mechanic_referral` item with its evidence, but it can never carry a pass/fail, a
severity on the locked system, or a confidence-weighted verdict. We can raise an
alarm; we cannot sound an all-clear. Cost: the clamp is more complex than a blanket
drop, so the adversarial test covers both directions - a fabricated all-clear is
removed, a fabricated alarm is downgraded to a referral rather than deleted.

### D-006 - No estimated $/report in UNIT_ECONOMICS.md
**P0.** The obvious move is a plausible cost estimate for the model. Refused: an
invented number written in a doc becomes load-bearing and never gets revisited, and
this project's entire premise is not fabricating figures. Documented the assumptions
and the input counts, left the dollar total blank until `CostMeter` measures one, and
fixed the decision rule in advance instead - **>$5 inference per report does not ship
at $25**. A pre-committed threshold is more useful than a made-up point estimate.

### D-007 - Safety-locked rows get a color off the severity ramp
**P0.** Rendering "mechanic required" in grey makes it read as absent; in red it reads
as a failing grade. Chose purple (`--tk-locked`), deliberately not on the
info/minor/major/critical ramp, so a locked row is visually a *different kind of
statement* rather than a point on the good-bad axis. Same reasoning drove
`--tk-unknown` being legible rather than faded: "cannot determine" is a first-class
output under LAW 1 and must not look disabled.

### D-008 - Box-match IoU set at 0.4, with a tighter number reported alongside
**P0.** Detection convention is IoU 0.5. For this product the useful claim is "there
is rust on this rocker panel," not pixel-exact localization, and a strict threshold
would score a correct, useful, well-placed box as a miss. Chose 0.4 as the headline
threshold with a stricter figure published next to it so the choice is visible rather
than hidden. Fixed now, before any results exist, per the anti-gaming rules in EVAL.md.

### D-009 - Fixture mode is the default, live API is opt-in
**P0.** No `ANTHROPIC_API_KEY` exists in this environment and CI must never need one
(LAW 7). Chose `TIREKICK_MODE=fixture` as the default in code, not just in CI config,
so the failure mode of a missing key is a deterministic cached run rather than a
crash - and live calls require explicitly setting `TIREKICK_MODE=live`. Cost: it is
possible to believe you are testing live behaviour when you are not, so every run
prints its mode in the header banner and stamps it into the report JSON.

### D-010 - P0 fixture media is synthetic and labeled as such
**P0.** The end-to-end fixture run needs media, and there are no real car photos in
hand. Using photos found online would violate LAW 3; inventing findings about a real
car would violate LAW 1 outright. Chose **generated synthetic images and a synthesized
audio tone** - obviously artificial, not photographs of any car - with cached model
responses that are hand-authored placeholders, all declared in
`fixtures/PROVENANCE.md` and stamped `synthetic: true` in the fixture manifest. These
prove the pipeline shape and the schema. They are not evidence of anything about any
vehicle and no accuracy claim will ever cite them. Real media arrives in P2 via the
founder capture reps.

### D-011 - Fixture mode freezes its own clock
**P0.** `generated_at` was stamped from the wall clock unless `--generated-at` was
passed, which made the golden report differ on every run: the committed fixture
churned, `git diff` was never clean, and the dossier snapshot test would have been
regenerated so often that nobody would read its diff. A reproducibility guarantee
that depends on remembering a flag is not a guarantee. Chose to default
`generated_at` to a fixed constant whenever `mode == "fixture"`, in
`dossier.py::_default_generated_at`, with live runs still stamping real time and an
explicit `--generated-at` still overriding both. Cost: a fixture report shows a
timestamp that is obviously not when it was generated - which is correct, because a
cached run has no meaningful generation time. Locked by
`test_fixture_mode_freezes_its_own_clock` and by the `fixture:clean` gate, which
fails the build if a run leaves the committed report dirty.

### D-012 - Cost is shown in the P0 report, at the bottom, unstyled
**P0.** LAW 5 requires per-report cost to be visible, but a "$0.0000" line rendered
near the verdict invites the buyer to price the analysis rather than read it. Chose
to render the cost block as the last section of the dossier under "Run metadata",
present and unhidden but visually terminal. It is internal-facing in P0 and becomes
a real decision input when live inference has a measurable price. Cost: a buyer who
reads to the bottom sees an implementation detail. That is the cheaper mistake than
hiding a number the laws say we publish.

### D-013 - The GitHub repo is created private, not public
**P0.** The brief authorized creating `github.com/vineetsista/tirekick` via `gh` when
`gh` is authenticated, but did not specify visibility, and visibility is the one
part of that action that is hard to walk back: a public repo is indexed, forkable,
and archived by third parties within minutes, while a private repo can be made
public in one click. Chose private. There is a real argument for public - the laws
and the accuracy page are the differentiator, and building them in the open is
evidence we meant them - but that argument is the founder's to make, not a default
to take on his behalf. Cost: the "built in the open" signal is deferred. Reversal is
one command, and it is written into the FOUNDER REPS in `phase_reports/PHASE_0.md`.

### D-014 - A failed check digit rejects a North American VIN and only warns on others
**P1.** ISO 3779 defines a check digit in position 9, but it is mandatory only for
vehicles built for the North American market; manufacturers elsewhere commonly
ignore it. Treating every mismatch as a hard error would reject valid VINs on
imported cars, and treating none of them as an error would let the commonest typo
through on the vehicles where the arithmetic actually holds. Chose to gate on the
first character of the WMI: 1-5 means the digit is required and a mismatch is a
refusal to look anything up, anything else means the digit is optional and a
mismatch is reported as "could not verify" while the lookup proceeds. Cost: a
mistyped VIN on an imported car still reaches vPIC, where it will simply fail to
decode - which the report then surfaces as a decode error rather than as a typo.

### D-015 - Complaint responses are reduced to counts before they touch the disk
**P1.** One complaint query for one model year returns up to several megabytes of
narratives written by members of the public, each carrying a partial VIN, a date,
a location, and often an account of someone's crash. TIREKICK needs the counts and
nothing else. Committing the raw bodies would put thousands of strangers' accident
descriptions into a git repository, permanently, to compute a histogram. Chose to
reduce in `sources.py::_reduce_complaints` before caching - counts by component,
crash/fire/injury/death totals, nothing more - and to carry the SHA-256 of the
original response body in the envelope so the reduction stays traceable to the
exact bytes it came from. Cost: the cache is not a faithful replay of the API, so
a future field we decide we want requires a refetch rather than a re-parse. Worth
it. The 2003 Accord alone drops from about 2 MB to 1.1 KB.

### D-016 - Recalls are model-scoped, and the report says so three times
**P1.** NHTSA publishes recall campaigns keyed to make/model/year and publishes no
public per-VIN remedy status - there is no endpoint that answers "was this done on
this car". A report that lists four campaigns under a masked VIN will be read as
"this car has four open recalls", which we do not know. Chose to carry the scope
in three places rather than one: `VehicleRecord.recall_scope` above the list, a
sentence inside every finding's own detail text, and a seller question phrased as
a question rather than an accusation. Three repetitions is deliberate - the caveat
has to survive being skimmed, and it has to survive a single finding being read on
its own. Locked by `test_no_recall_is_presented_as_outstanding_on_this_vehicle`,
which asserts the wording on all five golden VINs. Cost: the recall section reads
more hedged than a competitor's will.

### D-017 - Title-brand matches are classified, and a denial produces nothing
**P1.** A history report that says "Salvage: None" contains the word "salvage".
The naive scan reports a salvage indicator on a clean car, which is precisely the
error ACCURACY.md names as the one that costs a buyer a good deal. Chose to
classify every match as asserted, denied, or ambiguous: denied produces no finding
at all, ambiguous ships at reduced severity saying in as many words that we could
not read the line, and asserted ships at full severity with the line quoted
verbatim so the buyer checks our reading in one glance. The first implementation
of this got it wrong in the most ordinary case - "None reported" carries both a
negation and an assertion verb and was classified ambiguous, which put a salvage
indicator on the demo fixture whose own paperwork denied one. Fixed by matching
negated assertions as a unit, before either signal is counted separately. Nine
denial phrasings are locked in `test_history.py`. Cost: a document that asserts a
brand in wording we have not anticipated ships as ambiguous rather than as major.
That is the right direction to be wrong in.

### D-018 - The eval gate gains a minimum sample size
**P1.** LAW 4 as written in P0 compared a measured precision against a threshold,
and nothing stopped a tiny sample from clearing a high bar. This was not
hypothetical: P1 decodes five VINs correctly, and 5/5 "clears" a 0.99 gate while
being statistically almost empty - the 95% confidence interval on five successes
runs down to roughly 0.55. Added `FindingTypeSpec.min_n`, defaulting to 50, and
`enabled_for_paid` now requires the sample size before it looks at the precision.
The gate table printed on every run gained a column saying which condition is
failing, so "not measured", "n too small" and "below gate" are visibly different
states rather than three ways of printing NO. Cost: nothing ships sooner than the
evidence supports, which is the entire intent.

### D-019 - Golden VINs carry real model codes and an invented serial
**P1.** The gate calls for golden tests on five real VINs, and a real VIN
identifies one physical vehicle belonging to a real person. Publishing five of
them in a public repository, then querying federal databases about them, is a
privacy cost with no testing benefit: the decode exercises the WMI and VDS - the
manufacturer, plant, line, body and engine codes - and never the serial. Chose to
take real WMI and VDS values, set the last six characters to 000000, and recompute
the position-9 check digit so the result is internally valid. All five decode
cleanly against live vPIC with real trim, body class and engine data, and none of
them is anybody's car. Cost: the serial-derived fields vPIC sometimes returns are
untested, and they are fields we do not use.

### D-020 - The complaint model index resolves NHTSA's second vocabulary
**P1.** The recalls and complaints endpoints do not share a model vocabulary, and
neither response says so. Recalls accept "F-150"; complaints return HTTP 400 for
it and index the same truck as "F-150 SUPERCAB", "F-150 REGULAR CAB" and "F-150
SUPER CREW". Two of the five golden vehicles hit this, and the failure mode is the
dangerous kind: an error becomes an empty result, and an empty result renders as
zero complaints, which reads as good news. Chose to query NHTSA's own model index
and resolve most specific first - model plus vPIC's series where there is one, so
a Silverado 1500 is not blended with a 3500; then the exact model name; then every
indexed name beginning with it, aggregated, with the names listed in the scope
sentence and an explicit statement that the VIN does not say which variant this
is. Cost: one extra cached lookup per vehicle, and an aggregated count for trucks
whose cab style the VIN does not encode.

### D-021 - Model-level findings are excluded from the red-flag score
**P1.** Wiring real recall data in took the demo fixture from 62/100 to 100/100 on
the strength of five campaigns against a 2013 Accord. That number said the car was
maximally bad; the evidence said a model year has recall campaigns on file, most
of them years old, all of them free to remedy at any dealer, and none of them
known to be outstanding on this vehicle. Chose to score only findings evidenced on
this vehicle - photographs, audio, the buyer's own paperwork - and to exclude
`open_recall` and `complaint_pattern`, which describe the model. They are still
reported in full at their own severity, and the headline now names them in a
separate clause with their own count. The score returned to 50/100. Cost: a buyer
who reads only the number sees nothing of the recall history, which is why the
headline sentence carries it and the vehicle record section repeats it.
