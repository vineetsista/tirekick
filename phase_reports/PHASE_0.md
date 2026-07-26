# PHASE 0 - SCAFFOLD + LAWS

Tag: `v0.1` | Branch: `main` | 11 commits | 107 tracked files

---

## 1. WHAT SHIPPED

**The repo.** pnpm + turborepo monorepo at `~/projects/tirekick` in the WSL2 ext4
filesystem. `apps/web` (Next.js 15, TS strict), `packages/shared` (zod contract),
`packages/db` (drizzle schema), `packages/engines` (Python 3.12), `fixtures/`,
`bench/`, `docs/`.

**The laws, as code.** `docs/LAWS.md` names the file and the test enforcing each
one. The mechanized ones:

| Law | Mechanism | Where |
| --- | --- | --- |
| 1 TRUTH | Pydantic validator refuses evidence-free findings | `models.py` |
| 2 SAFETY | Post-pipeline clamp, not a prompt instruction | `safety.py:90` |
| 4 EVAL GATE | Registry gate table; unmeasured types cannot ship paid | `registry.py:180` |
| 5 COGS | Cost meter prints on every run | `cogs.py:93` |
| 6 AI-NATIVE | Banned-language scan over copy and prompts | `test_liability_copy.py` |
| 7 CI | Nine gates, one script, no API key | `scripts/gates.sh` |

**The disclaimer architecture.** `docs/LIABILITY.md` (10 KB) - what we claim, what
we refuse to claim, and where each disclaimer renders. The banner is above the
verdict and is not dismissible.

**The fixture pipeline.** `pnpm inspect:fixture` runs a full inspection end to end
from committed synthetic media and cached responses, with no API key, and writes a
golden report that the test suite holds byte-stable.

**The dossier viewer.** `apps/web` renders that report: annotated overlays with
severity-coloured boxes and confidence labels, coverage above the verdict, systems
table with the four locked rows, price check with its comps, seller questions,
negotiation script.

**Closed this session** (the previous session stopped mid-flight): `apps/web` was
untracked with zero tests, `.github/workflows/` was an empty directory, and
`scripts/gates.sh` was referenced by `package.json` but did not exist. All three
are now real. The fixture clock is frozen so the golden report stops churning.

---

## 2. DECISIONS

D-001 through D-010 were logged previously. New this session:

- **D-011 - Fixture mode freezes its own clock.** `generated_at` came from the wall
  clock, so every run rewrote the committed golden and the tree was never clean. A
  reproducibility guarantee that depends on remembering a flag is not one.
- **D-012 - Cost renders at the bottom of the dossier, present but terminal.** LAW 5
  requires the number be visible; putting it near the verdict invites the buyer to
  price the analysis instead of reading it.

---

## 3. REAL MEASUREMENTS

Not estimates. Every number below came off a run in this session.

**Gates** - 9/9 green (`bash scripts/gates.sh`):

```
py:lint  py:types  py:test  inspect:fixture  contract:check
ts:typecheck  ts:test  ts:build  fixture:clean
```

**Tests** - 113 total:

| Suite | Tests |
| --- | --- |
| `packages/engines` (pytest) | 62 |
| `packages/shared` (vitest) | 14 |
| `packages/db` (vitest) | 5 |
| `apps/web` (vitest) | 32 |

**The fixture report** (`fixtures/reports/demo-01.report.json`):

| Metric | Value |
| --- | --- |
| Findings | 8 |
| Mechanic referrals | 2 |
| Red-flag score | 62/100 |
| Media coverage | 67% |
| Safety clamp events | 3 (2 converted to referrals, 1 dropped) |

The clamp log from that run, verbatim:

```
LAW 2: converted 'vf_bay_02' (brakes, severity=major) to a mechanic referral
LAW 2: dropped 'vf_bay_03' (brakes, severity=info, confidence=0.96)
LAW 2: converted 'recall_FIX000001' (restraints, severity=major) to a referral
```

`vf_bay_03` is the adversarial fixture: a high-confidence *all-clear* on brakes.
It does not reach the report. `vf_bay_02` is an adverse brake observation and it
survives, stripped of severity and confidence. That asymmetry is the whole of D-005
and it is now demonstrated on the real artifact, not asserted in prose.

