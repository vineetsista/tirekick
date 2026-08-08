# LIABILITY ARCHITECTURE - v1

**Status:** v1, written by the build team, **not reviewed by counsel.** Every section
marked [COUNSEL] is a question for a lawyer licensed in our operating state before we
take money from a stranger. This document is the engineering design for how the
product avoids making promises it cannot keep. It is not legal advice and it is not a
substitute for the terms of service a lawyer will write.

**Blocking rule:** the [COUNSEL] items in section 8 must be resolved before the first
paid report (P6 gate), not before launch of the free teaser.

---

## 1. What TIREKICK is

TIREKICK is an **automated analysis of media and public records that a buyer gives
us.** It produces observations, confidence levels, and questions to ask - so that a
buyer walks into a used-car purchase with better questions than they had before.

It reads photographs, a walkaround video, a short audio clip, a VIN, and comparable
listings the buyer pastes in. It cross-references federal vehicle databases. It writes
up what it saw, with the evidence attached.

## 2. What TIREKICK is not

This list is load-bearing. Each item is a thing we will be accused of being, so each
one is denied explicitly, in the product, in the buyer's words.

- **Not an inspection.** A pre-purchase inspection is a physical examination by a
  person, with the car on a lift, wheels off, scan tool plugged in. We never touch the
  car. We use the word "inspection" only in the compound product name, and the report
  itself says "remote analysis."
- **Not a certification.** Nothing we produce certifies, warrants, guarantees, or
  approves a vehicle. There is no TIREKICK pass. There is no seal a seller can put on
  a listing. (The seller-facing badge was pencilled in for P8 and locked behind
  counsel first. P8 shipped without it and the lock held - there is no badge in the
  codebase. It stays open in section 8 rather than being quietly dropped.)
- **Not a warranty or guarantee** of condition, mechanical fitness, safety,
  merchantability, or fitness for a particular purpose.
- **Not a substitute for a mechanic.** Every report tells the buyer to get one. The
  safety-critical sections tell them they have no other option.
- **Not a title/history report.** We surface federal recall and complaint data and
  read documents the buyer uploads. We are not an NMVTIS-based history provider and do
  not claim title-brand completeness. [COUNSEL: NMVTIS disclosure requirements if we
  ever summarize title brands from user-uploaded documents - see section 6.]
- **Not an appraisal.** The price section is an arithmetic comparison against
  comparables the buyer chose. It is not a valuation by a licensed appraiser.

## 3. The safety-critical lock

Brakes, airbags and restraints, frame and structure, and steering are hard-locked to
"not remotely verifiable - independent mechanic required" in code (LAW 2), regardless
of model output.

The reasoning is both ethical and legal, and the two point the same way:

1. **These are the failures that injure people.** A wrong "brakes look fine" is not a
   refund problem, it is a hospital problem. No confidence score justifies taking that
   risk on a buyer's behalf.
2. **They are genuinely unobservable in our inputs.** Pad thickness, rotor runout,
   airbag deployment history, module fault codes, frame straightness, and rack play
   cannot be read from a walkaround video. A model that appears to assess them is
   pattern-matching, not measuring. Under LAW 1 that output has no valid evidence and
   must not exist.
3. **It collapses our worst legal exposure.** The catastrophic claim against a product
   like ours is "your report told me the car was safe and it was not." We never say a
   car is safe. The lock means that sentence cannot appear in our output even if a
   model hallucinates it, and we can demonstrate that in code and in a test.

Corollary we hold to: the lock does not silence warnings. If the analysis sees
something alarming near a locked system, the buyer is told to have it examined. We can
raise an alarm; we cannot sound an all-clear.

## 4. Disclaimer architecture

Disclaimers do not work as a wall of text in a footer. They work when they appear at
the moment of the decision they qualify, in the buyer's own reading path. Ours are
placed by moment, not by page:

| Moment | Placement | Substance | Checked by |
|---|---|---|---|
| Landing page, above the fold | Body copy, not fine print | What this is: AI analysis of your photos. What it is not: a mechanic. | `Marketing.test.tsx`, against the product rather than for keywords (D-037) |
| Upload flow, before payment | Checkbox, unticked by default, own paragraph | Acknowledgement: remote analysis, not an inspection; safety systems cannot be assessed; get a mechanic before buying. | `TeaserView.test.tsx` - there is no way to pay before the boxes are ticked (D-033) |
| Report, top of page, before the verdict | Persistent banner, same type size as the verdict | Remote analysis of buyer-supplied media. Not an inspection. Confidence is not certainty. | `ReportView.test.tsx` asserts the banner precedes the red-flag score. Nothing asserts the type size. |
| Every safety-critical row | Inline, in the row itself | Not remotely verifiable - independent mechanic required. | `test_laws.py` - all four rows on every report, verbatim, no paraphrase |
| Every finding | Inline confidence bar + basis | The evidence and the confidence, adjacent to the claim. | `models.py` - `confidence_basis` and `evidence` are both required fields |
| Share page / public link | Footer + watermark | Analyzed by TIREKICK AI, plus the same "not an inspection" line. | `Marketing.test.tsx` |
| PDF export | First page and running footer | Same as report banner; survives being printed and handed to a seller. | `Marketing.test.tsx` - `position: fixed` in `@media print` is what makes it *running* |

