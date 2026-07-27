# PHASE 4 - TEASER, DISCLOSURE, CHECKOUT

Tag: `v0.5` | Branch: `main` | 35 commits | 183 tracked files
Remote: `github.com/vineetsista/tirekick` (private - D-013, D-022)
Gates: 9/9 green, locally and in CI. 326 tests.

**Gate PARTIALLY met, and I want to be precise about which part.**

The free/paid boundary is built and it is honest: a real server-side projection,
a disclosure flow that meets LIABILITY section 4, and a checkout that states what
has actually been measured before it asks for money.

What is *not* built is the half that needs infrastructure I do not have: file
upload to object storage, a database to persist an inspection, and a Stripe
webhook to mark one paid. Those need a Neon connection string, a bucket, and
Stripe keys. All three are founder reps.

**0 of 16 finding types are enabled for a paid report. Fifth phase running.**

---

## 1. What shipped

**The teaser as a projection** (`teaser.py`). 6.1KB against the report's 48.7KB.
Nothing omitted was ever serialised.

**The teaser page** (`/teaser/demo-01`). Coverage first, then the limits, then the
score, then the price - deliberately not the conversion-optimal order.

**The purchase gate** (`/buy/demo-01`). Three acknowledgements, unticked, and no
payment control rendered at all until all three are ticked.

**`accuracy_statement()`**, generated from the eval-gate registry and rendered
above the payment button. Today it says nothing has been measured.

**Checkout plumbing** that degrades honestly: an unconfigured Stripe link renders
a panel saying so, never a dead href.

---

## 2. Decisions (D-031 .. D-034, full text in DECISIONS.md)

- **D-031** The teaser is a projection, not a redaction.
- **D-032** The checkout page states how much of the product is measured.
- **D-033** The pay button does not exist until the acknowledgements are ticked.
- **D-034** The teaser costs the same to produce as the report it is teasing.

**D-032 is the one to argue with me about.** It will cost conversions.

---

## 3. Real measurements

| | |
|---|---|
| Gates | 9/9 green, local and CI |
| Tests | 326 (246 pytest / 61 web / 14 shared / 5 db) |
| Teaser payload | **6.1 KB** vs report **48.7 KB** |
| Finding titles leaked into the teaser | **0** |
| Paid-only keys present in the teaser | **0** |
| Payment controls before acknowledgement | **0** |
| Finding types enabled for a paid report | **0** |

**The teaser costs full price.** It is a projection of a finished report, so every
engine has already run before anyone sees the free page. Conversion rate therefore
multiplies inference cost directly, and `docs/UNIT_ECONOMICS.md` now carries the
table:

| Conversion | Inference per paid report | Margin on $25 |
|---|---|---|
| 20% | $1.71 | 93.2% |
| **10%** | **$3.42** | **86.3%** |
| 5% | $6.84 | 72.6% |
| 1.5% | $22.81 | 8.8% |

The $5 ceiling from D-006 binds on **conversion**, not on the model - it is crossed
somewhere between 5% and 10%. Below about 1.5% the product does not work at this
price on any model.

I considered running a cheap subset for the teaser and the rest on payment. It
would fix the economics and I rejected it: the free page shows a red-flag score,
and a score computed on partial analysis changes after payment. A buyer who sees
50/100 free and 72/100 after paying has been baited, and the version where the
number goes *down* is worse. D-034.

---

## 4. Gaps

**The four that are mine:**

1. **No upload flow.** There is no way for a stranger to give TIREKICK a car. The
   report and teaser render from a committed fixture. This needs object storage
   (a bucket + signed URLs) and it is the largest single piece of unbuilt product.
2. **No persistence.** `packages/db` has a full Drizzle schema and no database
   behind it. Nothing is written anywhere. An inspection exists only as a
   directory on this machine.
3. **No fulfilment.** A Stripe payment link can be clicked; nothing listens for
   the webhook, so nothing marks an inspection paid or emails a report. The
   `/report` route is currently public.
4. **The paywall is not enforced server-side.** `/report/demo-01` is a static
   route with no check on it. The *projection* is correct - the teaser genuinely
   does not contain the paid content - but the paid page is not gated, because
   there is nothing to gate it against yet. That is the next thing to build after
   persistence, and it must not ship to a paying customer before it exists.

**The five carried forward, all still blocked on you:**

5. **No API key.** Fifth phase asking. The live path has still never run.
6. **No labelled photographs**, so nothing measured, so nothing legitimately
   sellable. This is still the only gap that matters.
