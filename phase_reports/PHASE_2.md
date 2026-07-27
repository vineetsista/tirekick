# PHASE 2 - VISION ENGINE

Tag: `v0.3` | Branch: `main` | 27 commits | 161 tracked files
Remote: `github.com/vineetsista/tirekick` (private - D-013, and now D-022)
Gates: 9/9 green, locally and in CI. 255 tests.

**Gate HALF met, and the half that is missing is the important one.**

The vision engine is built: prompts, the live Anthropic path, the eval harness,
the gate wiring. What does not exist is a single measured number, because that
needs an API key and photographs of real cars, and this phase had neither. You
chose to build it unmeasured rather than wait, which was the right call - but the
honest summary of P2 is that TIREKICK can now see, and has not yet been checked.

**0 of 16 finding types are enabled for a paid report. Same as P1. Same as P0.**

---

## 1. What shipped

**Prompts as versioned files** (`prompts/vision/*.md`). Ten of them, each with an
`id` and `version`, all inside the banned-language scan. The system prompt is the
load-bearing one, and two instructions in it matter more than the rest combined:
an empty list is a correct answer, and the four locked systems are never assessed
at any confidence.

**The live path** (`client.py`). Real Anthropic Messages calls with base64 images,
structured output forced through a tool rather than requested in prose, retries
that distinguish a rate limit from our own bad request, and token accounting into
the cost meter. It has never run. It is pinned by a fake API that asserts what we
would send.

**The vision engine, wired live** (`engines/vision.py`). Each pass constrained by
schema to the finding types it can legitimately produce. Locked systems still
permitted, on purpose.

**The eval harness** (`bench.py` + `bench/`). Labels in, reports in, precision and
recall out, at IoU 0.4 with the strict 0.5 figure beside it. The registry reads
what it writes, so there is now no second place in this codebase where a precision
number can be typed.

**The first non-invented COGS number.** Not a measurement - a calculation.

---

## 2. Decisions (D-022 .. D-025, full text in DECISIONS.md)

- **D-022** Real vehicle media means the repository stays private.
- **D-023** Sonnet 5 is the default, and the eval decides, not the price.
- **D-024** The model is never asked for a repair cost.
- **D-025** Prompts are versioned files inside the scanned surface.

**D-023 partly retracts its own reasoning.** Read that one.

---

## 3. Real measurements

| | |
|---|---|
| Gates | 9/9 green, local and CI |
| Tests | 257 (197 pytest / 41 web / 14 shared / 5 db) |
| Prompt files | 10, versioned, all scanned for banned language |
| Model calls per 8-photo capture | 22 (8 classify + 14 targeted passes) |
| Image tokens per phone photo | 2,459 (4032x3024 downscaled to 1568x1176) |
| Tokens per report | ~75,600 in / ~7,700 out |
| **Projected** inference, Sonnet 5 | **$0.34** (98.6% margin on $25) |
| **Projected** inference, Opus 5 | **$1.71** (93.2% margin on $25) |
| Labeled photographs in the eval set | **0** |
| Finding types measured | **0** |
| Finding types enabled for a paid report | **0** |
| Live API calls ever made | **0** |

Three things worth pulling out.

**The $5 inference ceiling from D-006 is nowhere near binding.** Every model we
would consider clears it by more than an order of magnitude. That is good news and
it is also an argument against my own reasoning: I set the default to Sonnet partly
on cost, and a $1.37 per-report difference does not decide anything. The model
choice is an accuracy question and it belongs to the eval. D-023 says so.

**The real cost risk is the free teaser, not the model.** At 10% conversion, ten
teasers at $0.34 make one paid report cost $3.40 - a tenfold swing that no model
choice comes close to. That is the number to watch in P4, and it is already in the
measurement list in `docs/UNIT_ECONOMICS.md`.

**The banned-language scan caught two violations in prompts I had just written**,
within a minute of the scan being extended to cover them. Both were me using a
banned word in order to forbid it. I rephrased rather than widening the sanctioned
list, because that list exists for buyer-facing disclaimers and would be weakened
by absorbing internal instructions.

### Two things CI found after the tag, and one of them matters a lot

The first push of this phase went red, and chasing it turned up a worse problem
than the one it reported.

