# PHASE 6 - WHAT A STRANGER SEES

Tag: `v0.7` | Branch: `main` | 39 commits | 187 tracked files
Gates: 9/9 green, locally and in CI. 362 tests. 38 decisions logged.

**Gate met**, and it found the worst honesty bug in the project.

---

## 1. The thing worth reading this report for

The P0 landing page said TIREKICK gives you back **"the open recalls on that VIN"**.

In P1 I established that NHTSA publishes recall campaigns per model and publishes
nothing at all about individual vehicles. I wrote D-016 about it. I added *three*
separate caveats to the report - above the recall list, inside every recall
finding, and in the seller question - and a test asserting the wording on all five
golden VINs.

And then I left the front page promising the exact thing the report had just been
rewritten to refuse. For four phases. It also advertised walkaround video
analysis, which has never existed in any phase of this project.

Nothing failed, because nothing looked. The banned-language scan checks for
forbidden *phrases* - it cannot notice a sentence that is well-written, plausible,
and no longer true. **Marketing copy drifts silently and always in the same
direction.**

The fix is `Marketing.test.tsx`: it renders the landing page and asserts against
the current product. No per-VIN recall claim. No title search. No audio diagnosis.
No features that do not exist. No clearance language. And the positive half
asserted on *position* rather than presence, because a disclaimer under the button
is not a disclaimer.

I would rather have found this than shipped it. I would rather still have not
written it.

---

## 2. What else shipped

**The accuracy statement is now on three surfaces from one generated source** -
landing page, teaser, checkout. It reads: *none of the 16 finding types has cleared
its accuracy threshold yet - 0 have been measured at all.* Above the fold on all
three.

**A section called "What the report will not do"**, with five entries, on the
landing page rather than in a terms link.

**The README** now opens its status section with a table whose interesting rows are
all zero.

---

## 3. Decisions (D-037, D-038)

- **D-037** The landing page is scanned against the product, not just for banned words.
- **D-038** The banned-language exemption excuses files by role, never by sentence.

D-038 is small but worth the paragraph: the new copy test names "certified" in
order to assert its absence, so the scan caught it - the same shape as P2, where
the scan caught the prompts I had just written to forbid those words. Test files
are now exempt by suffix, and there is a test asserting the exemption never
swallows a component or a page. A guard on the guard, because an exemption list is
the obvious place to hide a real violation.

---

## 4. Where the project actually stands

| | |
|---|---|
| Phases | 6 (P0-P5 plus this) |
| Tests | 362 |
| Gates | 9/9 green, local and CI |
| Decisions logged | 38 |
| Finding types the engines can produce | 16 |
| **Finding types with a measured accuracy** | **0** |
| **Finding types enabled for a paid report** | **0** |
| **Real vehicles this has ever seen** | **0** |
| **Live model calls ever made** | **0** |

Six phases have built a careful machine that has never been pointed at a car.

Everything measured in every phase report is about plumbing: that the clamp fires,
that the paywall holds, that a spectrogram renders, that a range is not produced
from two listings for a Civic. All of it is necessary and none of it is evidence
that this product works.

---

## 5. What is left, in the order it matters

**1. The three reps.** An API key, one car photographed, a Vercel deploy. Sixth
phase asking. Everything below is blocked on the first two.

**2. Run the vision engine live and label the output.** The first real photograph
will falsify something. Better now than at phase nine.

**3. Measure, and publish the misses.** `bench/` is built, tested and empty. The
moment it has numbers, `docs/ACCURACY.md` and the gate table and the three
accuracy statements all change together, because they read from one file.

**4. Upload, persistence, enforced paywall.** The largest unbuilt surface. Needs a
database, a bucket, and Stripe keys. **The paid route is currently ungated** - that
is gap 4 in `phase_reports/PHASE_4.md` and it must be fixed before any real money.

**5. Repair cost bands.** The price check deducts nothing because nothing has a
sourced cost. That is a licensing question, not an engineering one.

---

## 6. YOUR 2 HOURS

### Read (35 min)

1. **`README.md`, the status table** - 5 min. Four zeros.
2. **`apps/web/src/components/Marketing.test.tsx`** - 10 min. Read it as the audit
   it is, and add anything you would want a customer to be able to hold us to.
3. **`DECISIONS.md`, skim all 38** - 20 min. Read D-016, D-023, D-027, D-032 and
   D-037 properly. Three of them retract or undercut an earlier decision of mine.

### Assigned reading (25 min)

**Your own landing page, at `/`, out loud, to somebody who is not you.**

Not a link this time. Every reading assigned so far has been about a discipline
this project already applies to itself. This one is the test that four phases of
testing did not catch: read the page aloud, and stop at every sentence you could
not defend to somebody who paid $25 and feels cheated.

That is exactly the check that would have caught the VIN recall claim in P1, and
no amount of test coverage substituted for it.

### FOUNDER REPS

**Unchanged, and I am not going to invent new ones.**

1. **Vercel deploy.** `apps/web`, `pnpm --filter web run build`, no env vars.
2. **API key** in `.env`, low cap.
3. **One car**: eight photographs per `bench/README.md`, thirty seconds of engine
   audio, and everything you know to be true written down beside it.

Rep 3 is the one that changes what this project is. Until it happens, every number
I can produce is about the machine rather than about a car.

---

## 7. NEXT

There is no P7 to define, because the next move is not mine. The build has run
ahead of the evidence by about four phases, and the correct thing to do now is
stop adding surface and start measuring what exists.

When the key and the photographs land: live vision run, label the output, run
`bench`, publish the numbers including the misses, and find out which finding types
survive their own gate. My honest expectation is that several will not, and that
the first version of `docs/ACCURACY.md` with real numbers in it will be
uncomfortable reading.

That is the phase this whole thing has been building toward, and it is the first
one that can tell you whether any of it works.