Two of these rows were specified here and unbuilt for six phases - the share surface
and the print footer - which is why the last column exists at all (D-043). A
placement described in a table and in no test is a placement nobody has.

Design rule: **a disclaimer that a user can reach the verdict without reading has not
been placed correctly.** The banner is not dismissible.

## 5. Banned language

These phrases never appear in product copy, report output, marketing, or model
prompts. The list is not prose: it is `BANNED` in
`packages/engines/src/tirekick_engines/copy_rules.py`, and the table below is that
list transcribed. Prompts are in scope for the same reason the web copy is - a prompt
containing "inspect" teaches the model to write it back to us, and then it arrives
wearing a confidence score.

The pattern column is the regex verbatim, not a readable rendering of it, and
`packages/engines/tests/test_docs_numbers.py` compares this table to `BANNED` row for
row and in order. A prettified pattern would be the more pleasant thing to read and
the less useful thing to have: this section used to prettify, and the prettifying is
where it went wrong twice - once claiming bare "passed" was banned when it never was,
once omitting `inspected by` while the scan enforced it.

| Pattern, as the scan actually matches it | Why | Say instead |
|---|---|---|
| `\bcertif(y\|ies\|ied\|ying\|ication\|ications)\b` | We certify nothing. There is no TIREKICK pass. | analysis / analyzed |
| `\bguarantee(d\|s\|ing)?\b` | We guarantee no condition, ever. | visible in the provided media |
| `\bwarrant(y\|ies\|ed\|ing\|s)\b` | We offer no warranty of condition or fitness. | observed / not observed |
| `\b(safe to drive\|road safe\|roadworthy)\b` | We never assert a vehicle is safe. That is the claim that hurts someone. | have a mechanic verify before purchase |
| `\bclean bill of health\b` | Implies a clearance we cannot give. | no issues visible in the media provided |
| `\bpass(ed\|es) (\w+ ){0,2}inspection\b` | There is nothing to pass. We do not inspect. | analysis complete |
| `\b(we\|tirekick) inspect(s\|ed\|ing)?\b` | A person inspects. We analyze media. | TIREKICK analyzed |
| `\binspected by\b` | Passive voice does not make it true. Nobody inspected anything. | analyzed by |
| `\bno problems found\b` | Overclaims absence. Absence of evidence is not evidence of absence. | no problems visible in the media provided |
| `\bbrakes (are\|look\|appear) (fine\|good\|ok)\b` | LAW 2. A locked system is never cleared. | not remotely verifiable - independent mechanic required |

Two corrections to how this section used to read, both of which mattered:

- **`inspected by` was missing from this list entirely** while being in the scan.
  It was added in P9 after the report watermark and share footer were found reading
  `INSPECTED BY TIREKICK AI` - the exact claim this whole document denies, in the
  passive voice, on the two surfaces most likely to be forwarded to a stranger.
- **Bare "passed" is not banned and never was.** This section listed it as though it
  were. The scan bans "passed inspection" and near variants; "passed" alone appears
  in ordinary English ("the deadline passed") and banning it would have made the
  scan unusable. Likewise "brakes are fine **and any variant**" overstated it: the
  regex covers nine exact phrasings. Everything beyond those nine is caught by the
  LAW 2 clamp in `safety.py`, which drops a locked-system clearance regardless of
  wording, not by this scan. The scan is a backstop against copy we write; the clamp
  is the control against output a model generates.

**The scan is not absolute, by design.** Our own disclaimers have to be able to say
"this is not a certification", so `SANCTIONED_DISCLAIMERS` declares those sentences
verbatim and strips them before scanning. That list is short and changing it is a
change to the disclaimer architecture in section 4. Docs are outside the scanned
globs, which is why this section can print the banned phrases in order to ban them -
and also why nothing stops this file from drifting away from `copy_rules.py` again.

**Enforced in:** `packages/engines/tests/test_liability_copy.py` - the scan runs over
prompts, engine modules and web copy, with a guard that the exemption list cannot
quietly acquire a component or a page (D-038). The table above is held to `BANNED`
row for row and in order by `packages/engines/tests/test_docs_numbers.py`, which is
why the pattern column is the regex verbatim rather than a readable rendering of it.

