# UNIT ECONOMICS

**Nine phases in: still no real API calls, so there is still no measured $/report.**
P2 added a *calculated* projection, which is a different and weaker thing than a
measurement, and is labeled as such everywhere it appears below. Nothing on this
page has been replaced by a measurement since, because nothing has been measured.

The projection is arithmetic over the price table in
`packages/engines/src/tirekick_engines/cogs.py`. This page went three phases quoting
Opus at three times its actual rate: the table was corrected and this page was not,
so the corrected number sat in the code while the stale one sat on the page someone
would actually read.

**Since P10 the per-MTok columns below are read out of the markdown and compared to
`cogs.MODEL_PRICES`** by `packages/engines/tests/test_docs_numbers.py`, so that
particular failure - code corrected, page not - is now a red build. What no test can
reach is whether `cogs.py` itself still matches Anthropic's published prices. That is
a dated comment in the file and a human re-checking it, and a wrong number there
produces a wrong number here that still looks authoritative, with both places
agreeing.

The difference matters. A projection is arithmetic over token counts we can compute
from the images and prompts we would actually send. A measurement is what the
invoice says. They will not match, and the gap is the interesting part.

LAW 5: every run prints its cost. The per-run print is the source of truth for this
page.

## Price point

Target: **$25** per full dossier ($19-29 band per the brief). Free red-flag teaser
above it.

## Cost model per report - ASSUMPTIONS ONLY

| Line item | Assumption | Basis |
|---|---|---|
| Photos analyzed | 20 | typical listing set + buyer walkaround stills |
| Vision: view classification | 20 images, 1 cheap pass | assumption |
| Vision: targeted passes | ~8 images get a detailed pass | assumption |
| Audio | 30s clip, local ffmpeg + spectrogram, 1 model pass | assumption, and not built - the audio engine makes no model call today |
| Data engine | vPIC + recalls + complaints, cached | free federal APIs |
| Pricing | text-only, user-pasted comps | assumption |
| Dossier synthesis | 1 long-context pass | assumption, and not built - `dossier.py` assembles the report deterministically and calls nothing |
| Video | 1 walkaround clip, frames selected locally, kept frames analyzed as photos | built - `pipeline.py` appends the kept frames to the asset list, so they cost what photographs cost |
| Storage | ~60MB media, 90 day retention, priced at $0.023/GB-month | `PRICE_PER_GB_MONTH` in `cogs.py` |
| Egress / PDF render | negligible | assumption |

Two of those rows describe passes that do not exist. Every model call the pipeline
makes today is a vision call: the only two `client.call` sites in
`packages/engines/src` are stage 1 and stage 2 in `engines/vision.py`. Nothing checks
that count, so if a third ever appears this paragraph goes stale the same way the
projection below did. The audio and dossier rows are kept because
they are still the intended shape and because deleting them would hide that this
page's cost model is ahead of the code, but nothing below prices them.

**A photo count is not a call count**, which is the trap this section set for the
projection underneath it for eight phases. `PASSES_BY_VIEW` routes by *view*, and an
exterior view takes three stage-2 passes where an odometer takes one and a photograph
of paperwork takes none. Twenty photos is between 20 and 80 calls depending on a mix
this table does not state and we have no real capture to take one from. So the
projection below does not price this row. It prices captures whose view mix is known,
and says which.

**Not estimated here on purpose:** total dollars per report. Writing a plausible-looking
$/report number before a single real call is exactly the kind of number that becomes
load-bearing and is never revisited. The `CostMeter` fills it in from measurement.

What *is* fixed: the gross-margin floor we will hold. **A report that costs more than
$5 in inference does not ship at $25.** If measurement lands above that, the
response is fewer/cheaper passes or a higher price, not quiet acceptance.

## Projected inference cost per report - CALCULATED, NOT MEASURED

This is computable without spending anything. The inputs are all known: image tokens
are `width * height / 750` on images we downscale ourselves to a 1568px long edge
(`MAX_IMAGE_EDGE` and `image_tokens()` in `client.py`), the prompts are files we can
count, and `PASSES_BY_VIEW` in `engines/vision.py` says exactly how many calls a
capture makes.

