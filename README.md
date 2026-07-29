# TIREKICK

**An AI pre-purchase analysis for used cars.**

You give it the listing photos, a walkaround video, thirty seconds of engine
audio, the VIN, any paperwork you have, and a few comparable listings you found
yourself. It gives back an evidence-annotated dossier: what it can see, where it
saw it, how sure it is, what it cannot determine, what to ask the seller, and what
a mechanic still has to check.

It is not an inspection. It never clears brakes, airbags, frame, or steering -
those are hard-locked to "independent mechanic required" in code, not in copy.

---

## Status - read this before anything else

| | |
|---|---|
| Phases shipped | 8 |
| Tests | 469 |
| Gates | 9/9 green, local and CI |
| Finding types the engines can produce | 16 |
| **Finding types with a measured accuracy** | **0** |
| **Finding types enabled for a paid report** | **0** |
| **Real vehicles this has ever seen** | **0** |
| **Live model calls ever made** | **0** |

Those four zeros are the honest summary. Everything built so far is a careful
machine that has never been pointed at a car, and it cannot legitimately sell a
single finding. [docs/ACCURACY.md](docs/ACCURACY.md) says so in its first line
rather than waiting until there is something flattering to put there.

What unblocks it: an `ANTHROPIC_API_KEY`, and one real car photographed per
[bench/README.md](bench/README.md).

---

## The seven laws

Full text in [docs/LAWS.md](docs/LAWS.md). Each names the file and the test that
enforces it, because a law in a markdown file is a suggestion.

| | Law | Enforced by |
|---|---|---|
| 1 | Every finding cites visible evidence | Pydantic validators + `Report._referential_integrity` |
| 2 | Safety-critical systems are never cleared remotely | `safety.py` clamp, applied after every engine |
| 3 | No scraping - user-provided media and IDs only | `net.py` host allowlist |
| 4 | Nothing ships to a paid report before it clears its precision gate | `registry.py` reading `bench.py` output |
| 5 | Every run prints its cost | `cogs.py`, printed unconditionally |
| 6 | Name the AI, publish the accuracy | `copy_rules.py` scan + a generated accuracy statement |
| 7 | Green gates every phase | `scripts/gates.sh` + `test_laws_are_kept.py` |

**LAW 2 is the one to understand first.** Engines may say whatever they say. A
deterministic pass then discards any finding touching brakes, restraints,
structure or steering - with one asymmetry: an *adverse* observation survives as a
mechanic referral carrying its evidence, stripped of severity and confidence. We
can raise an alarm. We cannot sound an all-clear.

---

## How a report is built

```
manifest.json + media/
        |
        v
  materialize_assets ............ hash every file, so a finding cites the pixels it was written against
        |
        v
  walkaround.load_frames ........ sharpest non-duplicate frames from the video, as photo assets
        |
        v
  vision.classify_views ......... stage 1: what view is this photograph?
        |
        v
  vision.draft_findings ......... stage 2: only the passes that view can answer
        |
        v
  audio.load_track .............. spectrogram + measurements. Zero claims (LAW 4)
  data.lookup ................... vPIC decode, NHTSA recalls, complaint counts
  history.title_brand_findings .. reads your paperwork; queries no title registry
        |
        v
  safety.apply_safety_law ....... THE CLAMP. Nothing reaches a report without passing here
        |
        v
  dossier.build_report .......... systems table, coverage, verdict, price, script
        |
        +--> report.json ......... the paid dossier
        +--> teaser.json ......... a smaller object, not a hidden one
```

Two properties of that pipeline are worth stating because they are easy to lose:

**The clamp is one place.** Engines do not each police themselves. Everything
funnels through `apply_safety_law`, which is why LAW 2 is a guarantee rather than
an intention (D-004).

**"Examined" and "covered" are different.** A system is reported clean only if the
required views arrived *and* a pass that could have found something actually ran.
A system nothing looked at reads `cannot_determine`, however many photographs
arrived. That distinction is what stops silence reading as good news.

---

## Layout

