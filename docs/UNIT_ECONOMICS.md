# UNIT ECONOMICS

**As of P2: still no real API calls, so there is still no measured $/report.** What
P2 adds is a *calculated* projection, which is a different and weaker thing than a
measurement, and is labeled as such everywhere it appears below.

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
| Audio | 30s clip, local ffmpeg + spectrogram, 1 model pass | assumption |
| Data engine | vPIC + recalls + complaints, cached | free federal APIs |
| Pricing | text-only, user-pasted comps | assumption |
| Dossier synthesis | 1 long-context pass | assumption |
| Storage | ~60MB media, 90 day retention | assumption |
| Egress / PDF render | negligible | assumption |

**Not estimated here on purpose:** total dollars per report. Writing a plausible-looking
$/report number before a single real call is exactly the kind of number that becomes
load-bearing and is never revisited. The `CostMeter` fills it in from measurement.

What *is* fixed: the gross-margin floor we will hold. **A report that costs more than
$5 in inference does not ship at $25.** If P2 measurement lands above that, the
response is fewer/cheaper passes or a higher price, not quiet acceptance.

## Projected inference cost per report - CALCULATED, NOT MEASURED

P2 makes this computable without spending anything. The inputs are all known: image
tokens are `width * height / 750` on images we downscale ourselves to a 1568px long
edge, the prompts are files we can count, and the routing table says exactly how
many calls an 8-photo capture makes.

An 8-photo capture produces **22 model calls**: 8 view classifications, then 14
targeted stage-2 passes. A phone photo at 4032x3024 downscales to 1568x1176, which
is **2,459 image tokens**. Adding the system prompt and the pass prompt to each
call gives roughly **75,600 input** and **7,700 output** tokens per report.

| Model | Projected inference | Margin on $25 |
|---|---|---|
| Haiku 4.5 | $0.11 | 99.5% |
| **Sonnet 5 (current default)** | **$0.34** | **98.6%** |
| Opus 5 | $1.71 | 93.2% |

Reproduce with `packages/engines/.venv/bin/python -m tirekick_engines.cli inspect
--fixture demo-01`, which prints the same token accounting for the fixture run.

### What this changes

The $5 ceiling from D-006 is not close to binding. Every model we would consider
clears it by a wide margin, and even Opus 5 leaves 93% gross margin.

**That is an argument against the reasoning behind the current default.** Sonnet 5
was chosen partly on cost, and this calculation says cost should not have been a
factor: a $1.37 difference per report is not what decides this product. The model
choice is an accuracy question and it belongs to the eval, not to this page. When a
labeled set exists, both get scored on it and the more accurate one wins unless it
is dramatically more expensive, which it is not. See D-023.

The real cost risk is not the model. It is **the free teaser**: inference we pay for
on reports nobody buys. At a 10% conversion rate, ten teasers at $0.34 make the true
cost of one paid report $3.40 rather than $0.34 - a tenfold difference that no model
choice comes close to. That line is already in the measurement list below, and it is
the one to watch.

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

At $25 with Stripe fees, net is ~$23.95 per report before inference. The interesting
question is not break-even on fixed costs (trivially low) but **cost per report at
quality**, because the temptation will be to cut passes to protect margin. That
tradeoff is a LAW 4 question, not a finance question: a cheaper report that misses
rust is not a cheaper report, it is a different and worse product.

## What gets measured, starting P2

- $/report, p50 and p95 (p95 matters - a 40-photo listing is not the average one)
- $/report split by engine
- Cost of a `cannot_determine` report (we still pay for the passes)
- Refund rate and its dollar impact
- Cost per *paid* report including the free teasers that did not convert - the real
  number, since teasers are inference we pay for and do not bill

That last line is the one most likely to be uncomfortable. It gets its own row here
from the first teaser onward.
