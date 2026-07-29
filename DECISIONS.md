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

### D-022 - Real vehicle media means the repository stays private
**P2.** The eval set has to be committed or it is not reproducible - CI cannot score
against photographs that live on somebody's laptop, and an accuracy number nobody
else can recompute is an assertion rather than a measurement. Committing them means
committing photographs of real cars in real streets, which carry number plates and
sometimes faces belonging to people who did not agree to any of this. Chose to
commit the media and hold the repository private until a plate-and-face blur step
exists and has been run over everything in `bench/`. The founder chose this over
the alternatives when asked. Cost: the "built in the open" option from D-013 is
foreclosed for now, and it is no longer one command - `git rm` does not remove
anything from history, so a plate committed today is public the moment the
repository is, forever. That is why the constraint is written here rather than
assumed.

### D-023 - Sonnet 5 is the default, and the eval decides, not the price
**P2.** A report runs 22 model calls over 8 photographs, so the per-image model
choice is essentially the whole of COGS, and the obvious move is to pick the
cheapest model that seems adequate. Set the default to Sonnet 5 on the reasoning
that these passes are constrained detection and transcription against an explicit
schema rather than open-ended reasoning.

Then computed the actual numbers, and they undercut the reasoning: Sonnet 5
projects to $0.34 per report and Opus 5 to $1.71, against a $25 price and a
pre-committed $5 ceiling. A $1.37 difference does not decide anything. Cost was not
a real input to this decision and it was wrong to treat it as one.

So the default stays Sonnet 5 for now, because something has to be the default, and
the decision is explicitly deferred to the eval: when a labeled set exists, both
models are scored on it and the more accurate one wins. `TIREKICK_MODEL` selects,
`MODEL_PRICES` knows both rates, and the cost block names the model that produced
each report so the two can never be compared against the wrong price. Cost: we ship
a default chosen on an argument this entry partly retracts, which is why it says so.

### D-024 - The model is never asked for a repair cost
**P2.** Repair estimates are the single most useful thing a report could carry and
the easiest thing to fabricate. A model will produce a confident dollar band for
any damage in any photograph, and there is nothing behind it - not a parts
catalogue, not a labour rate, not a quote. It is the line a buyer acts on, and they
would be acting on a number we made up. Chose to leave `estimated_cost_usd` out of
the tool schema entirely, rather than asking for it and filtering afterwards: a
field that is not in the schema cannot be returned, and a field that is merely
discouraged eventually gets through. Locked by
`test_the_model_is_never_asked_for_a_repair_cost`. Cost: the negotiation script has
less to work with, and cost bands stay absent until they have a real source. The
P0 fixtures still carry invented bands, which `fixtures/PROVENANCE.md` declares.

### D-025 - Prompts are versioned files inside the scanned surface
**P2.** Prompts began as string literals in `vision.py`, which fails three ways: a
prompt change is invisible in a diff full of Python, a cached response cannot name
the prompt that produced it, and - the one that matters - the banned-language scan
did not cover them. A prompt that uses the vocabulary of official approval teaches
the model to hand it back, where it arrives wearing a confidence score, which is
worse than a banned phrase in our own copy. Chose one Markdown file per prompt with
an `id` and `version` header, added to the LIABILITY scan globs, with the version
stamped into every live response and the full set fingerprinted into the report's
cost block.

The scan immediately caught two violations in the prompts I had just written, both
of them cases of using a banned word in order to forbid it. Rephrased rather than
widening the sanctioned-disclaimer list, which exists for buyer-facing denials and
would be weakened by absorbing internal instructions. Cost: prompts are now package
data that has to ship with an install, declared in `pyproject.toml`.