```
apps/web              Next.js 15. Landing, teaser, checkout, report, share
  src/lib/access.ts     signed grants - who may read a paid dossier
  src/lib/crop.ts       geometry that puts a cited region beside its claim
  src/lib/flow.test.ts  the LAW 7 end-to-end test
  src/lib/tokens.test.ts  every var(--tk-*) exists; BRAND.md matches the CSS
  src/lib/layout.test.ts  the gate that opens a browser (D-050)
packages/shared       zod contracts. The schema the web app trusts
packages/db           Drizzle schema for Neon. Written, not yet connected
  src/column-parity.test.ts  every contract field has a column (D-049)
packages/engines      Python 3.12. All analysis lives here
  vision.py             two-stage image analysis
  signal.py, audio.py   ffmpeg, STFT, spectrogram, onset detection
  video.py              walkaround frame selection
  data.py, sources.py   vPIC + NHTSA, cached and cited
  history.py            title-brand scan of buyer documents
  pricing.py            comps, and when to refuse to price
  safety.py             the clamp
  bench.py              the eval harness LAW 4 reads from
  redact.py             plate and face blurring
  prompts/              versioned prompt files, inside the copy scan
bench/                labels, reports, results. Currently empty
fixtures/             synthetic media + committed federal records
docs/                 LAWS, LIABILITY, ACCURACY, EVAL, BRAND, UNIT_ECONOMICS
phase_reports/        what shipped, what was measured, what is missing
DECISIONS.md          50 judgment calls, with what each cost
```

---

## Running it

```bash
pnpm install
pnpm run py:setup            # packages/engines/.venv
pnpm run inspect:fixture     # full report + teaser, no API key needed
pnpm --filter web dev        # localhost:3000
pnpm run gates               # everything CI runs
```

Pages worth opening: `/`, `/teaser/demo-01`, `/buy/demo-01`, `/report/demo-01`,
`/share/demo-01`, `/accuracy`.

### Regenerating derived artifacts

These are committed on purpose, so a fixture run needs no ffmpeg, no network and
no key. Each is a deliberate act that produces a reviewable diff.

```bash
pnpm run refresh:federal              # vPIC + NHTSA. The only script that opens a socket
pnpm run refresh:audio                # spectrogram + acoustic measurements
pnpm run refresh:video                # walkaround frame selection
pnpm run bench                        # score reports against labels -> the eval gate
pnpm run redact -- check bench/media  # refuse unreviewed media (D-022)
```

### Live mode

```bash
echo 'ANTHROPIC_API_KEY=sk-ant-...' >> .env
TIREKICK_MODE=live pnpm run inspect:fixture
```

Fixture mode is the default **in code**, not just in CI config, so a missing key
produces a deterministic cached run rather than a crash. Every run prints its mode
and stamps it into the report.

---

## Adding a finding type

The order matters. The gate exists to be inconvenient.

1. Add it to `FindingType` in `models.py` **and** `findingTypeSchema` in
   `schema.ts` **and** the `findingType` enum in `db/schema.ts`. The contract
   drift test fails until all three agree (D-002).
2. Register it in `registry.py` with a precision gate and a written rationale for
   where that gate sits. Set it *before* you have results (`docs/EVAL.md`).
3. Emit it from an engine, with evidence. `DraftFinding` refuses one without.
4. Label examples in `bench/labels/`, run `pnpm run bench`, and let the measured
   number decide whether it ships. You do not get to skip this: `enabled_for_paid`
   reads the bench result file, and there is no second place to type a number.

---

## Reading this repository

If you read three things:

1. **[DECISIONS.md](DECISIONS.md)** - every judgment call made without asking, and
   what it cost. Several retract earlier ones. D-016, D-023, D-027 and D-032 are
   the load-bearing ones.
2. **`packages/engines/src/tirekick_engines/prompts/vision/system.md`** - the most
   consequential prose here. It is what the model is told before it looks at a
   photograph of somebody's car.
3. **The latest [phase_reports/](phase_reports/)** - the gaps section is the useful
   part.

## Fixture provenance

All media is synthetic: drawn images, a synthesised engine-like signal, a
generated panning video. The exception is the vehicle record, which is **real**
federal data for a documentation VIN - real manufacturer codes with an invented
serial, so it decodes to a real model and identifies nobody. Both halves are
labelled in the report itself. See [fixtures/PROVENANCE.md](fixtures/PROVENANCE.md).

No accuracy claim will ever cite synthetic media.