**How a capture becomes a number of calls.** One classification call per photo, then
one stage-2 call per (photo, pass) pair `PASSES_BY_VIEW` allows: each of the five
exterior views takes three passes, interior/dash/odometer/tire/engine-bay take one
each, and `vin_plate`, `document` and `unknown` take none. A walkaround adds to that
count rather than replacing part of it - `pipeline.py` appends the frames `video.py`
kept to the asset list before vision runs, so a kept frame is classified and routed
exactly like an uploaded photograph. That is the point of the frames (they close
coverage gaps nothing else can) and it is also why they cost what photographs cost.

Three capture shapes, and the figures below name which one they describe, because the
last edit of this section did not and got it wrong:

| Capture shape | Classify | Stage 2 | Model calls |
|---|---|---|---|
| Eight photos in demo-01's view mix, no video - **what the dollars below price** | 8 | 14 | **22** |
| demo-01 as it is actually committed: those eight photos plus the 14s walkaround | 13 | 26 | 39 |
| Eight exterior shots and nothing else | 8 | 24 | 32 |

The middle row is arithmetic over `fixtures/demo-01/manifest.json` and the committed
frame selection, not a guess. The manifest declares eleven assets - eight photos,
`video_01.mp4`, `audio_01.wav`, `history_01.txt` - and the video contributes five kept
frames, so thirteen images are classified. Seven of those thirteen classify as
exterior views (three photos, four frames) at three passes each, five take one pass
each, and the fifth frame classifies `unknown` and routes nowhere: 21 + 5 = 26.

**A fixture run is not that number either.** `cli inspect --fixture demo-01` prints
`images analyzed 29`, because the fixture caches 13 classifications and only 16 of the
26 stage-2 passes, and an uncached pass does not run - deliberately, so that the
degradation path is exercised on every run (`fixtures/PROVENANCE.md` says why). 29 is
a count of cached responses. It is already larger than the 22 this section prices, on
the deliberately under-cached path.

A phone photo at 4032x3024 downscales to 1568x1176, which is **2,459 image tokens**.
Add roughly 980 tokens of system prompt, pass prompt and tool schema per call -
`prompts/vision/system.md` is 2,895 characters and a pass prompt is 700-1,200, at the
usual four-ish characters per token - and assume 350 output tokens per call. Over 22
calls that is roughly **75,600 input** and **7,700 output** tokens per report. The
output figure is the softest number on this page: nothing has ever generated one.

One row per model priced in `cogs.py`, at its per-MTok list price. The `TIREKICK_MODEL`
column is here so a test can compare the row to the code rather than a reader
comparing "Opus 5" to `claude-opus-5` by eye:

| Model | `TIREKICK_MODEL` | $/Mtok in | $/Mtok out | Projected inference | Margin on $25 |
|---|---|---|---|---|---|
| Haiku 4.5 | `claude-haiku-4-5`, `claude-haiku-4-5-20251001` | 1.00 | 5.00 | $0.11 | 99.5% |
| **Sonnet 5 (current default)** | `claude-sonnet-5` | **3.00** | **15.00** | **$0.34** | **98.6%** |
| Opus 5 | `claude-opus-5` | 5.00 | 25.00 | $0.57 | 97.7% |
| Fable 5 | `claude-fable-5` | 10.00 | 50.00 | $1.14 | 95.4% |
| *any model not in the table* | `FALLBACK_PRICE` | *15.00* | *75.00* | *$1.71* | *93.2%* |

**These dollars are a floor, not a central estimate.** They price the smallest shape
on this page. The same arithmetic over demo-01's real 39-call shape is about 134,000
input and 13,700 output tokens, or **$0.61 on Sonnet 5** - 1.8x - and that is still one
buyer, eight photographs and a fourteen-second clip. It is an upper bound for that
shape rather than a figure: `video.py` caps an extracted frame at a 1568px long edge,
so a frame is at most as expensive as a still and usually cheaper. Multiply every
dollar figure below by 1.8 to read the page for a capture that includes a walkaround.

The last row is the deliberate fallback in `cogs.py`: an unknown model is charged at
the most expensive rate we know of, so a model swap cannot silently improve the unit
economics. The $1.71 in it is not a coincidence. It is the figure this page printed
against Opus 5 until P10, because the page was written when the price table said
$15/$75 and was never revisited when the table was fixed. A stale number is worse
than a missing one: it is precise, it is in a table, and nobody re-derives it.

**Cannot be reproduced from a fixture run.** An earlier version of this section said
to run `cli inspect --fixture demo-01` for "the same token accounting". A fixture run
prints zero input tokens, zero output tokens, and `$0.0000` - correctly, because
nothing was sent and nothing was billed (LAW 5). The token counts above come from the
image-token arithmetic in `client.py` and the prompt files; `CostMeter` records a
`projected_image_tokens` figure on the live path only, and does not print it or put
it in the report, so today there is no run of any kind that emits the numbers this
projection is built on.

