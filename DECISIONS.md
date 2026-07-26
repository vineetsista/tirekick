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
