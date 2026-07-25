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
  a listing. (The seller-facing badge product in P8 is explicitly locked behind this
  question being answered by counsel first.)
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

| Moment | Placement | Substance |
|---|---|---|
| Landing page, above the fold | Body copy, not fine print | What this is: AI analysis of your photos. What it is not: a mechanic. |
| Upload flow, before payment | Checkbox, unticked by default, own paragraph | Acknowledgement: remote analysis, not an inspection; safety systems cannot be assessed; get a mechanic before buying. |
| Report, top of page, before the verdict | Persistent banner, same type size as the verdict | Remote analysis of buyer-supplied media. Not an inspection. Confidence is not certainty. |
| Every safety-critical row | Inline, in the row itself | Not remotely verifiable - independent mechanic required. |
| Every finding | Inline confidence bar + basis | The evidence and the confidence, adjacent to the claim. |
| Share page / public link | Footer + watermark | Inspected by TIREKICK AI, plus the same "not an inspection" line. |
| PDF export | First page and running footer | Same as report banner; survives being printed and handed to a seller. |

Design rule: **a disclaimer that a user can reach the verdict without reading has not
been placed correctly.** The banner is not dismissible.

## 5. Banned language

These phrases never appear in product copy, report output, marketing, or model
prompts. This is enforced by a test that scans copy and prompt files
(`packages/engines/tests/test_liability_copy.py`).

- "certified", "certification", "TIREKICK certified"
- "guaranteed", "guarantee", "warranted", "warranty"
- "safe to drive", "road safe", "roadworthy"
- "passed", "passes inspection", "clean bill of health"
- "we inspected" (we analyze; a person inspects)
- "no problems found" (correct phrasing: "no problems visible in the media provided")
- "brakes are fine" and any variant clearing a locked system

Replacement vocabulary: *visible / not visible in the provided media*, *consistent
with*, *cannot be determined remotely*, *ask the seller*, *have a mechanic verify*.

## 6. Data, privacy, and other people's property

- **Faces and plates** in media the buyer uploads are blurred before anything is
  published in content or share pages. [P6 content engine implements the blur; until
  then, no publication.]
- **Seller identity** is anonymized in any public content. Listings referenced in the
  "10 listings inspected" series are described, not linked, and identifying details
  are removed.
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
8. The P8 seller-verified badge: this is the highest-exposure idea in the whole plan,
   because a badge is a representation to a *third party* who did not agree to our
   terms. Locked until counsel answers it.

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
