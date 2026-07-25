# UNIT ECONOMICS

**As of P0: no real API calls have been made, so every number below is a stated
assumption, not a measurement.** Assumptions are labeled. They get replaced with
measured numbers the moment the vision engine makes its first live call (P2).

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