**The live path imported the SDK even when faked.** `_send` had `import anthropic`
at the top of the retry loop, which runs even when the client is a test double. So
the entire live-vision suite passed on this machine - where the `live` extra
happens to be installed - and every test in it failed in CI, where it deliberately
is not. That is LAW 7's gate doing precisely its job: the environment without the
optional dependency is the only one that can catch this, and the machine writing
the code is the one machine that cannot. Fixed, plus two regression tests that
simulate the SDK's absence rather than trusting the environment.

**The mypy gate has never been strict.** Not since P0. `mypy` discovers its config
from the working directory, `scripts/gates.sh` runs from the repo root, and there
is no `pyproject.toml` there - so `strict = true` in
`packages/engines/pyproject.toml` was never read by CI or by the local gate script.
Verified rather than assumed: a function with no annotations at all passes the root
invocation and is caught by the package one.

LAW 7 says "TS strict + ruff/mypy". Half of that has been decoration for three
phases. The gate now names its config file, strict genuinely applies, and the
codebase passes it cleanly - the code was written to the standard, only the check
was hollow. Worth sitting with: this was found by accident, while chasing an
unrelated failure, and nothing else would have surfaced it.

---

## 4. Gaps

1. **No API key, so the live path has never executed.** Everything about it is
   asserted against a fake. The first real call will find something; they always do.
   This is REP 2.
2. **No labeled photographs, so nothing is measured.** The harness runs and
   correctly reports that it has nothing to score. This is REP 3, and it is the
   only thing standing between this product and its first honest number.
3. **P2 deliberately did not score the vision engine on the synthetic fixtures.**
   It would have produced a number describing how well the model reads drawings we
   made for it to read. That is worse than no number, because it looks like one.
4. **Still no Vercel deploy.** Third phase running. Nothing is publicly reachable.
5. **The repository must now stay private (D-022)**, and unlike D-013 this is not
   reversible with one command. Once a photograph with a plate is committed, making
   the repo public publishes it permanently - `git rm` does not touch history. A
   blur step has to exist before the public option comes back.
6. **A prompt change does not invalidate cached responses.** Versions are recorded
   in each response and fingerprinted into the report, so drift is *visible*, but
   nothing enforces it: edit `rust.md` and the old cached findings still load. The
   fix is putting the prompt version in the cache key, which renames every fixture,
   so it wants doing when the fixtures are regenerated from real captures anyway.
7. **Documents still are not OCR'd.** A photographed title is reported as unread.
8. **`min_n = 50` is still a judgment, not a derivation** - carried over from P1.
9. **Three phases of mypy runs proved nothing.** The gate is fixed now, but every
   "py:types PASS" in the P0, P1 and P2 reports was a weaker claim than it looked.
   I have not gone back and re-verified those phases under strict; the code passes
   strict today, which covers it, but the earlier green ticks were not what they
   said.

---

## 5. YOUR 2 HOURS

### Read, in this order (50 min)

1. `packages/engines/src/tirekick_engines/prompts/vision/system.md` - **10 min**,
   the whole file. This is the most consequential prose in the repository: it is
   what the model is told before it looks at a photograph of someone's car. Line 30
   ("an empty list is a real result") and line 38 ("Four systems you never assess")
   are where false positives and LAW 2 respectively live or die.
2. `bench/README.md`, the capture and labeling sections - **15 min**. You are the
   one who will execute this. Read it as instructions, and tell me where they are
   ambiguous.
3. `packages/engines/src/tirekick_engines/bench.py`, module docstring and `score` -
   **10 min**.
4. `DECISIONS.md` D-023 and D-024 - **10 min**.
5. Run the harness on nothing - **5 min**:
   ```
   packages/engines/.venv/bin/python -m tirekick_engines.cli bench
   ```
   It should tell you, clearly, that it has nothing to score.

### Assigned reading (30 min)

**"Are We on the Right Way for Evaluating Large Vision-Language Models?"**
https://arxiv.org/abs/2403.20330 (verified live). Read the abstract and section 2.

The finding: a large fraction of questions in standard VLM benchmarks can be
answered correctly *without looking at the image*, and a further chunk leak into
training data. Benchmarks were reporting capability that was not there.

