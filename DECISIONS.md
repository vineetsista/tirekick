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

### D-052 - Media is served through the same check as the page, and only what the report cites
**P9.** `/f/<id>/*` was a directory under `public/`: the report page verified a
grant while the photographs it renders did not. PHASE_8 named it - "whatever
replaces local disk has to serve media through the same check" - and this phase
is that. A route handler now serves every media byte, and the framework detail
that decided the design is that a file under `public/` is served *before* any
route handler runs: the demo's media had to leave `public/` entirely, or the
check would exist while never executing for the one inspection every stranger
loads. The sync script now deletes the copy it used to create.

Two judgement calls inside that, both restrictive on purpose:

**The allowlist is the report's own citations, not the media directory.** The
directory can hold things no report mentions - `redactions.json` sidecars naming
the reviewer and boxing every face, raw frames left by a crashed extraction, an
upload the pipeline rejected. "Serve what is on disk under this id" publishes
all of it; "serve what the report cites" publishes exactly the evidence the
buyer was shown citations for, which is the boundary LAW 1 already draws. The
spectrogram rides along explicitly (it is cited by `audio.spectrogramPath`, not
by an asset row). Cost: a file the pipeline writes but forgets to cite becomes
invisible to the viewer - which is the correct failure, since an uncited file
is not evidence.

**Denial is a 404, not a 403.** The route answers "no such thing" whether the
inspection is absent, the file uncited, or the grant missing, so a prober
cannot map which inspection ids exist. Cost: a buyer whose cookie expired sees
a missing image rather than an explanation; the report page above it carries
the recovery path.

### D-053 - Grants have tiers, the grant travels in a cookie, and `owner` opens the teaser only
**P9.** The media route forced a question P7's grant design never had to answer:
the free teaser page renders one photograph (D-044), so *some* media must open
without payment - but an upload is somebody's prospective car, and nothing about
it should be public. "Free" is a statement about money, not about who may look.

So the tiers: `paid` and `demo` open the report and every photograph it cites;
`owner` - issued to the uploader the moment their inspection is created - opens
the teaser and exactly one photograph, the sample finding's. A stranger with the
URL and no grant gets nothing at all, teaser included. Cost: the owner cannot
see their own photographs through the product without paying, only the sample.
They possess the originals; what they have not bought is the analysis.

The grant moved from a function parameter into an httpOnly cookie, set by one
route (`/access/<id>?t=...`) that verifies the token and redirects. An `<img>`
tag can carry no header we control, and a token in the URL leaks through
referrers, history sync and screenshots; after the exchange the token never
appears in a URL again. The redirect target is confined to same-site paths, or
the exchange route would be an open redirect wearing our domain. Cookie life is
90 days - the media retention window UNIT_ECONOMICS already assumes, so the
cookie never promises access to bytes that are gone.

### D-054 - The upload page ships as the honest dev implementation, not a mock of production
**P9.** LAW 7's end-to-end flow has driven upload -> analyse -> grant -> dossier
through library calls since P7, and no page let a person do the same. The flow
now has a form (`/new`): the same `createInspection` and `analyse` the test
drives, an `owner` grant in a cookie, and a redirect to the teaser.

What it does not do is pretend. Analysis is the local Python subprocess
`inspections.ts` has always declared itself to be, in fixture mode, with no
vision key - and the page says so in its copy: photographs are catalogued, not
examined; the result states what nothing looked at. On a deploy with no Python
runtime the action fails with the true reason rather than a soothing one. Cost:
the page is a dead end on Vercel until the worker host exists - which is the
same dead end the whole pipeline has, now visible in a form instead of hidden
in a test file.

Uploaded filenames are sanitised to the character set every pipeline-emitted
asset already uses (basename only, no leading dots, collisions suffixed), so an
upload named `../../report.json` becomes a file *inside* media/ rather than a
write outside it - checked by the same validator the media route applies on the
way back out.

### D-055 - The layout gate fails loudly when it cannot serve a file
**P9.** Moving demo media out of `public/` touched the one consumer nobody
advertises: the D-050 browser gate, which serves `/f/**` off disk so images have
real intrinsic dimensions. Its miss path was `route.abort()` - an image that
failed to load measured zero, and every overflow number on that page became
fiction while the suite stayed green. That is the exact failure D-050 exists to
forbid, one layer down, in the gate's own plumbing.

The interceptor now records every path it could not serve and the suite throws
after the run, naming them. Verified by pointing it at a directory that does not
exist and watching all the image-bearing pages fail at once. Cost: a genuinely
new asset in a stress case must exist under `fixtures/demo-01/media` or the gate
refuses to run quietly without it - which is the point.

### D-056 - LAW 4's switch is enforced on a measured failure, and disclosed on an unmeasured one
**P9.** LAWS.md says "below threshold means disabled in paid output" and names
`registry.py::enabled_for_paid` as the enforcement point. An audit of the report
path found the flag is read by the gate table and by the accuracy statement - by
the things that *describe* the gate - and by nothing that enforces it. The switch
governed a console printout.