### D-026 - Audio features are cached, even though computing them is free
**P3.** Audio analysis is deterministic arithmetic over a waveform. No API call, no
cost, no non-determinism - so caching it looks like pure ceremony. It is not: the
computation needs ffmpeg, and LAW 7 says a fixture run needs nothing. Computing
the spectrogram at report time would make the gate that proves fixture mode
dependency-free itself depend on ffmpeg being installed on the runner, which is
the same shape of mistake as the mypy gate that never read its config. Chose to
cache the measured features and the rendered spectrogram, written by
`scripts/refresh_audio_cache.py` and committed, exactly as the federal records
are. Cost: a change to the signal code does not show up in the report until
someone re-runs the script, and the numbers can silently go stale. The spectrogram
is committed alongside, so a stale cache is at least visible as an image that no
longer matches.

### D-027 - The audio engine ships a picture and says nothing
**P3.** P3 produced a working onset detector that locates all three planted
impulses in the fixture clip to within 21ms, at eight times the prominence of the
strongest false positive. It would be one line to label those "possible valvetrain
tick", and the report would look far more impressive for it.

`audio_anomaly` has a 0.70 precision gate and no measurement behind it, and
`docs/EVAL.md` committed in P0 to what happens in exactly this case: the engine
ships as a spectrogram and a list of things to ask a mechanic, with no anomaly
claims attached. Honoured it. The report shows the spectrogram, marks where the
transients are, gives the measured idle frequency, and states in the section
header that no claims are attached to any of it.

The transient copy is the part that took longest to write: it has to be useful
without being a diagnosis. It settled on naming what a transient is, listing the
mundane things that also produce one - a door, a footstep, a sleeve over the
microphone - and saying we are showing where to listen rather than what we heard.
Cost: a competitor will say "knocking detected" and sound better. We will be right
more often.

### D-028 - Implied RPM is shown only when the VIN supplied the cylinder count
**P3.** Firing frequency converts to RPM exactly, given the cylinder count and the
stroke. The arithmetic is not the risk; the input is. Guess four cylinders on a V6
and the answer is wrong by exactly 1.5x - not noisy, not obviously broken, just a
plausible number on a dashboard. Chose to report RPM only when vPIC returned the
cylinder count, and to say in the basis line where the number came from. When the
VIN did not decode, the report shows the dominant frequency and explains why no
RPM follows from it. Cost: a buyer with an unreadable VIN gets a Hz reading
instead of an rpm reading, which is less friendly and more honest.

### D-029 - Redaction is model-proposed and human-signed, and it moved up a phase
**P3.** D-022 made the plate-and-face blur step a blocker: real photographs cannot
be committed without it, the eval set cannot be labelled without them, and no
finding type can ship without the eval set. So it moved from P6 to here, ahead of
its scheduled phase, because the schedule was blocking the gate.

The design decision is who gets the last word. An automatic detector that misses
one plate in fifty is worse than no detector, because it produces a folder
everybody now believes is safe - and `git rm` does not remove anything from
history, so a single miss is permanent the moment the repository goes public.
Chose a three-step flow: the model proposes regions, a person checks every one
against the image and signs with their name, and only then will `apply` blur
anything or `check` pass. `assert_reviewed` fails on absence rather than passing
on it - an image with no record is unreviewed, not empty. "Nothing to redact" is a
legitimate answer that a human has to state explicitly.

Blurring pixelates before it blurs, because Gaussian blur alone is recoverable if
the kernel is known, and re-encodes rather than copies, because the original EXIF
carries the GPS coordinates of somebody's driveway. Cost: capture is now a
two-person-minute-per-image chore rather than a script.

### D-030 - Image encoding: decode small, resize rarely, encode once
**P3.** Found while chasing a test suite that had gone from 2 seconds to 180.
Three separate faults, all in the same twenty lines:

Every image was re-encoded for every pass. A report makes 22 image calls over 8
photographs, so the same bytes were decoded up to four times. Now cached on the
file's identity - path, mtime, size - so editing a file still invalidates it.

`draft()` was being asked for a square target. Pillow picks its DCT scale with
integer division on *both* axes and takes the minimum, so `(1568, 1568)` against a
4032x3024 photo computes `min(2, 1) = 1` and silently does nothing. Passing the
real target box makes libjpeg decode 3.0 megapixels instead of 12.2.

