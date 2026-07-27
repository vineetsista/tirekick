# TIREKICK

**An AI pre-purchase analysis for used cars.**

You give it the listing photos, a 30-second engine clip, the VIN, any paperwork you
have, and a few comparable listings you found yourself. It gives you back an
evidence-annotated dossier: what it can see, where it saw it, how sure it is, what it
cannot determine, what to ask the seller, and what a mechanic still has to check.

It is not an inspection. It never clears brakes, airbags, frame, or steering - those
are hard-locked to "independent mechanic required" in code. See
[docs/LIABILITY.md](docs/LIABILITY.md).

---

## The laws

Seven of them, in [docs/LAWS.md](docs/LAWS.md). The short version: every finding cites
visible evidence; safety-critical systems are never cleared remotely; no scraping;
nothing ships to a paid report before it clears its precision gate; every run prints
its cost; we name the AI and link our own accuracy page; gates stay green.

## Layout

```
apps/web           upload flow, report viewer, share pages, paywall (Next.js 15)
packages/shared    zod contracts - the schema the web app trusts
packages/db        Drizzle schema (Neon Postgres)
packages/engines   vision / audio / data / pricing / dossier (Python 3.12)
bench/             eval harness, labeled sets, accuracy + cost reports
docs/              LAWS, LIABILITY, ACCURACY, EVAL, BRAND, UNIT_ECONOMICS
phase_reports/     what shipped each phase
DECISIONS.md       every judgment call made without asking
```

## Quickstart

```bash
pnpm install
pnpm run py:setup          # creates packages/engines/.venv, installs deps
pnpm run inspect:fixture   # end-to-end fixture inspection, no API key needed
pnpm --filter web dev      # report viewer at localhost:3000
```

`pnpm run gates` runs everything CI runs.

## Fixture mode

The default mode is `fixture`: cached model responses, deterministic output, $0.00
cost, no API key. CI runs this way on purpose - a fork with no secrets gets a green
build. Live calls require `TIREKICK_MODE=live` and an `ANTHROPIC_API_KEY`, and the
mode is printed on every run and stamped into every report.

The fixture media is **synthetic** - generated images and a synthesised engine-like
signal, not photographs or recordings of any vehicle. The one exception is the vehicle
record, which is real federal data for a documentation VIN carrying real manufacturer
codes and an invented serial, so it decodes to a real model and identifies nobody. See
[fixtures/PROVENANCE.md](fixtures/PROVENANCE.md).

## Status

**Through P5.** Six phases, 350 tests, nine gates green.

| | |
|---|---|
| Finding types the engines can produce | 16 |
| Finding types with a measured accuracy | **0** |
| Finding types enabled for a paid report | **0** |
| Real vehicles this has ever seen | **0** |
| Live model calls ever made | **0** |

That table is the honest summary of this project and it is deliberately the first
thing in the status section. Everything built so far is a careful machine that has
never been pointed at a car. It cannot legitimately sell a single finding, and
[docs/ACCURACY.md](docs/ACCURACY.md) says so in its first line rather than waiting
until there is something flattering to put there.

What exists: a vision engine with versioned prompts and a live path, a data engine on
real NHTSA records, an audio engine that draws a spectrogram and makes no claims, a
pricing engine that can decline to price, an eval harness with nothing in it, a free
teaser that is a real projection rather than hidden HTML, and a purchase flow that
states all of the above before asking for money.

What does not: upload, persistence, an enforced paywall, and any measurement at all.
Those are in [phase_reports/PHASE_5.md](phase_reports/PHASE_5.md) under gaps.

## Reading this repository

If you read three files, read these:

1. **[DECISIONS.md](DECISIONS.md)** - every judgment call made without asking, with
   what it cost. Thirty-six of them. Several retract earlier ones.
2. **[docs/LAWS.md](docs/LAWS.md)** - the seven rules, and the file and test that
   enforces each. A law in a markdown file is a suggestion.
3. **The latest [phase_reports/](phase_reports/)** - what shipped, what was measured,
   and what is still missing, per phase. The gaps section is the useful part.