Enforcing it literally would empty every report this product can currently
produce, because nothing has been measured at all. That is not what the project
decided: D-032 settled the unmeasured state with disclosure, generating the
sentence above the payment button from the same registry. So the two states are
now treated as the different things they are. **Measured and failing** is
enforced: the drafts are dropped before the safety clamp, and each withheld type
is named in the could-not-assess block with its precision, its sample size and
its threshold, so the gap is visible rather than silent. **Not measured** ships
under D-032's disclosure.

Cost: the law's headline sentence is broader than the code, and this decision
narrows the code's obligation rather than the law's words. The honest resolution
is to amend LAW 4 to say what the product does - which requires a commit that
edits LAWS.md and nothing else - and that commit is not in this phase. Until it
lands, the gap is named here rather than left for the next audit to find again.

### D-057 - The negotiation script stops attributing its own estimate to a shop
**P9.** The script told the buyer to say, to a seller's face: *"a shop quoted
that kind of work at roughly $600 to $900."* No shop was called. D-024 already
holds that cost bands have no real source, `fixtures/PROVENANCE.md` declares the
fixture's bands invented, and the same function's docstring promises "a script
that never asks the buyer to overstate what we found". It scripted a fabricated
provenance for the buyer to assert as fact.

The band is now described as what it is - the analysis's own rough estimate, not
a quote - and the sentence asks the seller to let a shop price it properly. Cost:
a weaker negotiating line, because "the analysis estimated" carries less weight
in a driveway than "a shop quoted", and that is precisely why the second version
was tempting.

Two related fixes shipped with it. `vision.py` accepted `estimated_cost_usd`
straight out of a model response despite the comment above the line saying it
never does: D-024's stated mechanism - "a field that is not in the schema cannot
be returned" - is false, because JSON Schema permits extra properties unless
told otherwise. A volunteered band now dies at the boundary in live mode, while
fixture responses keep theirs. And the headline stopped counting recalls from
the surviving findings: a campaign against a locked system becomes a mechanic
referral before the count runs, so a car whose only campaign was an airbag recall
- the most common category in the fleet - reported "Nothing adverse was visible
in the media provided."

### D-058 - The systems table is about this car; the recall section is about the model year
**P9.** D-021 kept model-level records out of the red-flag score and said why:
scoring five campaigns like observed damage reads as "this car is a wreck" and is
not what the evidence says. The systems table was never given the same rule. A
recall carries confidence 1.0 - confidence that the campaign *exists* - so the
shipped fixture rendered the transmission row as attention at 1.0 on a car
nothing had observed a transmission fault on, and the teaser turned that into
"Something was found here." The engine row led with a recall title over the fluid
leak actually visible in the photograph.

Only vehicle-level findings set a system's status now, and the teaser's severity
counts follow the same rule - they read "7 major" beside a headline saying two
and a score that excluded five of them. Cost: a system whose only record is a
recall now reads `cannot_determine`, which is a weaker-looking row, and it is the
true one: nothing was observed about that system on this car.

### D-059 - What the teaser sells is derived from what the report contains
**P9.** The six unlock bullets were a fixed list. A buyer who uploaded eight
photographs and nothing else was sold "the engine audio spectrogram", "the full
vehicle record" and "what your own paperwork says", paid $25, and opened a report
where none of those sections render - while the price comparison, a real paid
section, was advertised nowhere. The teaser computed `has_audio` and
`has_price_check` and used neither.

The list is now built from the report: a bullet exists when the section behind it
does. The sample statement stopped claiming "each with its own photograph and
box" for findings cited to a document rather than an image. Cost: the free page
sells less to buyers who provided less - which is the correct amount, and is the
difference between a teaser and a bait.

### D-060 - Prices, ranges and boxes are validated as the shapes they claim to be
**P9.** Four coordinates each legal in [0,1] can still describe a box that runs
off the edge of the photograph, and a range whose low exceeds its high is not a
range. Both were representable, and a report carrying either is one a reader
cannot check: a box nobody can redraw is not evidence, and a fair range with an
inverted floor makes every verdict computed against it meaningless.

`BoundingBox` now rejects x+w or y+h past 1 (with a rounding-error tolerance, since
the fractions are serialised at four decimals), and `CostBand`, `PriceRange` and
`PriceDeduction` reject inverted pairs. Cost: an engine that produces a
slightly-out-of-frame box now fails loudly at construction instead of shipping a
box the viewer clips - which is the trade LAW 1 already makes everywhere else.

### D-061 - The accuracy gate table is written by a script, not typed
**P10.** `docs/ACCURACY.md` has said since P0: "This page is generated from
`bench/results/latest.json`. There is no second place to type a precision figure,
so a number here that is not in that file cannot happen." Nothing generated the
page. The table was typed in P0 and hand-edited afterwards, which is exactly the
second place the sentence promises does not exist - and by P9 it had drifted in
all three ways a hand-maintained table drifts: fifteen rows for sixteen registered
types (so `documentation_gap` shipped with no published gate at all), Status values
reading "awaiting P2" four phases after P2, and nothing anywhere able to tell you
either was true.