A 1600px fixture photo was being resampled to 1568px - a full-quality pass over
two million pixels to save about 4% of the image tokens. Added a tolerance so that
trade is not made.

Stated as pixel counts rather than as a speedup, deliberately. This machine takes
six seconds to multiply two 2000x2000 matrices, and the drafted decode has
measured *slower* than the full one on pure noise; any timing published from here
would be fiction.

### D-031 - The teaser is a projection, not a redaction
**P4.** The quick way to build a paywall is to send the report and hide the
findings in the browser. It is also not a paywall: the whole product is one
network tab away, and the first person to notice will publish how. Chose to build
a genuinely smaller object in `teaser.py`. What the free route omits was never
serialised - there is no `display: none` anywhere in it.

Two tests guard it from opposite directions. `test_teaser.py` searches the teaser
JSON for every finding title, detail, confidence basis and evidence caption in the
paid report. `TeaserView.test.tsx` does the same against the rendered HTML, by
importing the full report alongside the teaser. The dangerous refactor is one that
keeps the shape and changes what fills it, which a type checker cannot see, so
both tests assert on text rather than on structure. `parseTeaser` additionally
throws if a payload carries any paid-only key, because zod strips unknown keys
silently by default and would have let a whole report through.

### D-032 - The checkout page states how much of the product is measured
**P4.** Writing the purchase flow surfaced the question I had been deferring since
P2: it is now possible to charge $25 for a report in which zero of sixteen finding
types has cleared its accuracy gate. Flagged it in the P3 report rather than
building quietly around it.

The resolution is not to hide the number or to wait. It is `accuracy_statement()`,
generated from the eval-gate registry and rendered above the payment button on
both the teaser and the checkout page. Today it reads: *none of the 16 finding
types has cleared its accuracy threshold yet - 0 have been measured at all.*

It is generated rather than written for one reason. A hand-written sentence gets
softened when it becomes commercially inconvenient, and it will become
commercially inconvenient. A generated one changes only when the measurements
change, and the test asserts it starts saying something better the moment a type
clears its gate. Cost: this is the single worst sentence that could appear next to
a payment button, and it is going to cost conversions. That is the correct price
for the LAW 6 claim that we market the machine and never oversell it.

### D-033 - The pay button does not exist until the acknowledgements are ticked
**P4.** LIABILITY section 4 specifies a checkbox, unticked by default, in its own
paragraph, at the moment of the decision it qualifies. The design rule in that
document is that a disclaimer a user can reach the verdict without reading has not
been placed correctly.

A greyed-out button satisfies the letter and not the rule - it is still a thing to
click at, and the eye goes to it rather than to the text above it. Chose to render
no payment control at all until all three boxes are ticked, so the only thing on
screen to act on is the text. Three acknowledgements, chosen as the three things a
person who felt cheated afterwards would say nobody told them: that this is not a
physical inspection, that the four locked systems cannot be assessed at all, and
that a mechanic should look at the car regardless.

Also decided here: an unconfigured Stripe link renders a panel saying payment is
not connected, never a dead href. A checkout that appears to work and does not is
worse than one that admits it is not ready.

### D-034 - The teaser costs the same to produce as the report it is teasing
**P4.** The teaser is a projection of a finished report, which means every engine
has already run by the time a buyer sees the free page. A teaser therefore costs
the same ~$0.34 of inference as the paid product, and conversion rate multiplies
that directly: at 10% conversion, ten teasers make one paid report cost $3.40.

The obvious optimisation is to run a cheap subset for the teaser and the rest on
payment. Rejected, and not on engineering grounds. The teaser shows a red-flag
score and severity counts. If those are computed from a partial analysis, they
change after payment - a buyer sees 50/100 for free, pays, and gets 72/100. There
is no way to present that which is not either a bait or an apology, and the
version where the number goes *down* after payment is worse.