Read it as a warning about `bench/`, not about somebody else's leaderboard. Our
version of that failure is concrete and I have written the two guards into
`bench/README.md`: an eval set of nothing but damaged cars, where "there is rust
here" is right every time without looking; and labels quietly reconciled with
model output after the fact. Both would produce excellent numbers.

*Optional, 10 min, if you want the detection-metric background:*
https://cocodataset.org/#detection-eval - where IoU thresholds and the
precision/recall convention in `bench.py` come from.

*The mechanic's inspection checklist moves to P3, where it decides which findings
to build next. Spectrogram basics stay with the audio engine.*

### Drill - answer from the code (40 min)

1. **A photograph shows an undamaged door. What should the model return, and what
   in the system prompt makes that the expected answer rather than a failure?**
   `prompts/vision/system.md:30`. Why is this the instruction I would defend
   hardest if you wanted it softened?

2. **The engine-bay pass sees fluid pooled behind a front wheel. Trace it from
   schema to report.**
   `engines/vision.py:119` (the schema permits `brakes`), then `safety.py`. Why is
   it not blocked at the schema, where blocking would be easier?

3. **A model returns a $400-900 estimate for a dent. Where does that number die?**
   `engines/vision.py:74` and the module docstring; `tests/test_live_vision.py:175`.
   Why removed from the schema rather than filtered after?

4. **Two overlapping boxes are drawn over one rusty rocker panel. What does the
   harness score, and why is that not pedantry?**
   `bench.py:252` (`claimed`), `tests/test_bench.py:85`.

5. **The eval set is ten photographs of rusty cars and the model scores 1.00
   precision. What is wrong, and which line of code would have caught it?**
   `bench.py:225` (`judged`), `tests/test_bench.py:110`, and the rule in
   `bench/README.md`. This is the assigned reading, in our own codebase.

---

## 6. FOUNDER REPS (~30 min)

### REP 1 - Deploy the web app (10 min) - carried from P0 and P1

Unchanged and still blocking. vercel.com, import `vineetsista/tirekick`, root
directory `apps/web`, build command `pnpm --filter web run build`, framework
Next.js, no environment variables. Open `/report/demo-01` and confirm the overlays
render.

**The public-repo question is now closed until further notice** (D-022): once real
photos land, public means published plates, and that is not one command to undo.

### REP 2 - Give me an API key (5 min)

Nothing in P2 has ever executed against a real model.

1. console.anthropic.com -> API keys -> create one, scoped to a project you can
   cap. **Set a low monthly limit** - $20 is more than enough for the whole eval.
2. In the repo root:
   ```bash
   echo 'ANTHROPIC_API_KEY=sk-ant-...' >> .env
   ```
   `.env` is gitignored (`.gitignore:26`). Do not paste the key into chat.

The projection says a full 8-photo run costs about $0.34 on Sonnet. If the first
live run costs wildly more than that, the projection is wrong and I want to know
immediately rather than at scale.

### REP 3 - Photograph one car (15 min)

Not three. One. Enough to prove the whole pipeline on real media before you spend
an afternoon on a full set.

Follow the eight-shot list in `bench/README.md`. The rules that matter:

- **Overcast light if you can.** Direct sun makes shadows that read as dents, and
  that is the single largest source of false positives I expect.
- **Do not wash it first.**
- **Shoot the bad side.** The instinct is to photograph what looks good.
- Dash photo with the **engine running**, not during the ignition self-test.

Then write down, in plain text, everything you know to be true about that car -
including things a photograph cannot show. Especially those. They do not become
labels; they are how we find out what this product is structurally blind to.

Send me the folder and I will run it, label nothing myself, and hand you back the
model's output to check against what you wrote down.

---

## 7. NEXT - P3: AUDIO ENGINE, and the first real numbers

Two threads.

**The one that matters:** the moment REP 2 and REP 3 land, the vision engine runs
live against real photographs, the eval set gets labeled, and `docs/ACCURACY.md`
stops saying "no measurements have been made". That is the first time this project
can honestly claim anything, and it is also the first time it can be shown to be
wrong. Expect some finding types to fail their gates. That is the system working.

**The scheduled one:** the audio engine. ffmpeg, spectrograms, and the lowest
precision gate in the registry (0.70) because it is expected to be the weakest
engine we have. Below gate it ships as a spectrogram with no claims attached, which
is `docs/EVAL.md`'s existing answer for exactly this case.