The third is the serious one. A precision figure typed into a document is a
marketing claim wearing a measurement's clothes, and this project's whole argument
is that those are different things. `scripts/sync_accuracy_table.py` now writes the
table from `registry.FINDING_TYPES`, which already reads the bench results, and
`--check` runs in the test suite so editing the table by hand fails the build with
the diff printed. Cost: the table's wording is no longer editable in place - a
column you want to read differently is a change to the script. That is the point.

### D-062 - The accuracy page is rendered by a parser that refuses, not one that copes
**P10.** `/accuracy` is the page LAW 6 obliges the product to link, and for nine
phases it rendered the markdown source inside a `<pre>`. A buyer who followed the
accuracy link - the one above the payment button - was shown `## Finding types and
their gates`, `**bold**` with the asterisks in, and a sixteen-row gate table as
pipe-delimited text. The most important page in the product was the least readable
thing in it.

The obvious fix is a markdown library, and the reason not to take it is the failure
mode rather than the dependency. A general renderer's contract is "render what you
understand, pass through what you do not" - which, on this document, means a
mistyped pipe shows fifteen rows and a stray line of text, and the missing gate is
invisible. So `apps/web/src/lib/markdown.ts` inverts the contract: it understands
the constructs this one document uses, throws on everything else including
malformed versions of what it supports, and parses at module scope so a document it
cannot read fails `next build` instead of reaching a buyer half-rendered. It
returns an AST that the page renders through JSX, so nothing on the path produces
markup and there is no escaping question to get wrong. Cost: this parser is
correct for exactly one file. Pointing it at arbitrary markdown would be a bug, and
the docstring says so.

### D-063 - The README's numbers and its quotation of the product are generated
**P10.** The front page opened with a table of nine numbers and quoted the
product's own output back at the reader. Every one of those was typed. The test
count said 612 when the suites collected a different number, and the
could-not-assess block - presented in a code fence as what the product prints - was
a paraphrase: the report says "Airbags and restraints" and "Frame and structural
integrity", the README said "Restraints" and "Structure", tidied into aligned
columns that no code path produces.

Nothing malicious and nothing load-bearing, which is what makes it worth writing
down: that is what drift looks like before it matters. A repository whose argument
is "we do not claim what we have not measured" was pretty-printing the product's
words on its front page. `scripts/check_readme.py` now writes both blocks from the
repository - phase reports, DECISIONS.md, docs/LAWS.md, gates.sh, the registry, the
collected test suites, and the committed fixture report - and checks that every
path the README names resolves. It runs as a gate. Cost: about thirty seconds per
gate run, because counting tests honestly means collecting both suites rather than
grepping for `def test_`, and 25 of the Python tests are parameterised so a static
count is wrong the moment anyone looks.

### D-064 - The SDK contract is checked outside pytest, by a job that installs it
**P10.** `client._retryable_errors` reads two attributes off `anthropic` and
returns `()` when the import fails. `()` is a legal `except` clause that catches
nothing, so a rename on the SDK's side does not raise - it silently turns the retry
loop into a single attempt, and the symptom is a paid run dying on the first 429 a
retry would have absorbed. The test written to prevent this was named
`..._the_sdk_actually_defines` and asserted against a stub built three lines above
it; a fake `anthropic` exporting neither name left it green.

The one-line fix inside pytest is `importorskip`, and that is the line that removed
the retry tests from CI for a phase while still reporting a pass - which
`test_no_test_in_this_package_is_conditional_on_the_live_extra` now forbids, for
good reason: the suite must pass with no SDK installed, because running without one
is the product's documented default (D-009). So the real-package assertion lives in
`scripts/check_sdk_contract.py`, run by a CI job that installs the `live` extra on
purpose, and it fails rather than skips when the SDK is absent. A test in
`test_live_vision.py` asserts the script and the job both still exist, so deleting
either goes red rather than leaving a docstring describing a check that is gone.
Cost: one more CI job, and a job that can break on somebody else's release. That is
the alarm working - the gates job stays green, the product still runs without a
key, and the thing that is actually broken is the thing that goes red.

### D-065 - A fix ships with the mutation that proves its test can fail
**P10.** Seven crews fixed seven verified defects. All nine gates were green, 776
tests passed, and an adversarial pass found every one of the seven defective -
including a regression that turned a clean car's history report into five major
findings at full confidence, each quoting its own denial as the evidence.

Nine gates did not see it. What saw it was deleting each new mechanism and asking
whether anything went red. So that is now the bar: a change that adds a mechanism
also reports the mutation that breaks it and the test that caught the break. This
is not a new law, it is how the existing rule about watching a test go red gets
applied to work that is already written - and it catches the case the original rule
misses, which is a mechanism whose test passes for a reason unrelated to it.