So the whole analysis runs before anything is shown, the numbers on the free page
are the real ones, and the cost of that sits in `docs/UNIT_ECONOMICS.md` as the
line most likely to decide whether this business works. It is still 86% gross
margin at 10% conversion. It stops working somewhere near 1.5%, and that is a
number worth watching from the first teaser rather than discovering later.

### D-035 - The pricing engine can decline to price
**P5.** The engine could always do the arithmetic. That was the problem: three
listings for a Civic, or two listings for anything, produced a dollar range
formatted identically to one built from twenty relevant comps. Nothing in the
output distinguished them.

Three changes, all of them refusals rather than features. A listing more than two
model years away, or for a different make or model than the VIN decoded to, is
excluded - and the exclusion is *rendered*, because a comp silently dropped is a
comp the buyer believes was counted. Below three usable listings the verdict is
`cannot_determine` and the range is not shown at all, while the listings still
are. And listings that disagree with each other by more than 40% get a note saying
that a range that wide is evidence the listings are not comparable, not evidence
the car is worth anything inside it.

Relevance is only checked when the VIN decoded. No decode means no basis to
exclude on, and excluding on a guess is worse than not excluding.

Cost: a buyer who pastes four listings and gets "cannot determine" will be
annoyed. The alternative is pricing their car against a Civic.

### D-036 - Comps carry a date, and a future date is an error
**P5.** Used-car prices moved by tens of percent inside single years recently, so a
range built from spring listings against an autumn market is wrong in a way no
amount of arithmetic reveals. Comps gained `listed_on`, listings older than 90
days are flagged and still counted - they are the buyer's own research - and comps
with no date at all produce a note saying currency could not be checked rather
than an assumption that they are fresh.

The future-date branch was not designed; the fixture found it. Fixture mode
freezes its clock at 2026-01-01 (D-011), so comps I had dated in July 2026 were
silently treated as extremely fresh - a negative age passes any "older than 90
days" check. A listing dated after the report is a paste error, and it now says
so. Two of this project's own guarantees interacting badly is a better argument
for the frozen clock than any test I would have written on purpose.

### D-037 - The landing page is scanned against the product, not just for banned words
**P6.** The P0 landing page promised "the open recalls on that VIN". P1 established
that NHTSA publishes recalls per model and nothing per vehicle (D-016), added three
separate caveats to the report saying so - and left the front page promising the
thing the report now explicitly refuses to claim. It also advertised walkaround
video analysis, which has never existed in any phase.

Nothing failed, because nothing looked. The banned-language scan checks for
forbidden *phrases*; it cannot notice a true-sounding sentence that the product no
longer supports. Marketing copy drifts silently and always in the same direction.

Added `Marketing.test.tsx`, which renders the landing page and asserts against the
current product: no per-VIN recall claim, no title search, no audio diagnosis, no
features that do not exist, and no clearance language. Plus the positive half - the
banner and the generated accuracy statement both appear above the first call to
action, asserted on position rather than presence, because a disclaimer under the
button is not a disclaimer.

Also, the accuracy statement now appears on the landing page, the teaser and the
checkout page, from one generated source. Three surfaces, one sentence, and it is
the least flattering fact about the product.

### D-038 - The banned-language exemption excuses files by role, never by sentence
**P6.** The copy scan caught `Marketing.test.tsx`, which asserts that the word
"certified" does not appear on the landing page - and therefore contains it. Same
shape as the P2 case where the scan caught the prompts I had just written to
forbid those words.

Chose to exempt test files by suffix, alongside `copy_rules.py`, on the criterion
the scan is actually applying: a surface a buyer can reach. The globs are an
approximation of that, and test files are where the approximation is wrong.

The exemption is the obvious place to hide a real violation - add a file, move on -
so it excuses by role and never by sentence, and
`test_the_exemption_list_does_not_swallow_product_code` asserts that nothing
exempted is a component or a page, and that the landing page, report view, teaser
view, purchase gate and prompts are all still scanned. A guard on the guard.

