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

<!-- generated: standing. scripts/check_readme.py - do not edit by hand -->

| | |
|---|---|
| Phases shipped | 10 |
| Tests | 942 (573 Python, 369 TypeScript) |
| Gates | 11, green local and CI |
| Laws | 7 |
| Decisions logged | 70 |
| Finding types the engines can produce | 16 |
| **Finding types with a measured accuracy** | **0** |
| **Finding types enabled for a paid report** | **0** |
| **Real vehicles this has ever seen** | **0** |
| **Live model calls ever made** | **0** |

<!-- end generated: standing -->

Those four zeros are the honest summary, and they have not moved in ten phases.
Everything built so far is a careful machine that has never been pointed at a
car, and it cannot legitimately sell a single finding.
[docs/ACCURACY.md](docs/ACCURACY.md) says so in its first line rather than
waiting until there is something flattering to put there.

What unblocks it: an `ANTHROPIC_API_KEY`, and one real car photographed per
[bench/README.md](bench/README.md).

**Every number in that table is read out of the repository by
`scripts/check_readme.py`, and a gate fails when the page and the repository
disagree.** That is not decoration. Before P10 the table said 612 tests when the
suites collected a different number, and the block below quoting the product's
own output was a *paraphrase* of it — tidied into aligned columns, with two of
the four lines shortened. Nothing load-bearing, which is exactly what drift looks
like before it matters.

---

## What makes this repository unusual

Most projects treat honesty as a documentation problem. This one treats it as an
engineering problem, and the difference shows up as tests.

**A claim that nothing checks is the defect class this project keeps finding in
itself.** It does not matter whether the claim lives in a docstring, a law, a
colour table, a feature switch, or a test's own name — if nothing executes it, it
drifts. Ten phases of evidence:

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
- A test named `..._the_sdk_actually_defines` asserted against a stub the test
  itself had built, and passed against an SDK that had renamed both attributes
  away. The signature defect, wearing the uniform of the test written to prevent
  it. *(P10)*

So the rules got teeth. **D-049:** a duplicated definition ships with the test
that compares the copies, in the same change. **D-050:** the layout gate opens a
real browser and fails rather than skips when it cannot. **D-055:** a gate that
cannot fetch what it is measuring fails loudly and names the paths it could not
fetch. **D-061/D-063:** a published number is generated from the thing it
describes, or it is not published.

Every test in this repository was verified by first breaking the thing it checks
and watching it go red.

### What P10 learned about that

P10 fixed the second half of a 70-finding audit, in seven parallel crews, and
then pointed an adversary at each crew's work with instructions to refute it.

**All nine gates were green, 776 tests passed, and every crew's work was
defective.** Not cosmetically: one had shipped a regression that turned a clean
car's history report into five major findings at full confidence, each one quoting
its own denial as the evidence. A pipe had been added to the statement-splitting
pattern, so `| Salvage | None reported |` — the commonest row in the commonest
layout — split into a bare label and an answer about nothing.

What found it was not another test. It was **mutation testing**: delete each
mechanism, and require something to go red. That is now the bar for a fix here,
and it is applied to the fixes in this paragraph too — including a guard in the
new classifier that survived its first mutation run unpinned, and got the test it
was missing.

---

## The seven laws

Full text in [docs/LAWS.md](docs/LAWS.md). Each names the file and the test that
enforces it, because a law in a markdown file is a suggestion.

| | Law | Enforced by |
|---|---|---|
| 1 | Every finding cites visible evidence | Pydantic validators + `Report._referential_integrity` |
| 2 | Safety-critical systems are never cleared remotely | `safety.py` clamp, applied after every engine |
| 3 | No scraping — user-provided media and IDs only | `net.py` host allowlist + `test_provenance.py` |
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

From the committed synthetic fixture, with no API key and no network — copied out
of `fixtures/reports/demo-01.report.json` by the same script that writes the table
above, so this cannot quietly become a paraphrase again:

