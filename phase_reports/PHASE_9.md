# PHASE 9 - THE DOOR, AND WHAT AN AUDIT FOUND BEHIND IT

Branch: `main` | 612 tests | 60 decisions logged
Gates: 9/9 green.

P8 ended by naming a hole it had not closed: *"Media is served unguarded.
`/f/<id>/*` is static: the report page checks a grant, the photographs behind it
do not."* That is this phase's first half.

The second half was not planned. Closing the hole meant reading the report path
end to end, and reading it end to end turned into a full audit of the
repository - ten specialists over the engines, the contract, the web app, the
tests and the docs, each finding verified by an adversary trying to refute it.
**Seventy findings survived that filter.** This phase fixes the ones that reach a
buyer.

None of it moves the four zeros. Nothing here required a key or a car, which is
another way of saying: all of it could have been done in any of the last four
phases, and was not, because nobody looked.

---

## 1. The door

`/f/demo-01/photo_01.jpg` was a file in `public/`. The report page verified an
HMAC grant; the photographs it renders were served by the framework before any
check could run. The product sells one sentence - *here is what it can see, and
here is the picture it saw it in* - and the sentence was gated on one side.

**The framework detail that decided the design:** a file under `public/` is
served *before* any route handler. So the demo's media had to leave `public/`
entirely, or the check would exist and never execute for the one inspection
every stranger loads first. The sync script now deletes the copy it used to
create, and the route serves demo media from `fixtures/` - the source of truth,
the same bytes the golden report was hashed against.

Two judgement calls inside that, both restrictive (D-052):

**The allowlist is the report's own citations, not the media directory.** The
directory can hold things no report mentions: `redactions.json` sidecars naming
the reviewer and boxing every face a human marked, raw frames left behind by a
crashed extraction, an upload the pipeline rejected. "Serve what is on disk under
this id" publishes all of it. "Serve what the report cites" publishes exactly the
evidence the buyer was shown citations for, which is the boundary LAW 1 already
draws. The test that proves it puts a real `redactions.json` inside the media
directory and asserts a **paid** grant cannot fetch it.

**Denial is a 404, not a 403.** Absent, uncited, and unauthorised are one answer,
so a prober cannot map which inspection ids exist.

Grants grew tiers (D-053), because the media route forced a question the P7 grant
design never had to answer. The free teaser renders one photograph, so *some*
media must open without payment - but an upload is somebody's prospective car,
and "free" is a statement about money, not about who may look. `paid` and `demo`
open the report and everything it cites; `owner`, issued to the uploader at
upload time, opens the teaser and exactly one photograph. A stranger with the URL
and no grant gets nothing at all. The grant moved out of a function parameter and
into an httpOnly cookie, set by one route that verifies a token and redirects,
because an `<img>` tag carries no header we control and a token in a URL leaks
through referrers and screenshots.

And the flow finally has a form (D-054). LAW 7's end-to-end test has driven
upload → analyse → grant → dossier through library calls since P7, with no page
that let a person do the same. `/new` is that page, running the same local
Python subprocess `inspections.ts` has always declared itself to be - and saying
so in its own copy, because a build with no vision key catalogues photographs
rather than examining them, and the page a buyer starts at should not be the one
place that pretends otherwise.

---

## 2. What the audit found

Ten finders, each verified by a skeptic reading the current code and trying to
refute the claim. What follows is what survived.

### The gate that was measuring nothing

The D-050 browser gate serves `/f/**` off disk so images have real intrinsic
dimensions - its own comment says that without it "every `<img>` would measure
zero and the overflow numbers would be fiction."

It was fiction. `page.setContent` leaves the document on `about:blank`, where a
root-relative URL cannot resolve: no request fires, the interceptor never runs,
the image reports `complete` at 0×0, and `@font-face` never fetches. **From D-050
until this phase, the layout gate measured every page with zero-size images and
fallback system fonts** - 73 green assertions about a page nobody had laid out.
Found by writing a probe that logged which URLs chromium actually requested, and
getting an empty list.

The gate now navigates to a fully-intercepted fictional origin, and records every
path it could not serve so a miss fails the suite loudly instead of quietly
measuring nothing (D-055). Verified by pointing it at a directory that does not
exist and watching it fail.

### A gate with no mechanism