### D-039 - Walkaround video ships as a frame-selection problem
**P7.** Video was a stated input in the brief and was never built. `kind: "video"`
existed in the schema and `has_video` in coverage, and nothing processed one. In
P6 I removed the claim from the landing page, which made the copy honest and
quietly turned a missing feature into a smaller product. That was the wrong
trade and this reverses it.

The engineering is entirely selection. A 45-second walkaround at 30fps is 1,350
frames; sending them all costs about $30 in image tokens, most of it spent on
motion blur and on the same rear quarter from four angles. So: sample on a fixed
grid, keep the sharpest frame per 1.5-second bucket by variance of the Laplacian,
drop perceptual near-duplicates, cap at 12 frames. Everything that survives goes
through the *same* vision path as an uploaded photograph - classified, routed,
clamped, cited - because a frame is a photograph that arrived inside a video and
does not deserve its own rules.

The payoff is coverage, which is the thing every report so far has had to
apologise for. On the demo fixture, adding the walkaround took coverage from 67%
to 83% by supplying the exterior side and three-quarter views the photographs
never had. A seller photographs the side they want shown; a buyer walking round
the car covers all of it.

The discards are reported, not just the keeps. A report saying "5 frames
analysed" without saying 23 were discarded invites the reader to assume the whole
video was examined.

### D-040 - The perceptual dedupe threshold is a guess, and says so
**P7.** The first value was 8 of 64 bits, chosen for no reason at all. On the
fixture it merged frames two seconds and half a car apart: genuinely different
views scored 7, while frames from a deliberate camera pause scored 0. A threshold
that cannot separate those is not doing its job.

Changed to 5, which is the conventional near-duplicate distance for an average
hash - a defensible default rather than a tuned one. Deliberately **not** tuned
against the fixture: a synthetic panning strip has far less texture than a car in
daylight, so its hash distances are compressed, and fitting to it would be
overfitting to a drawing. The constant carries a comment saying it is unvalidated
and the test asserts the property that matters (pause distance below the
threshold, sweep distance above it) rather than the number.

### D-041 - The paid report is gated by a signed grant
**P7.** `/report/demo-01` was a static route with no check on it for six phases.
The teaser projection was correct - the free payload genuinely never contained the
findings - but the paid page itself was open to anyone who guessed a URL, which is
a different hole and a worse one, and P4's own report listed it as gap 4.

Chose a stateless HMAC grant over the inspection id and the reason it was issued.
Stateless because there is no database yet and a signed token needs no lookup;
when persistence lands this becomes a row without the interface changing. The
reason travels *inside* the signature so a `demo` grant cannot be replayed as
`paid` by editing a prefix. Exactly one id is publicly readable and it is named as
a constant rather than inferred from a flag, so the free sample is greppable.

In production an unset signing key is a hard failure rather than a fallback. A
well-known development key is the same as no signing at all, and the failure mode
of getting that wrong is that every paid report is free forever.

### D-042 - The laws are now checked against the build
**P7.** LAW 7 has required "an e2e upload -> paid dossier test" since P0. No such
test existed. Six phases were tagged ALL GATES GREEN with a clause of one of the
seven laws simply unmet - not disputed, not deferred with a note, unnoticed.

The cause is structural and worth naming: `scripts/gates.sh` encodes the checks
that exist, not the checks the laws require, and `docs/LAWS.md` is prose that
nothing parses. Individual laws were enforced well. The *list* was never compared
against the repository.

`test_laws_are_kept.py` now reads LAWS.md, extracts every file it names, and fails
if one is missing; asserts the e2e test exists and actually walks the flow;
asserts each law is still present with its key clause; and asserts the gate script
still runs the suites the laws depend on. It cannot judge whether a test is any
good. It can catch a law pointing at nothing, which is the failure that happened.