This paragraph used to end "**Nothing compares the table above against `BANNED`**,
so the two can disagree exactly as they did before P10" - forty lines under the
sentence at the top of this section that correctly says the comparison exists. P10
built the check and left the sentence describing its absence in place, so one
section of one document asserted a thing and its negation, and the negation is the
half a reader would have believed, because it is the half written in bold.

Replacement vocabulary: *visible / not visible in the provided media*, *consistent
with*, *cannot be determined remotely*, *ask the seller*, *have a mechanic verify*.

## 6. Data, privacy, and other people's property

- **Faces and plates** in media the buyer uploads are blurred before anything is
  published in content or share pages. This was a bracketed promise for six phases
  ("P6 content engine implements the blur; until then, no publication"). It exists
  now: `redact.py` pixelates and blurs, and `assert_reviewed` refuses to pass an
  image with no signed review record - absence is treated as unreviewed rather than
  as nothing to do, because a detector that misses one plate in fifty produces a
  folder everybody now believes is safe (D-029). It is not wired into the upload
  path yet, so the "no publication" half of the original promise still binds.
- **Seller identity** is anonymized in any public content. Listings referenced in the
  "10 listings analyzed" series are described, not linked, and identifying details
  are removed. That series was called "10 listings inspected" here until P10, which
  is the noun section 2 says we never use for what we do - our own liability
  document naming a marketing programme after the claim it forbids.
- **The buyer's media is the buyer's.** Default: we retain it for report generation
  and support. Use for model training or eval sets requires separate opt-in, off by
  default, revocable. [COUNSEL: retention period, deletion mechanics, CCPA/CPRA
  applicability given consumer-facing US operation.]
- **VINs** are not personal data on their own but link to one, and we do not publish
  full VINs in any shareable surface - last 6 masked.
- **User-uploaded history documents** may contain a prior owner's name. We extract
  keywords about title brands, not identities, and we do not store the extracted
  personal fields.

## 7. Payment, refunds, and expectation setting

- Price is stated before upload, not after the buyer has spent effort.
- The free teaser must be genuinely useful and must not misrepresent what the paid
  report adds. Bait-and-switch is both wrong and an FTC Act section 5 problem.
- Refund posture for v1: **refund on request, no argument, through the first 100
  reports.** It is cheaper than a dispute, it is the correct treatment of an early
  customer, and it gives us honest signal - a refund request is data about a bad
  report, and each one gets read.
- "Cannot determine" outcomes are not a defect and are not a reason we withhold a
  refund; but a report that is mostly "cannot determine" should not have been sold,
  and that is a product problem to fix upstream (see section 9).

## 8. [COUNSEL] - open questions before first dollar

1. Entity and liability shield: LLC formation before first paid report; personal
   exposure until then.
2. Terms of service and limitation-of-liability clause: enforceability of a liability
   cap at the purchase price for a consumer product, in our state.
3. State-level regulation of vehicle inspection services and of the word "inspection"
   in a product name - does any operating state restrict it?
4. UDAP / FTC Act section 5 review of landing page and teaser claims.
5. NMVTIS: does summarizing title-brand keywords from a user-uploaded document create
   any obligation, and is our language safely outside "vehicle history report"?
6. Insurance: E&O / tech professional liability quote and whether a carrier will write
   an AI-analysis product in this category at all.
7. Data retention and deletion obligations under CCPA/CPRA and any state equivalents.
8. The seller-verified badge: this is the highest-exposure idea in the whole plan,
   because a badge is a representation to a *third party* who did not agree to our
   terms. It was scheduled for P8, P8 shipped without it, and it stays locked until
   counsel answers. Nothing about that is a deferral to record as done.

None of the eight has been answered. The blocking rule at the top of this file says
they must be before the first paid report, and the first paid report has not
happened - `NEXT_PUBLIC_STRIPE_PAYMENT_LINK` is unset, so the pay button renders
visibly disabled rather than as a dead link. That is why the rule has not yet been
broken, which is not the same as it having been kept.

## 9. The honest failure mode we design against

The realistic way this product hurts someone is not a dramatic false clearance. It is
**false reassurance by omission**: a report full of green rows and mild findings that
leaves a nervous buyer feeling done, when the real problem was a thing our inputs
could never show.

Countermeasures, all of which are product requirements and not copy:

- The verdict block leads with **what we could not assess**, not with what looked
  fine. Coverage before conclusions.
- A "media coverage" meter: which of the standard views we actually received. A report
  built on 6 photos says so, loudly, next to the verdict.
- No overall letter grade or single score that can be screenshotted without its
  caveats. The red-flag score is bounded, explained, and never rendered alone.
- The mechanic referral is a required section with specific, findings-linked asks -
  not a generic line. A buyer should leave with a list to hand a shop.

---

*v1. Revisit at every phase gate. Every change to this file gets a DECISIONS.md entry.*