LAW 4 says "below threshold means disabled in paid output" and names
`registry.py::enabled_for_paid` as the enforcement point. That flag is read by
the gate table and the accuracy statement - by the things that *describe* the
gate - and by nothing in the report path. It governed a console printout. The
moment `bench/` records a type at 0.60 against a 0.85 threshold, the console
would print `NO / below gate` while the paid report shipped the type unchanged.

Now enforced, with a distinction (D-056): *measured and failing* is filtered
before the safety clamp and named in the could-not-assess block with its
precision, sample size and threshold. *Not measured* still ships under D-032's
disclosure, because filtering on unmeasured would empty every report this
product can currently produce while telling the buyer less than the sentence
above the payment button already does. The law's headline is still broader than
the code, and that gap is written down rather than papered over.

### The sentence the buyer says to a seller

> *"a shop quoted that kind of work at roughly $600 to $900."*

Shipped, in the demo report, in the negotiation script. No shop was called. D-024
holds that cost bands have no real source; `PROVENANCE.md` declares the fixture's
bands invented; the same function's docstring promises "a script that never asks
the buyer to overstate what we found." It scripted a fabricated provenance for
the buyer to assert to a stranger's face (D-057).

Beside it, the mechanism D-024 relied on turned out to be false. It kept
`estimated_cost_usd` out of the tool schema on the reasoning that "a field that
is not in the schema cannot be returned" - but JSON Schema permits extra
properties unless told otherwise, and the code read `raw.get("estimated_cost_usd")`
directly under a comment saying it never does. A live model volunteering a dollar
figure had it flow into a price deduction, the fair range, and that sentence.

### The car described as a wreck by its model year

D-021 kept recall campaigns out of the red-flag score, and said why. The systems
table never got the rule. A recall carries confidence 1.0 - confidence that the
*campaign exists* - so the shipped fixture rendered:

    transmission   attention   1.0   Recall 25V422000: POWER TRAIN:DRIVELINE...

on a car nothing had observed a transmission fault on. The teaser turned that row
into "Something was found here." The engine row led with a recall title over the
fluid leak actually visible in a photograph. The teaser counted "7 major" beside
a headline saying two and a score that excluded five of them (D-058).

The inverse error was in the headline: a campaign against a locked system becomes
a mechanic referral *before* the count runs, so a car whose only campaign was an
airbag recall - the most common category in the fleet, and a do-not-drive
candidate - reported **"Nothing adverse was visible in the media provided."**

### Sold what the report does not contain

The teaser's six unlock bullets were a fixed list. A buyer who uploaded eight
photographs and no audio, no VIN and no paperwork was sold "the engine audio
spectrogram", "the full vehicle record" and "what your own paperwork says", paid
$25, and opened a report where none of those sections render. Meanwhile the price
comparison - a real paid section - was advertised nowhere. The teaser computed
`has_audio` and `has_price_check` and used neither (D-059).

### The claim the whole liability architecture exists to deny

`SHARE_FOOTER = "INSPECTED BY TIREKICK AI"` - on the share page, the report
footer, and the running footer of anything printed. LIABILITY section 2 commits
to using "inspection" only in the compound product name; section 5 bans "we
inspected" because *a person inspects, we analyze media*. This is the same claim
in the passive voice, stamped across a document whose own banner four inches up
denies it, on the surfaces most likely to be forwarded to a seller.

The scanner missed it because it banned a phrase naming an actor. It now catches
the passive form, along with three other holes an audit found by running it:
`certifies` and `certifications` (the pattern matched only `certify/certified/
certification`), `passed our inspection` (the pattern required adjacency), and
**any banned phrase wrapped across a line break** - which the sanctioned-phrase
stripper had always tolerated, deliberately, so `"This car is safe to " + "drive"`
scanned as two innocent lines through the gate written to catch exactly that.

### Six more, in one paragraph each

**EXIF GPS survived redaction for every photograph marked "nothing to redact."**
`cmd_apply` skips images with no regions, and stripping EXIF happens only inside
the re-encode it skips. An interior shot with no plate and no face - the majority
of the standard views - keeps the coordinates of the seller's driveway, in a
repository whose history is forever, while the tool reports success. Named here
and **not yet fixed**: the crew working it hit the session limit mid-change.

**A manifest could name a file outside its own inspection.** `materialize_assets`
joined a manifest-supplied filename onto the media root with no containment
check, so an absolute path or a `../` escaped it - and the same value later became
a servable asset path. Fixed at the boundary; the media route validates
independently on the way back out.