Writing it immediately found two more: `pnpm run py:types` still lacked the
`--config-file` flag that made the gate non-strict for three phases, and
`inspect:fixture` did not emit the teaser, so `fixture:clean` could not see the
teaser going stale.

### D-043 - The share page and print footer exist because the liability doc said they did
**P7.** LIABILITY section 4 is a table of seven disclaimer placements. Two of them
- the share page and the PDF/print running footer - had been specified since P0
and never built. That is precisely the drift P6 found on the landing page, except
it was inside the document that describes our liability position.

Both now exist. The share page carries a fixed diagonal watermark behind the
content, because a shared link arrives with no context - forwarded to a seller, a
partner, or a forum - and a watermark survives a screenshot where a footer does
not. It is `noindex`, because a shared report should not end up in a search index
attached to somebody's car. The print stylesheet uses a fixed `body::after`, which
is what makes it a *running* footer rather than a footer, and hides the watermark
on paper where it would be ink across the evidence.

### D-044 - Exactly one finding crosses the paywall, and it is the best one
**P8.** The free page sold "every finding, with the photograph it came from and a
box drawn on it" and, for seven phases, rendered no photograph at all. A stranger
deciding whether to spend $25 on a visual evidence product could not see a single
piece of visual evidence first. That asks them to take the whole thing on faith,
which is the opposite of what this product claims to be for.

So `Teaser.sample` carries one finding in full - the picture, the box, the
confidence, and the sentence explaining why that confidence and not a higher one.
Not a blurred preview and not a cropped teaser of a teaser.

It is the *worst-severity, best-evidenced* finding about the vehicle, not the
mildest. Showing the least of what was found in order to hold the best back is a
sales tactic, and the coverage block directly above it already states how much of
the car this could speak for. Model-level records are excluded: a recall campaign
is true of every car of that model year, so advertising this report with one
would be advertising it with a fact about a car the buyer has never seen. Locked
systems are excluded twice over - `apply_safety_law` has already converted them to
referrals, and `_sample` skips them again, because the free page is the most-read
surface in the product and a brake claim arriving there would be the worst
available place for that clamp to have failed (LAW 2).

The field is deliberately singular and deliberately named. `parseTeaser` still
refuses any payload carrying `findings` or `assets`, unchanged and exactly as
strict; the guard it replaces is not loosened but cut to shape. `test_teaser.py`
deletes `sample` from the payload and holds everything remaining to the original
standard, then separately asserts that every finding except the sampled one is
absent from the whole free payload. A list here would be a paywall with a length
knob on it, and the knob would be turned by whoever next wants the free page to
convert better.

### D-045 - An asset records its pixel dimensions, because a box is a fraction of them
**P8.** Every `image_region` in a report is four numbers between 0 and 1. Nothing
recorded what they were fractions *of*. The report hashed the exact bytes a claim
was written against - so a golden test could prove the pixels had not changed -
while never recording their shape, which meant a reader could not redraw the box
or confirm it lands where the finding says it does. A citation you cannot check is
a citation in form only.

`Asset.width` and `Asset.height` are read from the image header on ingest.
Failure is not an error: a corrupt file or a format Pillow cannot open yields
`(None, None)`, and every consumer treats absent dimensions as "cannot crop to
this" rather than guessing. `cropFor` returns null and the viewer shows the whole
frame, because a crop that is approximately right is evidence that is
approximately honest.

### D-046 - The evidence is the picture; the coordinates stay as the citation
**P8.** `Overlay.tsx` has carried the comment "evidence and claim are never more
than one interaction apart (LAW 1)" since P2. On the rendered dossier the gallery
sat at roughly 1,300px and the findings began at roughly 5,000px, on a page
14,282px tall. What actually sat beside each claim was
`photo_01 [0.08, 0.62, 0.34, 0.14]`. A buyer reading "corrosion visible along the
driver-side rocker panel" could not see the corrosion without scrolling four
thousand pixels and then finding the right thumbnail among thirteen.

The comment described an intention and the layout did something else, and nothing
failed, because a claim about layout written in a docstring is not a test.