<!-- generated: fixture. scripts/check_readme.py - do not edit by hand -->

```
2 finding(s) that are likely to cost money. Separately, 5 recall
campaign(s) are on record for this model year - free to fix, and worth
one phone call to a dealer.
```

Red-flag score 50/100 · 14 findings · 2 mechanic referrals · 83% coverage

The verdict opens with what it *could not* assess, and these lines are in
every report this product can produce:

```
Brakes - not remotely verifiable, independent mechanic required.
Airbags and restraints - not remotely verifiable, independent mechanic required.
Frame and structural integrity - not remotely verifiable, independent mechanic required.
Steering - not remotely verifiable, independent mechanic required.
```

<!-- end generated: fixture -->

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
  src/lib/markdown.ts         a parser for one document, which refuses everything else (D-062)
  src/lib/flow.test.ts        the LAW 7 end-to-end test, media included
  src/lib/layout.test.ts      the gate that opens a browser (D-050, D-055)
  src/lib/stress.ts           reports built to break the layout (D-051)
  src/lib/tokens.test.ts      every var(--tk-*) exists; BRAND.md matches the CSS
packages/shared             zod contracts. The schema the web app trusts
packages/db                 Drizzle schema for Neon. Written, not yet connected
  src/column-parity.test.ts   every contract field has a column, every table is compared (D-049)
packages/engines            Python 3.12. All analysis lives here
  vision.py                   two-stage image analysis
  signal.py, audio.py         ffmpeg, STFT, spectrogram, onset detection
  video.py                    walkaround frame selection
  data.py, sources.py         vPIC + NHTSA, cached and cited
  history.py                  title-brand scan of buyer documents
  pricing.py                  comps, and when to refuse to price
  safety.py                   the clamp
  registry.py                 the eval gate LAW 4 reads
  copy_rules.py               banned language, scanned across every buyer surface
  redact.py                   plate and face blurring, and metadata stripping
  prompts/                    versioned prompt files, inside the copy scan
bench/                      labels, reports, results. No media yet — that is the point
fixtures/                   synthetic media + committed federal records
docs/                       LAWS, LIABILITY, ACCURACY, EVAL, BRAND, UNIT_ECONOMICS
phase_reports/              what shipped, what was measured, what is still missing
DECISIONS.md                every judgment call, each with what it cost
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
because nothing ran is the failure this project has now found seven times.

### Regenerating derived artifacts

These are committed on purpose, so a fixture run needs no ffmpeg, no network and
no key. Each is a deliberate act that produces a reviewable diff.

```bash
pnpm run refresh:federal                       # vPIC + NHTSA. The only script that opens a socket
pnpm run refresh:audio                         # spectrogram + acoustic measurements
pnpm run refresh:video                         # walkaround frame selection, metadata stripped on the way out
pnpm run bench                                 # score reports against labels -> the eval gate
pnpm run redact -- check fixtures/demo-01/media # refuse media that is unreviewed or still carries metadata (D-022)
```

### Live mode

```bash
echo 'ANTHROPIC_API_KEY=sk-ant-...' >> .env
TIREKICK_MODE=live pnpm run inspect:fixture
```

Fixture mode is the default **in code**, not just in CI config, so a missing key
produces a deterministic cached run rather than a crash. Every run prints its
mode and stamps it into the report. The Anthropic SDK is a `live` extra and is
deliberately absent from what CI installs — which is why the one check that opens
the real package lives in `scripts/check_sdk_contract.py`, run by its own CI job
that installs it on purpose, and fails rather than skips when it is missing.

---

## Adding a finding type

The order matters. The gate exists to be inconvenient.

1. Add it to `FindingType` in `models.py` **and** `findingTypeSchema` in
   `packages/shared/src/schema.ts` **and** the `findingType` enum in
   `packages/db/src/schema.ts`. The contract
   drift test fails until all three agree (D-002).