### What this changes

The $5 ceiling from D-006 is not close to binding. Every model we would consider
clears it by a wide margin, and even Fable 5 leaves 95% gross margin.

**That is an argument against the reasoning behind the current default.** Sonnet 5
was chosen partly on cost, and this calculation says cost should not have been a
factor: a $0.23 difference per report between Sonnet 5 and Opus 5 is not what decides
this product. The model choice is an accuracy question and it belongs to the eval,
not to this page. When a labeled set exists, both get scored on it and the more
accurate one wins unless it is dramatically more expensive, which it is not. See
D-023.

The gap was $1.37 when this page believed Opus cost $1.71, and the argument was
already that the gap did not matter. Correcting the price made a weak argument
weaker, which is the direction that costs us nothing to admit.

The real cost risk is not the model. It is **the free teaser**: inference we pay for
on reports nobody buys. At a 10% conversion rate, ten teasers at $0.34 make the true
cost of one paid report $3.40 rather than $0.34 - a tenfold difference that no model
choice comes close to. That line is already in the measurement list below, and it is
the one to watch.

## The teaser costs full price - P4

The teaser is a projection of a finished report, so every engine has already run by
the time anyone sees the free page. **A teaser costs the same as the report it is
teasing.** That is a deliberate choice, not an oversight - see D-034. Running a
cheap subset for the teaser would make the free red-flag score change after
payment, and there is no honest way to present that.

So conversion rate multiplies inference cost directly. Each row below is
`teasers x $0.3423`, the unrounded Sonnet 5 figure from the table above, with teasers
rounded up to the whole run somebody actually pays for - the 1.5% row used to be
computed on 66.67 teasers while printing 67, which understated it by twelve cents:

| Conversion | Teasers per sale | Inference per paid report | Gross margin on $25 |
|---|---|---|---|
| 50% | 2 | $0.68 | 97.3% |
| 20% | 5 | $1.71 | 93.2% |
| **10%** | **10** | **$3.42** | **86.3%** |
| 5% | 20 | $6.85 | 72.6% |
| 2% | 50 | $17.12 | 31.5% |
| 1.5% | 67 | $22.93 | 8.3% |

Two things fall out of that table.

**The $5 inference ceiling from D-006 binds on conversion, not on the model.** At
Sonnet pricing it is crossed somewhere between 5% and 10% conversion. That is the
number to instrument first, and it is why cost-per-*paid*-report, not
cost-per-report, is the line that matters.

**Below roughly 1.5% conversion the product does not work at this price**, whatever
model it runs on. The responses are a cheaper teaser stage, a higher price, or
fewer teasers - and the first of those is the one D-034 rules out on honesty
grounds, so it would need a different design rather than a switch.

These are projections built on a projected per-report cost. Both halves get
replaced by measurement the moment there is a live run and a real funnel.

## Fixed costs (monthly, assumption)

| Item | Assumption |
|---|---|
| Vercel | $0 hobby -> $20 pro when needed |
| Worker host | ~$5-20 small instance |
| Neon Postgres | $0 free tier at this volume |
| Object storage | ~$5 |
| Domain | ~$15/yr |
| Stripe | 2.9% + $0.30 per transaction |

## Break-even framing

At $25 with Stripe fees (2.9% + $0.30 = $1.03), net is $23.98 per report before
inference. The interesting
question is not break-even on fixed costs (trivially low) but **cost per report at
quality**, because the temptation will be to cut passes to protect margin. That
tradeoff is a LAW 4 question, not a finance question: a cheaper report that misses
rust is not a cheaper report, it is a different and worse product.

## What gets measured, from the first live run

This list was headed "starting P2". P2 came and went, and so did seven more phases,
without a live run to measure. The list is unchanged because it is still the right
list; only the date on it was ever wrong.

- $/report, p50 and p95 (p95 matters - a 40-photo listing is not the average one)
- $/report split by engine
- Cost of a `cannot_determine` report (we still pay for the passes)
- Refund rate and its dollar impact
- Cost per *paid* report including the free teasers that did not convert - the real
  number, since teasers are inference we pay for and do not bill

That last line is the one most likely to be uncomfortable. It gets its own row here
from the first teaser onward.