`crop.ts` computes the geometry in source pixels and returns percentages, so the
cited region renders at a readable size with no canvas, no client JavaScript and
no image processing - and lands exactly where the finding says it does. The
magnification is stated on the frame, because a crop is a claim about scale as
much as position and a 4x blow-up of a 60px region should not read as a clear
photograph of a large defect. The coordinates are still printed: they are what
makes the claim checkable against the hash. They are simply not the evidence any
more. `ReportView.test.tsx` now asserts the adjacency instead of trusting the
comment.

### D-047 - The coverage map lights from the photograph, not from the finding's system
**P8.** The signature visual is a plan view of the vehicle showing three states
per region - flagged, photographed-and-nothing-visible, and never photographed -
with the four locked systems drawn where they physically live. Every other
inspection interface draws a car to decorate a column of green ticks. This product
cannot produce one, and *where it looked* is the most honest thing it knows.

Two things about it are decisions rather than drawing. First, a zone flags only
when a finding's `image_region` evidence cites an asset whose `viewClass` is that
zone. Keying it off the finding's `system` - the obvious implementation, and the
first one - lit the front, the rear and both flanks for one corrosion finding on a
rocker panel, because all four are `system: "exterior"`. The component reported
damage on parts of the car nothing had been found on, which is the precise failure
it exists to prevent.

Second, the row of views with no place on the drawing is derived from
`coverage.requestedViews` rather than from a list kept in the component. The
hardcoded version was three entries long while the contract had fifteen view
classes and the pipeline requested twelve. It agreed with the pipeline on the day
it was written. A view added to `REQUESTED_VIEWS` later would have gone missing
from the one component whose entire purpose is showing what was not covered.

### D-048 - There is no brand hue
**P8.** An accent green existed from P0 to P7 and was used for links, active
states, the checkout button, and the `no_issues_visible` system status. The last
of those is the problem: it painted "nothing adverse was visible in the
photographs you sent" in the same colour every competitor uses for *pass*, which
is the one thing LAW 2 says this product may never say. A hue whose most natural
application is forbidden is a hue that will eventually be applied anyway.

So it was removed rather than restricted. The only chroma on the page is the
meaning ramp - four severities, plus locked and unknown, which sit off the ramp on
purpose. A primary action is `--tk-paper` on `--tk-void`: the highest contrast
available, earned by contrast rather than by colour. The base is warm rather than
blue-black, because against a cool ground the severity ramp reads as neon, and a
report about somebody's actual money should not look like a game.

Removing a token is a change to every file that used it, and three of the four
call sites were in files this phase never opened - including the checkout button,
which rendered as near-black text on a transparent background on the one page
where money changes hands. See D-049.

### D-049 - A second copy of a definition gets a parity test, not a comment
**P8.** This project has now found the same failure five times: a shape defined
twice, kept in step by attention, drifting the moment attention moved. The enums
(caught, P2), the laws (caught, P7), the landing page (caught, P6), and this
phase: the `assets` table silently had nowhere to put the new dimensions, the
stylesheet deleted a token four components still asked for, and every one of the
fourteen colour values in BRAND.md was wrong.

The rule from here: a duplicated definition ships with the test that compares the
copies, in the same change. Three exist now - `column-parity.test.ts` (contract
fields against Postgres columns), `tokens.test.ts` (every `var(--tk-*)` in the
source against `globals.css`, and the BRAND.md colour table against both), and the
existing `enum-parity.test.ts`. Each was written by first breaking the thing it
checks and confirming it went red.

A comment saying "mirrored in X" is not this. It is a note asking a future reader
to do the check by hand, and the evidence is that they do not.

### D-050 - One gate opens a browser, and it is not allowed to skip
**P8.** P8 found eight defects. Six were invisible to a suite of 444 tests and
visible within a minute of loading the built page: a pay button rendering
near-black on nothing, three layouts overflowing a phone viewport, a federal
recall title pushing its heading 40px past its panel, and prose set at 159
characters a line.