It has already earned itself twice inside this phase. The replacement history
classifier survived its first mutation run with one guard unpinned, and the fixture
provenance test's format-refusal branch passed for a reason unrelated to the code
it was presented as guarding. Cost: roughly a third again as much work per fix,
paid in the phase where seven of seven fixes needed it.

### D-066 - A cell separator is not a statement boundary
**P10.** A denial has a scope and it is not the whole line, so `_CLAUSE_BREAK`
splits a document line into statements before deciding whether a brand is being
reported or denied. A pipe was added to that pattern on the reasoning that a table
row holds two statements. It does - and nothing distinguishes a cell separator from
a sentence boundary except what the cells say. Every clean row of every markdown
history report - `| Salvage | None reported |` - split into a bare label and an
answer about nothing, and shipped as a major at confidence 1.0 with its own denial
quoted underneath as the evidence.

It bought one contrived row full strength and cost a whole layout a false alarm.
D-017 says which direction to be wrong in and it is not that one. The pipe is out,
and the row that motivated it (`SALVAGE TITLE ISSUED | Prior owner: N/A`) now ships
hedged rather than at full strength - a downgrade of degree on one line, in
exchange for not printing a salvage warning on every clean car whose report is a
table.

What replaces it is narrower and says what it means: `.` and `;` remain boundaries,
but a following clause that contains nothing except answer words - "none reported",
"not reported" - belongs to the label in front of it, while one with a subject of
its own - "no accidents reported" - is a statement about accidents and denies the
brand beside it nothing. Cost: an answer vocabulary that has to be maintained, and
one guard (a clause that has already asserted the brand does not absorb the answer
after it) that exists to stop the absorption deleting a finding. Every separator is
now exercised in both directions, because a separator tested only where it upgrades
is a separator nobody weighed.

### D-067 - The redaction check reads the bytes, and our own media is subject to it
**P10.** `redact check` read the sign-off sheet: it asked whether every image had a
review record and never opened a file. Stripping metadata happened only inside
`apply`, a separate, destructive, skippable step - so a reviewer could honestly
sign every interior and odometer shot "nothing to redact", run check, get exit 0,
and commit photographs still carrying the seller's GPS.

check now asks both questions, and asserts the absence of metadata CONTAINERS -
EXIF, XMP, IPTC, JPEG COM, PNG text chunks, and trailing data after the JPEG EOI
marker, which is where a Samsung Motion Photo hides an entire MP4 - rather than
hunting for coordinates. Pillow parses some container formats and silently returns
nothing for others, so a coordinate-hunting check reads an empty dict off a
geotagged file and passes it. "No containers" is what the re-encode actually
establishes, so that is what the check asserts. A format the tool cannot strip
(`.heic`, `.webp`, raw) is refused rather than skipped, because a file the walk
never listed is a file the gate reported clean.

Then the repository submitted to its own rule, which it had never done: the gate
runs over `fixtures/demo-01/media` in `scripts/gates.sh`, and it immediately found
that five committed video frames carried ffmpeg's encoder banner in a COM segment
while README.md told the world the committed images carry no metadata. Harmless
content; a free-form text container all the same. `refresh_video_cache.py` now
strips on the way out and raises if anything survives. Cost: the frames are
re-encoded after selection, so they are not byte-identical to what ffmpeg wrote -
and the golden report's asset hashes changed with them. What the check still does
not cover, and says so in its own output rather than reporting a clean directory:
`.mp4` and `.wav`, and an `.mp4` can carry GPS in its `(c)xyz` atom.

### D-068 - One price, one source, and the charged price is named as being elsewhere
**P10.** The price existed three times: `checkout.ts` for the landing page,
`cli.py` for the teaser, and a comment claiming the first of those "is what
actually charges it". It charges nothing - `paymentLink()` appends a
`client_reference_id` to a Stripe payment link and never sends an amount, so
changing the constant to 30 turns every gate green while the buyer is billed
whatever Stripe holds. Meanwhile the landing page printed the TypeScript constant
and the very next page printed the Python one, from two unlinked literals with
nothing comparing them.

`PRICE_USD` now lives in `packages/shared/src/constants.ts` beside the other
cross-language constants, the Python side is held to it by the same parity test
that holds `REPORT_BANNER`, and a second literal fails a gate. The Stripe amount
genuinely cannot be asserted from inside this repository, so the code says that
instead of implying otherwise. Cost: a real gap that a test cannot close, written
down in `checkout.ts` and in the Known Gaps section rather than papered over with a
comment that reads like a guarantee.

### D-069 - A provenance record is compared against `git ls-files`, or it is a souvenir
**P10.** `fixtures/PROVENANCE.md` ran from P3 to P9 with no row for the rendered
spectrogram, and from P7 to P9 with no rows for the walkaround video or its five
extracted frames. Seven files covered by the front page's "all media is synthetic"
claim had no provenance row at all. Each gap opened in the commit that added the
artifact and closed in none of the phase gates after it, because no gate read the
file - and both provenance documents said exactly that about themselves, in
writing, for phases.