7. **No Vercel deploy.** Fifth phase asking.
8. A prompt change still does not invalidate cached responses (P2).
9. `min_n = 50` is still a judgment, not a derivation (P1).

---

## 5. YOUR 2 HOURS

### Read, in this order (40 min)

1. `packages/engines/src/tirekick_engines/teaser.py`, the module docstring -
   **10 min**. It explains what is free and why, and the "why" is the part I most
   want challenged.
2. `apps/web/src/components/PurchaseGate.tsx`, the three acknowledgements -
   **10 min**. Read them as a customer who is about to lose $25.
3. `DECISIONS.md` D-032 and D-034 - **10 min**.
4. Click through it - **10 min**:
   ```
   pnpm --filter web dev
   # /teaser/demo-01  ->  /buy/demo-01
   ```
   Then open the network tab on the teaser page and confirm the findings are not
   in the payload. That is the claim; check it rather than believing it.

### Assigned reading (30 min)

**The FTC's guidance on substantiation of advertising claims.** Search
`FTC Policy Statement Regarding Advertising Substantiation` - it is a short primer
and it is directly load-bearing for D-032.

The principle is that a claim must be substantiated *before* it is made, not
defended afterwards. Read `accuracy_statement()` against it. My reading is that a
report which says "rust detected, confidence 0.72" without a measured precision
behind it is an unsubstantiated claim dressed as a measurement, and that the
sentence on the checkout page is the minimum honest response - but I would rather
you form your own view than inherit mine, because you are the one whose name is
on the company.

### Drill - answer from the code (40 min)

1. **Open the teaser JSON. Where are the findings?**
   `teaser.py:130`. Then: why does `parseTeaser` in `packages/shared/src/schema.ts`
   throw on extra keys rather than letting zod strip them?

2. **A buyer sees 14 findings for free and pays. How do we know the number will
   not change?**
   D-034. What would have to be true for it to change, and why was that rejected?

3. **The systems table appears on both pages. What is different about it?**
   `teaser.py:50`, and the four rows that are byte-identical in both.

4. **Why is there no greyed-out pay button?**
   `PurchaseGate.tsx:159`, `docs/LIABILITY.md` section 4, last line.

5. **The accuracy statement says nothing has been measured. Where does that
   sentence come from, and what happens to it when rust clears its gate?**
   `teaser.py:66`, and the test that patches the registry to prove it changes.

---

## 6. FOUNDER REPS (~35 min)

### REP 1 - Deploy (10 min) - fifth ask

Unchanged. `apps/web`, `pnpm --filter web run build`, Next.js, no env vars.

Once it is up, `/teaser/demo-01` is the first thing in this project that a
stranger could form an opinion about.

### REP 2 - The API key (5 min) - third ask

`.env`, `ANTHROPIC_API_KEY=...`, low cap.

### REP 3 - Three accounts, so P5 has something to build against (20 min)

All three are free to start and none needs a card except Stripe.

- **Neon** (neon.tech) - create a project, copy the pooled connection string into
  `.env` as `DATABASE_URL`. The Drizzle schema has been waiting since P0.
- **Object storage** - Vercel Blob is the least work given the deploy; Cloudflare
  R2 is cheaper at volume. Either way put the token in `.env`.
- **Stripe** (test mode) - create one product at $25, make a payment link, put the
  URL in `.env` as `NEXT_PUBLIC_STRIPE_PAYMENT_LINK`. Test mode is enough; do not
  enable live payments until the paywall is actually enforced, which it is not.

**Do not take real money yet.** Gap 4 above says the paid route is ungated, and
gap 6 says nothing has measured accuracy. Either alone is a reason to wait.

---

## 7. NEXT - P5: PRICE, AND THE PARTS THAT MAKE IT A PRODUCT

The pricing engine exists from P0 and has never been examined closely: it fits a
line through user-pasted comps and deducts against findings. P5 is where it gets
the same treatment the data engine got in P1 - specifically, what happens when the
comps are thin, mismatched, or three months stale, because "cannot determine" has
to be as available here as everywhere else.

Then the remaining product surface: upload, persistence, and a paywall that is
actually enforced.

**A standing note, and it is the reason I keep putting REP 2 first.** Five phases
have built a careful machine that has never seen a real car. Every number in every
phase report is about plumbing. The first photograph of a real vehicle will
falsify something, and I would rather that happened at phase five than at phase
nine.