Every one of them got a static test in the same phase, and those tests are real -
a dangling `var(--tk-*)`, an uncapped measure, a prose class on a `<td>`. But
each is the shape of a bug that already happened. `renderToStaticMarkup` returns
a string, and a string has no width, no cascade and no computed colour, so the
existing suite could confirm that the right elements exist in the right order
while the result was unreadable.

`layout.test.ts` renders the real components, applies the real stylesheet, and
lays it out in chromium at 320, 390, 768 and 1440px. It asserts three things the
markup cannot express: nothing overflows the viewport; no paragraph exceeds 92
characters a line, counted as real text over real line boxes from
`Range.getClientRects()`; and every piece of text clears WCAG AA against the
first opaque background above it. That last check is the general form of the pay
button bug - black on a dropped background measures 1.06:1 and fails without
anyone having to anticipate that particular button.

**It builds the page rather than fetching it.** No `next build`, no listening
port. Neither is what is under test, and a gate that needs both is slow enough to
be skipped and flaky enough to be disabled. Media and fonts are served off disk
through a route handler so images carry their real intrinsic size and text is
laid out in the real faces; without that every `<img>` measures zero and the
overflow numbers are fiction. The whole suite runs in about four seconds.

**It fails rather than skips when chromium is absent.** The tempting design is a
graceful skip so CI never breaks on a missing binary. That produces a gate that
reports success because nothing ran, which is the precise failure this project
has now found six times in three phases. CI installs the browser explicitly and
the test throws with the install command if it cannot launch.

The checkout button gets there by a specific route. It only exists in the DOM
after three checkboxes are ticked and Stripe is configured, so no static render
reaches it; its styling moved from inline into `.btn-primary` so that the class
can be put on a page and measured. That also gave it a `min-height: 44px` target,
since of every control in this product the one a nervous buyer taps to spend $25
on a phone is the one that should not need aiming at.

Each of the three checks was verified by reintroducing the defect it was written
for and confirming it went red - the overflow check reproduced the original 76px
at 390px exactly.

### D-051 - The layout gate is fed reports designed to break it
**P8.** D-050 built a gate whose checks were general and whose input was not. It
ran against `demo-01`: eight findings, short titles, every optional section
populated - the one report guaranteed not to surprise the layout, because the
layout was built while looking at it. The phase report listed that as a known
limit, which is a way of writing a bug down instead of fixing it.

`stress.ts` derives six adversarial reports and two adversarial teasers from the
real fixture: forty findings, 900-character details, federal component strings
with no break opportunity in them, an empty-handed report with no findings at
all, assets whose dimensions could not be read, and seven-figure prices. Each is
passed back through `parseReport`, which runs the zod contract *and*
`assertLaws`, so a case cannot drift into something the pipeline could never
emit. That constraint is the difference between "the layout survives arbitrary
JSON", which is not a claim worth making, and "the layout survives every report
this pipeline can produce".

**It found a defect on the first run, and the defect was severe.** A report whose
titles are real NHTSA component strings ran **1,128px past a 320px viewport, and
579px past a 1440px one**. Not a small-screen problem - a content problem that a
wide screen was hiding. Nothing in the product chooses those words: they arrive
from a federal record, a buyer's paperwork, or a vision model.

The fix is one inherited declaration, and which one matters:

    body { overflow-wrap: anywhere; }

`break-word` was the obvious choice and was wrong. Both values break a long token
onto the next line, but only `anywhere` also shrinks the element's *min-content*
width - and a flex or grid item defaults to `min-width: auto`, so it refuses to
be narrower than its min-content. With `break-word` the vehicle heading wrapped
its text correctly while still forcing its flex row 366px past a 320px viewport.
The token broke; the box did not shrink.

By inspection those two values look interchangeable. Only laying the page out
against content nastier than the fixture told them apart, which is the argument
for this decision in a sentence.