`test_provenance.py` now reads both, in three directions: a committed file with no
row, a row naming a file that is not there, and the file counts the documents state
about whole directories. It deliberately does not check whether a row is TRUE -
nothing opens `audio_01.wav` to confirm it was synthesised the way the row says -
and the docstring says so, because the P10 audit found a frames row whose four
counts were each correct and whose sentence around them did not add up. The file
list comes from `git ls-files` rather than the working tree, so an uncommitted
scratch file is not yet a provenance obligation. Cost: the documents now have a
house style the parser depends on, which is written down in each of them rather
than left to be inferred - a test that silently requires a convention is a test
that gets edited around.

### D-070 - LAW 2 is enforced on the sub-schemas, where Pydantic enforces it
**P10.** `assertLaws` checked strictly less than `models.py` did, and the gap was
LAW 2 itself: `findingSchema.parse` accepted a finding attached to brakes,
`systemRowSchema.parse` accepted a locked row cleared with a confidence, and
`teaserSystemRowSchema.parse` accepted the same on the free page - all three of
which the Pydantic models refuse on construction. No runtime exposure, because
`parseReport` and `parseTeaser` were the only entry points and both were correct.
But "the only entry point today" is not a property of a schema, it is a property of
the current call sites, and the law the whole product rests on should not depend on
one.

The invariants moved onto the sub-schemas. Cost: a zod schema carrying a refinement
becomes a `ZodEffects` and loses `.shape`, so it cannot be a `discriminatedUnion`
member - the schemas that need to stay unrefined for that reason are named with the
constraint written beside them rather than silently left out.

### D-071 - The redaction check walks the container and the coded stream, in pure Python
**P11.** `check` read still images and said so: it listed every `.mp4` and `.wav`
as "not examined" and returned zero. That is a declared gap rather than a hidden
one, which is the better of two bad answers and is still an answer that lets a
file ship unread - and what it let ship, in this repository's own fixtures, was a
clip carrying an encoder banner in a `(c)too` atom, a second copy of it in the
32-byte `compressorname` of the sample entry, and x264's whole command line in a
user-data SEI down inside `mdat`, where no container reader looks at all. A real
walkaround video carries the position it was shot in beside them.

Three choices worth recording. **Pure Python, not ffprobe:** a check that can
answer "skipped, the tool is not installed" has already passed on the one machine
where it mattered, and ffprobe answers with a normalised tag dict, so a container
it does not model reads as `{}` and passes - the Pillow-getxmp failure one format
up. **A real sample-table walk, not a substring search:** `avcC` for the NAL
length prefix, `stsz` for the sizes, `stsc`/`stco` for where samples sit, then
length-prefixed NAL units, flagging type 6 whose first payload type is 5. Grepping
`mdat` for a byte pair fires on compressed data by coincidence, and a check that
cries wolf is a check people learn to skip. **Nothing is ever removed:**
`stco`/`co64` hold absolute file offsets, so cutting a box out shifts everything
after it and silently repoints every chunk pointer into the middle of a frame - a
file that still opens, still reports the right duration, and decodes garbage. A
`udta` is retyped to `free` and zeroed at its original size instead.

One field is read by value rather than as a container: `creation_time` and
`modification_time` in `mvhd`/`tkhd`/`mdhd`, which say when the car was filmed.
The usual argument for containers (D-067) is that a reader cannot see reliably
inside every one of them, and that does not apply to a fixed-width field at a
known offset in a box the walker has already length-checked.

Cost, and it is the honest one: this is the third phase in a row where the
repository's own committed media failed the gate it had just been given. Also, the
in-place timestamp scrub was decorative when written - ffmpeg's `+bitexact` had
already zeroed those fields, so deleting the mechanism reddened nothing. It is now
tested where it can fail, with no remux in front of it.

### D-072 - Nothing in the media directory is invisible
**P11.** Every walk in the redaction tool was an allowlist of suffixes, so the
default for anything outside all of them was to be skipped: not listed, not
reviewed, not stripped, and not mentioned by the success line. The directory this
repository commits contains `history_01.txt`, a title history, and `check` printed
"14 still image(s) ... no metadata container" over it for four phases without ever
naming it. A real buyer's version of that file is a scan of a title certificate
with their address on it.

The default is inverted. A file no category claims is refused by name - the same
answer `.heic` already got, except that `.heic` had to be predicted in advance and
this does not. Documents are a category of their own: nothing strips a `.txt`,
because the content is the whole file and there is no container to strip, so what
they get is the other half of D-022 - a person confirming the file is safe to
commit. `redactions.json` is exempted by exact filename rather than by suffix,
because a buyer can upload a `.json` and an exempt suffix is a hole shaped like a
file extension.

Cost: the fixture directory needed a new signed-off record, and `init` had to
learn to scaffold one for a document, or the tool refused a file it gave no way to
clear.

