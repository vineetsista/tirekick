# TIREKICK

**An AI pre-purchase analysis for used cars — and an experiment in building
something that refuses to overstate itself.**

You give it the listing photos, a walkaround video, thirty seconds of engine
audio, the VIN, any paperwork you have, and a few comparable listings you found
yourself. It returns an evidence-annotated dossier: what it can see, *where* it
saw it, how sure it is, what it could not determine, what to ask the seller, and
what a mechanic still has to check.

It is not an inspection. It never clears brakes, airbags, frame, or steering —
those are hard-locked to "independent mechanic required" in code, not in copy.

---

## Read this before anything else

| | |
|---|---|
| Phases shipped | 9 |
| Tests | 612 |
| Gates | 9/9 green, local and CI |
| Decisions logged | 60 |
| Finding types the engines can produce | 16 |
| **Finding types with a measured accuracy** | **0** |
| **Finding types enabled for a paid report** | **0** |
| **Real vehicles this has ever seen** | **0** |
| **Live model calls ever made** | **0** |

Those four zeros are the honest summary, and they have not moved in nine phases.
Everything built so far is a careful machine that has never been pointed at a
car, and it cannot legitimately sell a single finding.
[docs/ACCURACY.md](docs/ACCURACY.md) says so in its first line rather than
waiting until there is something flattering to put there.

What unblocks it: an `ANTHROPIC_API_KEY`, and one real car photographed per
[bench/README.md](bench/README.md).

---

## What makes this repository unusual

Most projects treat honesty as a documentation problem. This one treats it as an
engineering problem, and the difference shows up as tests.

**A claim that nothing checks is the defect class this project keeps finding in
itself.** It does not matter whether the claim lives in a docstring, a law, a
colour table, or a feature switch — if nothing executes it, it drifts. Nine
phases of evidence:

- A component docstring said evidence sat one interaction from its claim. It sat
  four thousand pixels away. *(P8)*
- `BRAND.md` documented a colour table where **every value was wrong**, and one
  named a token the stylesheet had deleted. *(P8)*
- The browser-based layout gate served images from a path that could not resolve,
  so for a full phase it measured **every page with zero-size images and fallback
  fonts** — 73 green assertions about a layout nothing had laid out. Its own
  comment warned that this exact failure would make the numbers "fiction." *(P9)*
- LAW 4 names a registry flag as its enforcement point. That flag was read by the
  gate table and the accuracy statement — by the things that *describe* the gate
  — and by nothing in the report path. **It governed a console printout.** *(P9)*
- The negotiation script told buyers to say, to a seller's face: *"a shop quoted
  that kind of work at roughly $600 to $900."* No shop was called. *(P9)*

So the rules got teeth. **D-049:** a duplicated definition ships with the test
that compares the copies, in the same change — not a comment saying "mirrored in
X". **D-050:** the layout gate opens a real browser and fails rather than skips
when it cannot. **D-055:** a gate that cannot fetch what it is measuring fails
loudly and names the paths it could not fetch.

Every test in this repository was verified by first breaking the thing it checks
and watching it go red.

---

## The seven laws

Full text in [docs/LAWS.md](docs/LAWS.md). Each names the file and the test that
enforces it, because a law in a markdown file is a suggestion.

| | Law | Enforced by |
|---|---|---|
| 1 | Every finding cites visible evidence | Pydantic validators + `Report._referential_integrity` |
| 2 | Safety-critical systems are never cleared remotely | `safety.py` clamp, applied after every engine |
| 3 | No scraping — user-provided media and IDs only | `net.py` host allowlist |
| 4 | Nothing ships to a paid report before it clears its precision gate | `registry.py` reading `bench.py` output |
| 5 | Every run prints its cost | `cogs.py`, printed unconditionally |
| 6 | Name the AI, publish the accuracy | `copy_rules.py` scan + a generated accuracy statement |
| 7 | Green gates every phase | `scripts/gates.sh` + `test_laws_are_kept.py` |