**An asset id steered a cache filename.** `f"{engine}.{task}.{subject}"` becomes a
path, and `subject` is a manifest-supplied id.

**Enumerated history rows read as denials.** `"No. 3 - SALVAGE TITLE ISSUED"`
classified as *denied* because the negation regex matched the enumeration
abbreviation "No." - the module's own comment names that exact string as the case
its assertion pattern exists to rescue. Real history reports number their rows.
Also **not yet fixed** for the same reason.

**Transient markers were 19-36ms early**, against a module header claiming ~12ms
- always early, never late, because the code named the analysis window's centre
and a 2048-sample window is 93ms long. The honest estimate is the midpoint of the
one hop of new audio the flux difference actually describes, walked back to where
the rise crossed its threshold: ±5.8ms.

**A three-cylinder engine "fires 1 times per revolution."** Integer division, in
the one place the report shows its arithmetic, beside an rpm computed from 1.5.

**Opus-5 was priced at three times its rate** in the COGS table, and the model
alias the docs tell people to use was keyed only by its dated id, so the spelling
we recommend was billed at the fallback rate. A wrong number that is *in* the
table prints without the caveat an unknown model gets.

---

## 3. What this phase did not fix

Said plainly, because a gap in a phase report is not a gap that has been handled
- which is the lesson P7 wrote and P8 repeated:

The audit surfaced **70 verified findings**. This phase fixed roughly half - the
ones that reach a buyer, plus the security ones. Six parallel crews were working
the rest when the session's usage limit ended them mid-change; the work that had
landed is in this commit and the work that had not is not. Specifically still
open: **the EXIF-on-nothing-to-redact leak** (a security hole in the tool whose
entire purpose is preventing exactly that leak), **the enumerated-history false
negative**, redaction records keyed by filename stem so two files collide, EXIF
orientation never applied before drawing blur boxes, several contract-parity gaps
between the zod and pydantic sides, the accuracy page rendering raw markdown in a
`<pre>`, and a documented list of test-infrastructure checks that cannot fail.

They are in the audit output, they are verified, and they are the first work of
P10.

---

## 4. The rules this phase adds

**D-055.** A gate that cannot fetch what it is measuring fails, and says which
paths it could not fetch. D-050 established that a gate must not skip; this is
the same rule applied one layer down, to the gate's own plumbing, after finding
that the layout gate had been measuring blank images for a full phase.

**D-052's allowlist.** What a route serves is what the artifact cites, never what
the directory contains. The difference is invisible until the directory contains
something the artifact never mentioned - and by then it is published.

**D-060.** A shape validates as the shape it claims to be. Four coordinates each
legal in [0,1] can still describe a box that runs off the edge of the photograph;
a range whose low exceeds its high is not a range. Both were representable, and
a report carrying either is one a reader cannot check.

---

## 5. Where the project stands

| | |
|---|---|
| Phases | 9 |
| Tests | 612 |
| Gates | 9/9 green |
| Decisions logged | 60 |
| Audit findings verified | 70 |
| Audit findings fixed this phase | ~35 |
| Finding types the engines can produce | 16 |
| **Finding types with a measured accuracy** | **0** |
| **Finding types enabled for a paid report** | **0** |
| **Real vehicles this has ever seen** | **0** |
| **Live model calls ever made** | **0** |

The four zeros have not moved.

What did move is the distance between what this repository claims and what it
does. A phase that spends most of its effort on an audit rather than on features
looks like a phase that shipped little, and the honest reading is the opposite:
the layout gate had been green and blind for a phase, the eval gate had been a
printout for nine, and the negotiation script had been putting a fabricated shop
quote in a buyer's mouth since P2. Every one of those was invisible to 517 tests
and visible within an hour of looking on purpose.

That is worth stating as a rule rather than an anecdote: **this project's
characteristic defect is a claim that nothing checks, and it does not matter
whether the claim lives in a docstring, a law, a colour table, or a switch.** Six
phases found it in comments. This one found it in an enforcement point.

---

## 6. NEXT

Still the measurement phase, and it still cannot start without a key and a car.
Ninth phase asking.

Before it: the half of the audit this phase did not reach, starting with the EXIF
leak - because it is a live privacy hole in the one tool whose job is preventing
that hole, and the first real photograph will arrive with GPS in it.
