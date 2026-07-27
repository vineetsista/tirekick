# PHASE 5 - PRICE, AND KNOWING WHEN NOT TO

Tag: `v0.6` | Branch: `main` | 37 commits | 185 tracked files
Gates: 9/9 green, locally and in CI. 350 tests.

**Gate met.** The pricing engine now has the same property every other engine in
this project has: it can decline to answer.

**0 of 16 finding types are enabled for a paid report. Sixth phase running.**

---

## 1. What shipped

The pricing engine could always do the arithmetic. That was the problem. Three
listings for a Honda Civic, or two listings for anything at all, produced a dollar
range formatted identically to one built from twenty relevant comps. Nothing in
the output distinguished them, and the buyer had no way to tell.

Three refusals, all of them subtractions from what the engine will say:

**Listings for a different car are excluded, visibly.** More than two model years
away, or a different make or model than the VIN decoded to. The exclusion and its
reason are rendered in the report, because a comp silently dropped is a comp the
buyer believes was counted.

**Below three usable listings there is no verdict.** `cannot_determine`, no range,
and the listings still shown - they are the buyer's own research, and declining to
price them is not a reason to hide them.

**Listings that disagree by more than 40% are called out** as evidence that the
listings are not comparable, rather than evidence the car is worth anything inside
the range.

Comps also gained a date. Used-car prices have moved by tens of percent inside
single years, so a range built from spring listings against an autumn market is
wrong in a way no amount of arithmetic reveals.

---

## 2. Decisions (D-035, D-036)

- **D-035** The pricing engine can decline to price.
- **D-036** Comps carry a date, and a future date is an error.

---

## 3. Real measurements

| | |
|---|---|
| Gates | 9/9 green, local and CI |
| Tests | 350 (270 pytest / 61 web / 14 shared / 5 db) |
| New pricing tests | 24, most of them about refusing |
| Comps in the demo fixture | 5, of which **1 is excluded on every run** |
| Finding types enabled for a paid report | **0** |

**The interesting bug was found by the fixture, not by design.**

Fixture mode freezes its clock at 2026-01-01 (D-011). I dated the demo comps in
July 2026, which made them *negative* days old - and a negative age passes any
"older than 90 days" check silently. The staleness warning was correct and never
fired, and it would have gone on never firing.

A listing dated after the report is a paste error, and it now says so. Two of this
project's own guarantees interacting badly is a better argument for the frozen
clock than any test I would have thought to write.

**Also worth noting:** the demo report now shows zero deductions and says why.
D-024 stopped the model inventing repair cost bands, so live reports have none at
all. An unexplained absence of deductions reads as "nothing needs fixing", which
is the opposite of true, so the notes now state that TIREKICK does not invent cost
bands and none of these findings carries a sourced one.

---

## 4. Gaps

1. **Repair cost bands have no source.** This is now the biggest hole in the price
   check: the deduction machinery works and there is nothing to feed it. A real
   source means a parts-and-labour database or regional shop rates, and both are
   licensing questions rather than engineering ones. Until then the price check
   compares listings and deducts nothing.
2. **The range is still the observed spread of a handful of listings.** With three
   comps it is fragile by construction. The wide-spread note helps; it is not a
   confidence interval and the copy says so.
3. **No upload, no persistence, no enforced paywall** - carried from P4, and still
   the largest unbuilt surface.
4. **No API key. No labelled photographs. No deploy.** Sixth phase asking. Nothing
   in this project has seen a real car.

---

## 5. YOUR 2 HOURS

### Read (30 min)

1. `packages/engines/src/tirekick_engines/engines/pricing.py:116` (`_relevance_problem`)
   and `:187` (`_spread_note`) - **10 min**.
2. `packages/engines/tests/test_pricing_limits.py` - **10 min**. It is mostly a
   list of things the engine refuses to say.
3. `DECISIONS.md` D-035, D-036 - **10 min**.

### Drill (20 min)

1. **You paste four listings and get "cannot determine". Why, and what would fix
   it?** `pricing.py:47`.
2. **One of your listings does not appear in the range. How do you find out
   which, and why?** The `excluded` block in the price section.
3. **The demo shows no deductions. Is that good news?** `pricing.py`, the last
   note. Then D-024.
4. **A comp dated next year is treated how?** And which of this project's own
   rules made that bug invisible until now?

### FOUNDER REPS

**Unchanged from P4, and I am not going to pad them.** The three that matter are
the API key, one car photographed, and the Vercel deploy. Everything I build until
those land is a machine nobody has pointed at a car.

---

## 6. NEXT - P6: WHAT A STRANGER SEES

The landing page, the demo, and the accuracy page are the only three surfaces a
stranger will ever look at before deciding whether this is worth $25. All three
exist; none has been written as though someone hostile were reading it.

That is P6, and it is the last phase that can be done without your three reps.