2. Register it in `registry.py` with a precision gate and a written rationale for
   where that gate sits. Set it *before* you have results ([docs/EVAL.md](docs/EVAL.md)).
3. Emit it from an engine, with evidence. `DraftFinding` refuses one without.
4. Label examples in `bench/labels/`, run `pnpm run bench`, and let the measured
   number decide whether it ships. You do not get to skip this: a type that has
   been measured and *failed* is filtered out of the report and named in the
   could-not-assess block with its precision, its sample size and its threshold
   (D-056). There is no second place to type a number — `docs/ACCURACY.md`'s gate
   table is written from the registry by a script, and editing it by hand fails
   the build (D-061).

---

## Reading this repository

If you read four things:

1. **[DECISIONS.md](DECISIONS.md)** — every judgment call made without asking,
   and what it cost. Several retract earlier ones. D-016, D-023, D-027, D-032,
   D-056 and D-065 are the load-bearing ones.
2. **[phase_reports/PHASE_10.md](phase_reports/PHASE_10.md)** — what happened
   when seven fix crews were audited by seven adversaries, and why nine green
   gates did not catch a regression that turned a clean car into a wreck.
   [PHASE_9.md](phase_reports/PHASE_9.md) is the audit that produced the work.
3. **`packages/engines/src/tirekick_engines/prompts/vision/system.md`** — the most
   consequential prose here. It is what the model is told before it looks at a
   photograph of somebody's car.
4. **`packages/engines/src/tirekick_engines/safety.py`** — the clamp. One
   deterministic pass, and the whole product's promise.

---

## Fixture provenance

All media is synthetic: drawn images, a synthesised engine-like signal, a
generated panning video. Nothing in this repository is a photograph of a real
vehicle, and every committed image carries no EXIF, no XMP, no IPTC and no
comment segment — checked by the `redact:media` gate rather than asserted here.
Until P10 it was asserted here, and five video frames carried ffmpeg's encoder
banner while this paragraph said they carried nothing.

The exception is the vehicle record, which is **real** federal data for a
documentation VIN — real manufacturer codes with an invented serial, so it
decodes to a real model and identifies nobody. Both halves are labelled in the
report itself. See [fixtures/PROVENANCE.md](fixtures/PROVENANCE.md) and
[bench/PROVENANCE.md](bench/PROVENANCE.md), whose enumerations are now compared
against `git ls-files` by `test_provenance.py` — after one of them ran seven
phases with an unlisted artifact.

**No accuracy claim will ever cite synthetic media.**

---

## Known gaps

Kept here rather than only in a phase report, because a gap written down once and
never surfaced is how the defects above survived:

- **The eval set is empty**, so LAW 4 disables everything and the product cannot
  sell a finding. This is the whole project's blocking gap, and it needs a key
  and a car, not more code.
- **Persistence is local disk and Stripe is a payment link.** `inspections.ts`
  says so in its own header. The displayed price and the charged price are two
  different facts — the first is in this repository, the second is configured at
  Stripe — and `checkout.ts` says which is which rather than pretending the
  constant charges anybody.
- **Video and audio metadata is unchecked.** `redact check` reads still images
  only; an `.mp4` can carry GPS in its `©xyz` atom, and it says so in its own
  output rather than reporting a clean directory.
- **`docs/EVAL.md` promises four metrics `bench.py` does not compute** — F1,
  precision at high confidence, a severity confusion matrix, and a calibration
  plot. Marked as unimplemented in the document rather than left reading as
  though they exist.
- Smaller open items, each named with its failure scenario, are in
  [PHASE_10.md](phase_reports/PHASE_10.md) §4.

---

## Licence

MIT — see [LICENSE](LICENSE), which covers this repository's own source, docs and
synthetic fixture media. Three things travelling with it belong to somebody else
and are listed in [NOTICE](NOTICE): the bundled fonts (SIL OFL 1.1), the federal
records under `fixtures/federal/` (US government data, not subject to copyright),
and the Anthropic API the live path calls.