**Cost of one report** (LAW 5):

| | |
| --- | --- |
| Mode | fixture |
| Input / output tokens | 0 / 0 |
| Images analyzed | 18 |
| Audio processed | 22.0 s |
| Storage | 2.9 MB |
| **Total** | **$0.0000** |

$0.00 is the honest cost of a cached run, not a placeholder. It is also not
informative about live cost, which remains unmeasured - see gaps.

**Eval gate** - 15 finding types registered, **0 measured, 0 enabled for paid
reports.** This is the correct state under LAW 4 and it is worth staring at: today
TIREKICK cannot legitimately sell a single finding type. P2 is what changes that.

**Web build** - 4 static routes, 105 kB shared First Load JS, 1m11s cold build.

---

## 4. GAPS - WHAT IS NOT TRUE YET

1. **"Skeleton deployed" is NOT met.** No GitHub remote, no Vercel project. Both
   need your accounts; see FOUNDER REPS. This is the one P0 gate item outstanding
   and I did not do it unilaterally because both are outward-facing.
2. **No live model call has ever run in this repo.** Fixture mode is the default,
   no `ANTHROPIC_API_KEY` is present, and the `live` path is therefore exercised by
   exactly zero tests. The first live run will find bugs. Budget for that in P2.
3. **The vision engine drafts nothing on its own.** Every "finding" in the fixture
   comes from a hand-authored cached response. The pipeline shape is proven; the
   engine's judgment is entirely unproven.
4. **No database exists.** `packages/db` defines the drizzle schema and the enum
   parity test passes, but no Neon instance is provisioned and no migration has run.
   Nothing persists between runs yet.
5. **The audio engine is deliberately silent.** It reports zero findings and states
   that it does not analyze engine audio (P3). Silence is the correct output, not a
   stub - but do not mistake it for a working engine.
6. **The fixture media is synthetic** and labeled so everywhere (D-010). No accuracy
   claim can ever cite it. Real media arrives with your P2 capture reps.
7. **No PDF export, no Stripe, no upload flow.** P4 and P5.

---

## 5. YOUR 2 HOURS

### Read the code (50 min, time-boxed)

Read in this order. The point is to be able to defend the safety architecture to a
skeptical mechanic and to a lawyer, in that order.

1. **`docs/LIABILITY.md`** (15 min) - the whole thing. This is the document that
   decides whether this business is sane.
2. **`packages/engines/src/tirekick_engines/safety.py`** (15 min) - start with the
   module docstring, then `apply_safety_law` at line 90. This is LAW 2 in 150 lines.
3. **`packages/engines/src/tirekick_engines/registry.py:40-180`** (10 min) - the
   finding-type registry and the gate table. Note every row currently says NO.
4. **`apps/web/src/components/Overlay.tsx:173`** (10 min) - `annotationsFor`, where
   evidence becomes a box on an image. This is LAW 1 at the pixel level.

### Assigned reading (35 min)

**"A Dealer's Guide to the Used Car Rule" - US Federal Trade Commission**
(search `ftc.gov` for the title; it is FTC business guidance on 16 CFR Part 455).

Why this one, for P0: it is the clearest existing example of *disclosure
architecture* in exactly our domain - a regulator specifying what a used-car seller
must say, how prominently, and in what words, precisely because buyers systematically
over-read reassurance. Read it as a template for how our own banner, our locked-system
rows, and our "cannot determine" states should behave. Pay attention to how the
Buyers Guide handles "as is": it does not soften the message to be friendly, and it
does not let the salesperson's verbal promises override the printed form. Our banner
has the same job against our own marketing copy.