### D-073 - A rate with a zero denominator is null, and a harness with nothing to score refuses
**P11.** `docs/EVAL.md` promised F1, precision at high confidence, a severity
confusion matrix and a calibration plot from P0 and `bench.py` computed none of
them. Building them introduced the opposite risk immediately, because all four are
ratios and the eval set is empty: three of the four fail toward *flattery* if
written the obvious way. Precision at 0.8 over an empty subset guarded as 1.0 says
"we were right about all zero of them". A severity agreement rate as
`exact / max(n, 1)` is perfect agreement from nothing. And an expected calibration
error accumulated from 0.0 and never divided reports **0.0, which reads as
perfectly calibrated** - the worst thing this change could ship and the easiest to
write by accident.

So: every rate whose denominator is zero is `null`, never `0.0` and never `1.0`,
and every rate ships beside the integer count it came from. Above that,
`bench/results/latest.json` carries `"scored": false` and a refusal sentence, and
`render()` prints that refusal *instead of* the table, because a table of dashes
is still a table and a screenshot of one is a claim.

Two things deliberately did not change. The gate still reads overall precision at
IoU 0.4 and the unfiltered `n`: precision at 0.8 is `>=` overall precision by
construction for any model whose confidence carries signal, so gating on it would
let a type ship on the strength of the subset the report already privileges while
the findings below the threshold - which it also prints - went entirely ungated.
And `docs/ACCURACY.md`'s table still publishes precision and not F1, because a
buyer reading an F1 column beside a "Precision gate" column reads F1 as the gated
number. Both are pinned by tests rather than by this paragraph.

The severity vocabulary is `models.Severity` - info, minor, major, critical - read
with `get_args` rather than retyped. EVAL.md promised {cosmetic, moderate,
significant}, a third vocabulary matching nothing in the code; a translation table
between two of them would have hidden exactly the over-call the matrix exists to
measure. Cost: `bench/results/latest.json` is now regenerated and diffed by a
gate, so the file the eval gate reads can no longer drift silently - which it had,
through the entire addition of four metrics, with all eleven gates green.

### D-074 - A promise this repository cannot read is refused, not skipped
**P11.** `unkept_promises` checked that a `path::symbol` promise in `docs/LAWS.md`
named a symbol the file defines, and its loop opened
`if target.suffix != ".py" or not target.is_file(): continue` - two conditions
with opposite meanings sharing one `continue`, inside the function written to
catch a law pointing at nothing. `apps/web/src/lib/access.ts::verifyGrant` would
have had its file checked and its symbol dropped in silence. It had never given a
wrong answer only because both `::` promises in LAWS.md happened to be Python.

The mechanism is the refusal, not the reader. A dispatch table maps extension to
reader (`.py` by `ast`, `.ts`/`.tsx` by a declaration scan, `.sh` by the gate-name
reader that already existed), and an extension with no reader raises. `.md` and
`.json` are refused on purpose and the reasons are written beside the table: a
`.md::x` could mean a heading, an anchor or a phrase, and a JSON key is a path
that a flat set of names cannot express.

Cost: the TypeScript reader is a scan rather than a parse, because a Python test
must not acquire a TypeScript toolchain. Every failure mode of it except one is
red-not-green - a declaration form it cannot see makes the law report unkept,
which is a spurious failure and never a spurious pass. The exception, a re-export
naming a symbol defined elsewhere, is handled explicitly and tested.

### D-075 - The wordmark has one definition
**P11.** `docs/BRAND.md` specified the wordmark as "800 weight, 0.22em tracking",
recorded that two sites disagreed, and explained why it was writing the drift down
rather than correcting it: "a wordmark defined in two places will drift again the
moment a third appears." That was right and it undercounted. Four more appeared:
by P11 the mark was set at six sites, in three tracking values, at two weights.

D-049 says a duplicated definition ships with the test that compares the copies.
The better answer available here was to delete the copies, so there is one
`Wordmark` component and two tests guard it - one that nothing else may render the
word, one that the two figures BRAND.md publishes are the two the component uses.
Size stays a prop because the document does not specify one; weight and tracking
are not props, because a prop is a place for them to drift from it again.

The render test earned itself immediately: it found a sixth site the grep behind
this entry had missed, because `new/page.tsx` set the two properties on a `<Link>`
rather than on a `<span>` inside it. The count in the first draft of the component's
own docstring was wrong in the commit that removed the duplication.

### D-076 - An inspection directory is claimed, not assumed
**P11.** The id was `insp_${randomUUID().slice(0, 8)}` - 32 bits - handed to
`mkdir(..., { recursive: true })`, which returns quietly when the directory is
already there. So a collision did not fail, it MERGED: the second upload's media
landed beside the first's, the second manifest overwrote the first, and because a
grant is an HMAC over the inspection id, whoever held either grant held both. The
failure is not a lost upload, it is one stranger reading another stranger's
photographs, and the birthday bound puts even odds on it at about 77,000
inspections.

The id is now a whole UUID's worth of randomness, and `recursive: false` makes the
filesystem answer the question instead of us. The second change is the one that
matters: "negligible" is a probability argument and `EEXIST` is a fact, and a
probability argument is what the old code was already relying on. `ENOENT` is
handled separately from `EEXIST`, so a missing workspace is not retried five times
into an error that hides what actually went wrong.

