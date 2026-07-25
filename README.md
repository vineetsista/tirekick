# TIREKICK

**An AI pre-purchase analysis for used cars.**

You give it the listing photos, a walkaround video, a 30-second engine clip, the VIN,
and a few comparable listings. It gives you back an evidence-annotated dossier: what
it can see, where it saw it, how sure it is, what it cannot determine, what to ask the
seller, and what a mechanic still has to check.

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

The P0 fixture media is **synthetic** - generated images and a synthesized tone, not
photographs of any vehicle. See [fixtures/PROVENANCE.md](fixtures/PROVENANCE.md). It
exercises the pipeline. It is not evidence about a car and no accuracy claim will ever
cite it.

## Status

**P0 - scaffold and laws.** No accuracy numbers exist yet, which is why
[docs/ACCURACY.md](docs/ACCURACY.md) currently says so in the first line.