**LAW 2 is the one to understand first.** Engines may say whatever they say. A
deterministic pass then discards any finding touching brakes, restraints,
structure or steering — with one asymmetry: an *adverse* observation survives as
a mechanic referral carrying its evidence, stripped of severity and confidence.

> We can raise an alarm. We cannot sound an all-clear.

---

## What it actually produces

From the committed synthetic fixture, with no API key and no network:

```
2 finding(s) that are likely to cost money. Separately, 5 recall campaign(s)
are on record for this model year - free to fix, and worth one phone call to
a dealer.
```

Red-flag score 50/100 · 14 findings · 2 mechanic referrals · 83% coverage

The verdict opens with what it *could not* assess, and the first four lines never
change:

```
Brakes      - not remotely verifiable, independent mechanic required.
Restraints  - not remotely verifiable, independent mechanic required.
Structure   - not remotely verifiable, independent mechanic required.
Steering    - not remotely verifiable, independent mechanic required.
```

Note that the headline separates *this car* from *its model year*. Five recall
campaigns are filed against every car of that model year and are free to remedy;
counting them as defects turned a 2013 Accord into a 100/100 wreck, so they are
scored separately, excluded from the systems table, and reported in full in their
own section (D-021, D-058).

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
  registry.withheld_types ....... LAW 4: a type measured and failing does not ship
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

Four properties of that pipeline are worth stating, because each is easy to lose
and expensive to lose quietly:

**The clamp is one place.** Engines do not each police themselves. Everything
funnels through `apply_safety_law`, which is why LAW 2 is a guarantee rather than
an intention (D-004).

**"Examined" and "covered" are different.** A system is reported clean only if
the required views arrived *and* a pass that could have found something actually
ran. A system nothing looked at reads `cannot_determine`, however many
photographs arrived. That distinction is what stops silence reading as good news.

**The teaser is a projection, not a redaction.** The free payload is a genuinely
smaller object — what is missing was never serialised. A paywall you can defeat
with the network tab is not a paywall (D-031), and its unlock list is derived
from what the report actually contains, so nobody is sold a section their report
will not render (D-059).

**The evidence is served through the same check as the page.** `/f/<id>/*` is a
route handler that verifies the same grant the dossier does and serves only what
the report *cites* — never simply "what is in the directory", because a media
directory can also hold redaction sidecars naming reviewers and boxing faces
(D-052).

---

## Layout