Cost: the test has to stub `randomUUID` to repeat itself, because a test that
merely asserted "two ids differ" would have passed against the broken code every
time it ran.

### D-077 - The last typed number in the generated table becomes a derived one
**P11.** `README.md` said "Every number in that table is read out of the
repository" two paragraphs above a table whose live-model-call row was the string
`**0**`, typed into `render_standing` directly. Nine of the ten rows were derived.
The tenth was the one making the strongest claim.

"Live model calls ever made" is not derivable - nothing in a repository can know
what its author once ran on a laptop. What is derivable is what a live call leaves
behind: `ModelClient.call` writes its response into `cached/`, and those files are
committed so a fixture run needs no key. So the row counts cache entries that do
not declare themselves something else, and it is *named for what it counts* rather
than for what it implies. Every entry declares itself today - the hand-written
vision responses carry `_fixture_note`, the two computed caches name the script
that measured them - so a real response cached and committed arrives with neither
and is counted immediately, and so is an artifact dropped in with no provenance at
all.

The gates row lost its ", green local and CI" for the same reason: this script
counts the gates, it does not run them, and it was publishing a claim about their
result inside the block whose whole argument is that its contents are derived.
Whether the gates are green is what the CI badge is for, because a badge is a link
to a run and a sentence is not.

### D-078 - A denial is scoped to the brand standing next to it
**P11.** `_classify` returned "denied" the instant `_NEGATED_ASSERTION` matched
anywhere in the selected statement, with no check that the negation's subject was
the brand. `_CLAUSE_BREAK` splits on `.` and `;` only - a comma, a dash and a
table pipe are deliberately not boundaries (D-066) - so a denial about accidents,
liens or recalls swallowed an asserted salvage, flood, rebuilt or total-loss brand
sitting on the same line:

    SALVAGE TITLE ISSUED 03/2019, no accidents reported     -> denied. No finding.
    Flood damage reported 06/2018, none disclosed by seller  -> denied. No finding.
    | SALVAGE TITLE ISSUED 03/2019 | no accidents reported | -> denied. No finding.

A vehicle whose own paperwork declares a salvage brand produced no title-brand
finding at all. That is the inverse of P10's regression and it is worse: a false
major is something the buyer can check, because LAW 1 puts the quoted line beside
the claim. A silent drop gives them nothing to check.

The fix uses the shape the file already had for words that only look like denials:
blank the negated assertion as a *unit*, the way `_ENUMERATION` and
`_NAMED_WITH_A_NEGATION` are blanked, then read what remains. Something in the
remainder still asserting means both signals are present and the answer is
ambiguous; a remainder that only denies further is denying, whatever else it
mentions - hedging that would be P10's false-major regression in a new costume.
All three lines now ship hedged with the whole line quoted, and every clean-title
shape stays denied.

Two more defects in the same engine went with it. `scan` broke out of the pattern
loop on the first match, and the patterns are ordered by seriousness rather than
by position, so a correctly *denied* serious brand hid an asserted lesser one:
`Salvage: none reported. Flood damage reported 03/2019.` produced nothing, while
the same content on two lines produced the flood finding. The break is now
conditional on the stance having produced something a buyer will see. And
`_excerpt` truncated 240 characters from the start of the line while the keyword
could sit anywhere in it, so a wide record row published a major salvage
allegation cited to text that mentions no salvage - under copy reading "The line
is quoted below exactly as it appears." The window is centred on the match now,
and a shortened excerpt says it was shortened.

Cost, recorded because it is a real limit: `_NEGATED_ASSERTION` blanks up to
twenty characters past the negation, so "Salvage brand: none, title issued 2019"
has the assertion verb swallowed inside the blanked span and comes out denied. It
is not a regression - HEAD returned denied there too, for a cruder reason - and
widening the pattern to chase it is how this engine broke the last two times.

### D-079 - A grant expires, and can be revoked for one inspection without rotating the key
**P11.** `issueGrant` signed `${inspectionId}.${reason}` and nothing else. The
only time bound in the system was the *cookie's* max-age, which is client-side
advice, so the token was a permanent bearer credential and `/access/<id>?t=<token>`
re-minted the cookie on demand. Beside it, `GRANT_COOKIE_MAX_AGE_SECONDS`
described ninety days as "how long a grant lives" and `LIABILITY.md` section 6
promised a revocable grant. Both described properties the code did not have.

The issued-at is now inside the signed payload - beside the signature is where the
holder edits it - and `verifyGrant` rejects a stamp older than the retention
window and one more than five minutes in the future, because a signed future stamp
is our own broken clock minting an immortal token. Every unclear reading denies: a
non-digit timestamp, an empty field, the wrong number of parts. `Number("")` is 0
and `parseInt("12abc")` is 12, so the digit pattern is what stops us inventing a
timestamp on the holder's behalf.