The other four assigned readings (VLM evaluation methodology, an OCR/detection
primer, a mechanic's inspection checklist, spectrogram basics) land in P2 and P3
where they are directly actionable.

### 5 drill questions

Answer from the files. Cited so you can check yourself.

**Q1. A model returns "brakes look fine, confidence 0.96." Trace exactly what
happens to it and name the line that kills it.**
It is drafted normally, then dies in `apply_safety_law`
(`packages/engines/src/tirekick_engines/safety.py:90`) because `is_locked("brakes")`
(`safety.py:64`) is true and the draft carries a non-adverse verdict. Proven on the
real artifact by `test_the_fabricated_all_clear_never_reaches_the_report`
(`packages/engines/tests/test_pipeline.py:54`). The prompt also says not to do this -
that is defense in depth, not the guarantee (D-004).

**Q2. Why does an adverse brake observation survive when the all-clear does not?**
D-005. Warning a buyer is not the same as clearing one. It survives as a
`MechanicReferral` with its evidence intact but stripped of severity and confidence.
The UI enforces the same asymmetry: referral boxes are drawn in `--tk-locked` with a
label that carries no number (`apps/web/src/components/Overlay.tsx:196-207`), and
`Overlay.test.tsx` asserts no referral label anywhere in the report matches `/\d/`.

**Q3. If a `Finding` gains a field in Python, what breaks and where?**
Nothing at authoring time - the contract is dual-defined on purpose (D-002). It
breaks in `contract:check`, which runs the fixture inspection in Python and validates
the emitted JSON against the zod schema (`packages/shared/src/schema.ts:151`). It
would also break `parseReport` at `apps/web/src/lib/report.ts:9`, which parses at
module scope so the web build fails rather than the viewer rendering something
malformed.

**Q4. Why does a fixture report say it was generated on 2026-01-01?**
D-011. Fixture mode freezes its clock at `FIXTURE_GENERATED_AT`
(`packages/engines/src/tirekick_engines/dossier.py:66`, applied at
`_default_generated_at`, line 69). A cached run has no meaningful generation time,
and stamping a live one made the golden report churn on every run so that no
snapshot diff was ever worth reading.

**Q5. Today, which finding types may appear in a paid report?**
None. All 15 rows in `gate_status_table` (`registry.py:180`) read `not measured / 0 /
NO`. LAW 4 forbids shipping an unmeasured type, and no labeled eval set exists yet.
The gate table prints on every run so this stays uncomfortable rather than forgotten.

---

## 6. FOUNDER REPS (25 min)

### REP 1 - Create the GitHub repo (5 min)

`gh` is installed on Windows but not in WSL, and I am not creating a public repo on
your account without you saying so. Decide public or private, then run in WSL:

```bash
sudo apt install gh -y && gh auth login
cd ~/projects/tirekick
gh repo create vineetsista/tirekick --private --source=. --remote=origin --push
```

Swap `--private` for `--public` if you want the build in the open from commit one.
There is a real argument for public: the accuracy page and the laws are the product's
differentiator, and a public repo is evidence you meant them.

### REP 2 - Sign off on the banner (10 min)

Every report renders this above the verdict, non-dismissible. It is in
`packages/shared/src/constants.ts:26` and duplicated in the Python models. Read it as
a nervous buyer, then as an opposing lawyer:

> Automated analysis of media you provided. This is not an inspection, a
> certification, or a warranty. Confidence is not certainty. Have an independent
> mechanic examine any vehicle before you buy it.

Two questions to answer: does it survive being screenshotted without the rest of the
page, and does anything elsewhere in the product contradict it? If yes to the second,
that copy is the bug, not the banner.

### REP 3 - Line up three cars for P2 (10 min)

P2 needs >=150 labeled images and they start with cars you can walk to. Identify
three - yours plus two family - and send this. Pre-drafted, send as is:

> Hey - I'm building a tool that inspects used cars from photos, and I need real
> photos to test it against. Can I spend 15 minutes photographing your car this week?
> Nothing invasive, just a walkaround plus the dash and tires. I'll send you back the
> report it generates - you'll probably learn something about your own car.

Do not photograph anything yet. The capture guide ships in P2 and shooting to the
wrong spec means shooting twice.

---

## 7. NEXT

P1 - DATA ENGINE. VIN decode and build data via vPIC, open recalls via NHTSA,
complaint-pattern summary, title-brand keyword checks from user-supplied history
docs. All cached, all cited. Gate: golden tests on 5 real VINs, cited sections
rendering in the report.

The federal APIs are free and need no key, so P1 is the last phase that can be built
end to end without spending a cent - and the first one where the report contains a
fact about a real vehicle. vPIC connectivity is already confirmed working from this
machine (HTTP 200).