```
apps/web                    Next.js 15. Landing, upload, teaser, checkout, report, share
  src/app/f/[...]/route.ts    media behind the grant (D-052)
  src/app/new/                upload -> analyse -> owner grant -> free result
  src/lib/access.ts           signed grants, tiered: paid / demo / owner
  src/lib/media.ts            the allowlist: what a report cites, and nothing else
  src/lib/crop.ts             geometry that puts a cited region beside its claim
  src/lib/flow.test.ts        the LAW 7 end-to-end test, media included
  src/lib/layout.test.ts      the gate that opens a browser (D-050, D-055)
  src/lib/stress.ts           reports built to break the layout (D-051)
  src/lib/tokens.test.ts      every var(--tk-*) exists; BRAND.md matches the CSS
packages/shared             zod contracts. The schema the web app trusts
packages/db                 Drizzle schema for Neon. Written, not yet connected
  src/column-parity.test.ts   every contract field has a column (D-049)
packages/engines            Python 3.12. All analysis lives here (~7.5k lines)
  vision.py                   two-stage image analysis
  signal.py, audio.py         ffmpeg, STFT, spectrogram, onset detection
  video.py                    walkaround frame selection
  data.py, sources.py         vPIC + NHTSA, cached and cited
  history.py                  title-brand scan of buyer documents
  pricing.py                  comps, and when to refuse to price
  safety.py                   the clamp
  registry.py                 the eval gate LAW 4 reads
  copy_rules.py               banned language, scanned across every buyer surface
  redact.py                   plate and face blurring
  prompts/                    versioned prompt files, inside the copy scan
bench/                      labels, reports, results. No media yet — that is the point
fixtures/                   synthetic media + committed federal records
docs/                       LAWS, LIABILITY, ACCURACY, EVAL, BRAND, UNIT_ECONOMICS
phase_reports/              what shipped, what was measured, what is still missing
DECISIONS.md                60 judgment calls, each with what it cost
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

Pages worth opening: `/`, `/new`, `/teaser/demo-01`, `/buy/demo-01`,
`/report/demo-01`, `/share/demo-01`, `/accuracy`.

The layout gate needs chromium once:

```bash
pnpm --filter web exec playwright install chromium
```

It fails rather than skips if the browser is absent. A gate that goes green
because nothing ran is the failure this project has found six times.

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
produces a deterministic cached run rather than a crash. Every run prints its
mode and stamps it into the report.

---

## Adding a finding type

The order matters. The gate exists to be inconvenient.

1. Add it to `FindingType` in `models.py` **and** `findingTypeSchema` in
   `schema.ts` **and** the `findingType` enum in `db/schema.ts`. The contract
   drift test fails until all three agree (D-002).
2. Register it in `registry.py` with a precision gate and a written rationale for
   where that gate sits. Set it *before* you have results ([docs/EVAL.md](docs/EVAL.md)).
3. Emit it from an engine, with evidence. `DraftFinding` refuses one without.
4. Label examples in `bench/labels/`, run `pnpm run bench`, and let the measured
   number decide whether it ships. You do not get to skip this: a type that has
   been measured and *failed* is filtered out of the report and named in the
   could-not-assess block with its precision, its sample size and its threshold
   (D-056). There is no second place to type a number.

---

## Reading this repository

If you read four things:

1. **[DECISIONS.md](DECISIONS.md)** — every judgment call made without asking,
   and what it cost. Several retract earlier ones. D-016, D-023, D-027, D-032 and
   D-056 are the load-bearing ones.
2. **[phase_reports/PHASE_9.md](phase_reports/PHASE_9.md)** — a ten-specialist
   adversarial audit of the repository against itself. Seventy findings survived
   verification; about half are fixed and the rest are listed by name.
3. **`packages/engines/src/tirekick_engines/prompts/vision/system.md`** — the most
   consequential prose here. It is what the model is told before it looks at a
   photograph of somebody's car.
4. **`packages/engines/src/tirekick_engines/safety.py`** — the clamp. One
   deterministic pass, and the whole product's promise.

---

## Fixture provenance

All media is synthetic: drawn images, a synthesised engine-like signal, a
generated panning video. Nothing in this repository is a photograph of a real
vehicle, and the committed images carry no EXIF.

The exception is the vehicle record, which is **real** federal data for a
documentation VIN — real manufacturer codes with an invented serial, so it
decodes to a real model and identifies nobody. Both halves are labelled in the
report itself. See [fixtures/PROVENANCE.md](fixtures/PROVENANCE.md) and
[bench/PROVENANCE.md](bench/PROVENANCE.md).

**No accuracy claim will ever cite synthetic media.**

---

## Known gaps

Kept here rather than only in a phase report, because a gap written down once and
never surfaced is how the defects above survived:

- **EXIF GPS survives redaction** for any image a reviewer marks "nothing to
  redact" — the strip only happens inside a re-encode that path skips. A live
  privacy hole in the tool whose entire job is preventing it. First work of P10.
- **Enumerated history rows read as denials**: `"No. 3 - SALVAGE TITLE ISSUED"`
  classifies as denied because the negation pattern matches the abbreviation.
- Persistence is local disk and Stripe is a payment link; `inspections.ts` says so
  in its own header.
- Contract parity gaps between the zod and pydantic sides, and several
  test-infrastructure checks that cannot currently fail, are enumerated in
  [PHASE_9.md §3](phase_reports/PHASE_9.md).

---

Bundled fonts (Archivo, Newsreader, JetBrains Mono) are SIL OFL 1.1; the licence
text and copyright notices travel with them in `apps/web/public/fonts/`. The
project itself carries no licence yet, which means all rights reserved by default.