Revocation is a per-inspection epoch mixed into the payload, so one inspection can
be closed without rotating the secret and signing out everybody. An absent epoch
file reads as zero - failing closed there would invalidate every grant already in
a browser at deploy time - and a file that exists but does not parse denies, which
is D-017 applied to somebody's photographs: a buyer can be re-issued a link, a
seller cannot un-leak a driveway.

The demo exemption is the intersection of `reason === "demo"` and the public demo
id, and nothing wider. Its media is the checked-in fixture rather than retained
bytes, so an expiring demo grant would take the public sample dark ninety days
after a deploy with nobody noticing until a customer did. It is not exempt from
revocation or from the future-stamp check.

The clock is a parameter with a default, not a stubbed global: stubbing `Date`
proves the module agrees with the stub, while an injected instant leaves
production reading the real clock.

Cost, and it is still open: `bumpRevocationEpoch` is exported and tested and
nothing calls it. The property exists in code and a buyer still cannot exercise
it, which is the same defect class in a smaller box. The epoch file also lives in
the local workspace, so it inherits every limitation `inspections.ts` already
declares about local disk.

### D-080 - The clamp decides by provenance, not by reading prose
**P11.** `_is_adverse` decided whether a locked-system draft warned or cleared
from `draft.severity` alone, and its docstring said "anything reassuring is
dropped outright - that is the entire point of the law." The only reassurance it
could detect was `severity == "info"`. Any draft tagged minor, major or critical
became a `MechanicReferral` whose `observation` was the model's sentence copied
verbatim, printed under a heading that says a mechanic is required. A plausible
`minor` draft - "the pads appear to have plenty of life left; nothing here
suggests the braking system needs work" - was a remote all-clear on brakes, which
is the one outcome LAW 2 exists to make impossible. The clamp enforced "we can
raise an alarm" and not "we cannot sound an all-clear".

Reading the sentence and judging whether it reassures was the tempting fix and is
the wrong one: it bolts a second probabilistic filter onto a control that is
deterministic on purpose (D-004), and it fails the way the model does - silently,
on the case nobody wrote a phrase for. `copy_rules.BANNED` holds nine exact
phrasings and knows nothing about pads, rotors or life left.

So the clamp decides by *provenance*. `SELF_AUTHORED_ENGINES` is a default-deny
allowlist of engines whose sentences a person in this repository wrote. A referral
built from any other engine's draft carries none of that draft's text: the
observation is composed from the locked-system label, the engine name and the
evidence locators. Evidence captions are replaced too, because a caption renders
under the box in the report gallery and can clear a brake system exactly as well
as an observation can. Boxes, asset ids and document excerpts are untouched - the
citation ships, the sentence does not, and the withheld sentence still reaches the
operator through `clamp_log` on stdout.

The allowlist is itself a claim, so a test checks it mechanically against
`prompts/<engine>/`: an engine that loads a prompt talks to a model, and prompts
live one directory per engine. Cost: the buyer loses a sentence and keeps
everything the sentence was about, and the golden fixture changed in exactly two
lines - one observation and one caption - which is the fix visible in the product.

### D-081 - An extrapolated price is a refusal, not a $0 range
**P11.** `_normalized_prices` applied the fitted mileage slope over
`subject_mileage - comp.mileage` with no bound on how far the subject sat outside
the comps' observed range. `fit_mileage_slope` guarded the comps' internal spread
and nothing guarded extrapolation *distance*, so normalized prices went negative,
`max(0.0, ...)` clamped them silently, and the engine shipped
`fair_range_usd = $0-$0` with a confident `above_range` verdict: "The asking price
of $6,000 is above the $0-$0 range these comparable listings support after the
deductions above. The gap is $6,000." That sentence propagated into the
negotiation script the buyer is told to say out loud. Comps at 50k, 100k and 150k
miles with a subject at 260,000 - an ordinary high-mileage car - reproduce it.

`MAX_EXTRAPOLATION_FRACTION = 0.25`, and the argument sits beside the number
because this repository does not accept a magic constant without one: a
least-squares line is evidence about the miles its listings cover, and at a
quarter of the span at least four fifths of the mileage under the answer was
observed. It composes with `MIN_MILEAGE_SPREAD` - a fit already needs 10,000 miles
of spread - so the allowance is never tighter than 2,500 miles. It is symmetric,
because extrapolating *downward* inflates the range and makes an overpriced car
look fair. A second guard refuses outright on any normalized price at or below
zero rather than letting it meet the clamp.

Both route through one `_no_verdict` helper that also took over the pre-existing
"too few comps" refusal, so there is a single way to decline - extending D-032's
path rather than running a parallel one beside it.

Two more of the same class were found while fixing these, and the second was
found by the crew's own mutation rather than by a test. Deductions larger than the
range produced the identical `$0-$0` sentence by a different route, and now refuse
with the finding that actually matters - the repairs cost more than a comparable
car - with the deductions still rendered. Then, with the below-zero guard
disabled, three $0 listings reached that new deduction guard and produced "The
repairs found on this car - $0 to $0 - come to more than these listings say the
whole car is worth." The guard now requires a non-zero deduction.
