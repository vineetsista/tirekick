# PHASE 1 - DATA ENGINE

Tag: `v0.2` | Branch: `main` | 18 commits | 142 tracked files
Remote: `github.com/vineetsista/tirekick` (private - D-013)
Gates: 9/9 green, locally and in CI. 214 tests.

**Gate met.** Golden tests run on five real VINs. The cited sections render in the
report. Everything is cached, and CI still needs no network and no key.

---

## 1. What shipped

**VIN validation, offline** (`vin.py`). ISO 3779 transliteration and check digit,
the forbidden I/O/Q alphabet, and the two model years position 10 can mean. Nothing
here touches the network, so a mistyped VIN costs a message instead of a citation
for somebody else's car. A failed check digit rejects a North American VIN and only
warns on others, because the digit is mandatory only in that market.

**A cached federal record layer** (`sources.py`). vPIC decode, NHTSA recalls, NHTSA
complaints, and NHTSA's complaint model index. Every response is wrapped in an
envelope carrying the URL, the retrieval time and the SHA-256 of the body, so a
citation in the report has a receipt behind it rather than our memory of a lookup.
Fixture mode reads the cache and never opens a socket.

**The data engine, rewritten against real records** (`engines/data.py`). Decode,
recalls, complaint counts, and a check of the listing's claimed year/make/model
against what the VIN actually decodes to.

**A title-brand scanner** (`engines/history.py`). Reads documents the buyer
uploaded, quotes the matching line back verbatim, and queries no title registry -
which it says, in every finding, unprompted.

**The report** now renders the vehicle record with its limits in front of it: the
recall scope note above the counts and in the locked colour, the complaint scope
sentence under the table, and every federal lookup cited with what it covered and
when.

**The eval gate grew a minimum sample size.** More on that below, because it is the
thing that stopped this phase from shipping a flattering number.

---

## 2. Decisions (D-014 .. D-021, full text in DECISIONS.md)

- **D-014** A failed check digit rejects a North American VIN, warns on others.
- **D-015** Complaint responses are reduced to counts before they touch the disk.
- **D-016** Recalls are model-scoped, and the report says so three times.
- **D-017** Title-brand matches are classified; a denial produces nothing.
- **D-018** The eval gate gains a minimum sample size.
- **D-019** Golden VINs carry real model codes and an invented serial.
- **D-020** The complaint model index resolves NHTSA's second vocabulary.
- **D-021** Model-level findings are excluded from the red-flag score.

Three of these are corrections to things that were quietly wrong, and they are the
ones worth your attention: **D-016**, **D-017** and **D-021**.

---

## 3. Real measurements

| | |
|---|---|
| Gates | 9/9 green, local and CI |
| Tests | 214 (154 pytest / 41 web / 14 shared / 5 db), 0.4s for the Python suite |
| Golden VINs | 5, all decoding clean against live vPIC |
| Recall campaigns reproduced | 39/39 across the five vehicles |
| Federal cache on disk | 180 KB, 23 files |
| Complaint reduction | 2003 Accord: ~2.0 MB response -> 1.1 KB stored |
| Federal lookups per report | 4 |
| Cost per report | $0.0000 (fixture mode, still no live inference) |
| Demo report | 14 findings, 2 mechanic referrals, coverage 67% |
| Red-flag score | 50/100 - was 100/100 before D-021 |
| Finding types registered | 16 |
| **Measured** | **0** |
| **Enabled for a paid report** | **0** |

Three measurements that are really findings:

**2 of 5 golden vehicles could not be looked up under the model name vPIC returned.**
The recalls endpoint and the complaints endpoint do not share a model vocabulary and
neither says so. Complaints rejects `F-150` with HTTP 400 and indexes that truck as
`F-150 SUPERCAB`, `F-150 REGULAR CAB` and `F-150 SUPER CREW`. The Silverado has the
same problem and resolves cleanly, because vPIC hands back series `1500`. Before
this was handled, the lookup failed, the failure became an empty result, and an
empty result renders as *zero complaints* - which reads as good news. That is the
shape of bug this project exists to not ship.

**The first title-brand scanner put a salvage indicator on a clean car.** The demo
fixture's paperwork says `Salvage brand ... None reported`. That line carries a
negation and an assertion verb at once, my classifier called it ambiguous, and it
rendered a salvage finding on a document that explicitly denies one. Nine denial
phrasings are now locked in `test_history.py`.

**Wiring in real recalls took the demo report to 100/100.** Five campaigns against a
2013 Accord, weighted as major, saturated the score. The number said the car was
maximally bad; the evidence said a model year has campaigns on file, most of them
years old, all free to fix, none known to be outstanding on this car.

---

## 4. Gaps

1. **Still no Vercel deploy.** This was REP 1 in P0 and it is REP 1 again. Nothing is
   publicly reachable, so no stranger has seen a dossier. It needs your account.
2. **0 of 16 finding types are enabled for a paid report**, and that is still the
   correct state. TIREKICK cannot legitimately sell a finding today.
3. **We reproduce the database faithfully and that is not an accuracy measurement.**
   39/39 recalls copied correctly answers "is our code right", not "is this true of
   the car in front of you". It is deliberately kept out of the precision column in
   ACCURACY.md, because a `1.00` there would be read as certainty we do not have.
4. **No OCR.** A scanned or photographed title is not scanned for brands. It is
   reported as unread, never as clean. Needs the vision work in P2.
5. **No title registry.** NMVTIS is not openly queryable. Every title-brand finding
   is a reading of the buyer's own paperwork and says so.
6. **The cache can go stale silently.** Recall counts change. The retrieval date is
   rendered in the Sources block, so it is visible, but nothing warns that a snapshot
   is six months old. That warning belongs in P4 when reports are generated live.
7. **`min_n = 50` is a judgment, not a derivation.** It is defensible and it is not
   calculated from a target confidence interval. Worth revisiting when P2 produces a
   real eval set.
8. **The F-150 complaint count blends three cab configurations.** The scope sentence
   names them and says the VIN cannot distinguish them, which is honest but not
   precise.
9. **demo-01 is still half synthetic.** The photographs are drawings. The VIN and
   every federal record are real. Both halves are labelled, in the report and in
   PROVENANCE.md, and real media still arrives in P2.

---

## 5. YOUR 2 HOURS

### Read, in this order (55 min)

1. `packages/engines/src/tirekick_engines/engines/data.py`, the module docstring and
   `recall_findings` - **10 min**. This is where the phase's central honesty problem
   lives.
2. `packages/engines/src/tirekick_engines/engines/history.py`, docstring through
   `_classify` - **10 min**. Read `_NEGATED_ASSERTION` and the comment above it.
3. `DECISIONS.md`, D-016, D-017, D-021 - **10 min**.
4. `docs/ACCURACY.md`, the section "What P1 checked, and why it is not on the table
   above" - **10 min**. This is the page a customer will use against us, and it is
   the one I most want you to disagree with if you are going to.
5. `packages/engines/tests/test_history.py`, the `DENYING` list - **5 min**. Nine
   lines that must produce nothing.
6. Run it yourself - **10 min**:
   ```
   bash scripts/gates.sh
   packages/engines/.venv/bin/python -m tirekick_engines.cli inspect --fixture demo-01
   ```

### Assigned reading (25 min)

**NHTSA vPIC API documentation** - https://vpic.nhtsa.dot.gov/api/ (verified live).

Every vehicle fact in this report comes out of that API. Decode a VIN you own in the
interactive docs and look at how many of the 150-odd fields come back empty. That
emptiness is why our vehicle record has gaps - the Accord's Drive field renders as
`-` because vPIC returns an empty string for it, not because we dropped it.

Then, in a browser (the site blocks automated checks, so I could not verify the link
myself): **nhtsa.gov/recalls**. Look for anywhere it tells you whether a campaign was
performed on a specific vehicle. It does not, on any public endpoint. That absence is
D-016, and it is the single most consequential fact about this phase.

*The used-car inspection checklist from a mechanic source moves to P2, where it
directly decides which condition findings get built. Spectrogram basics stay in P3.*

### Drill - answer from the code, not from memory (40 min)

1. **A buyer sees five recalls listed under their VIN. Why is the report not telling
   them their car has five open recalls?**
   `engines/data.py:336` (`recall_scope`), `engines/data.py:398` (`recall_findings`),
   locked by `tests/test_data_golden.py:137`.

2. **Their history report says `Salvage brand ... None reported`. Trace what happens.**
   `engines/history.py:180` (`_NEGATED_ASSERTION`), `engines/history.py:198`
   (`_classify`). The vectors are `tests/test_history.py:46`. What did the first
   version do, and why was that the dangerous direction to be wrong in?

3. **The red-flag score went from 100 to 50 without a single finding being removed.
   Why is that more honest rather than less?**
   `dossier.py:91` (`MODEL_LEVEL_TYPES`), `dossier.py:98` (`_red_flag_score`).

4. **We decoded five VINs and got five right. Why is `vin_decode` still disabled?**
   `registry.py:37` (`min_n`), `registry.py:40` (`enabled_for_paid`). Two separate
   reasons, and the second one is in `docs/ACCURACY.md`.

5. **Open `fixtures/federal/nhtsa.complaints.2003.honda.accord.json`. What is in it,
   what is deliberately not, and how would you still prove which HTTP response those
   numbers came from?**
   `sources.py:98` (`_reduce_complaints`), `sources.py:230` (`body_sha256`).

---

## 6. FOUNDER REPS (~30 min)

### REP 1 - Deploy the web app (12 min) - carried over from P0

Still the one thing blocking "skeleton deployed", and it needs your Vercel account.

1. vercel.com -> Add New -> Project -> import `vineetsista/tirekick`
2. **Root directory:** `apps/web`
3. **Build command:** `pnpm --filter web run build`
4. Framework preset: Next.js. **No environment variables** - the viewer reads a
   committed fixture report, so there is nothing to configure and no key to leak.
5. Open `/report/demo-01` on the deployed URL and confirm the evidence overlays
   render.

Also still open: the repo is **private** (D-013). To make it public:
```bash
gh repo edit vineetsista/tirekick --visibility public --accept-visibility-change-consequences
```
Decide before P2. Once real vehicle photos land in this repo, flipping to public also
publishes someone's licence plate, and the answer stops being one command.

### REP 2 - Test the advice we give (8 min)

Our recall copy tells buyers "a dealer can tell you, by VIN, in a phone call, and the
work is free." I have never verified that a dealer will actually do this for a car
they did not sell you.

Call any franchise dealer for a brand you own. Give them **your own** VIN - not the
fixture's, whose serial is `000000` and will be rejected. Ask: *"Can you tell me if
there are any open recalls on this VIN?"*

Write down how long it took and whether they asked why. If they refuse or stall, the
sentence in `engines/data.py` is wrong and I will change it.

### REP 3 - The comprehension test (10 min)

The recall section is the most misreadable part of this report, and I have written
three separate caveats trying to prevent one specific misreading. Caveats I wrote and
then tested myself prove nothing.

Show the Vehicle Record section to one person who does not work in software. Do not
explain it. Ask exactly one question:

> **"Does this car have open recalls?"**

The correct answer is *"it doesn't say - you'd have to ask a dealer."* If they say
yes, three caveats and a colour change were not enough, and that is a finding about
the design rather than about them. Tell me which words they read.

---

## 7. NEXT - P2: VISION ENGINE

Real photographs, real prompts, real measurements. Claude vision behind the
`ModelClient` seam that P0 built and P1 left untouched: view classification, then
condition findings with bounding boxes, each one cited on the image it came from.

The gate is where P2 differs from everything so far: **a labeled eval set, and the
first real numbers in `docs/ACCURACY.md`** - including the misses. This is the phase
where `measured_precision` stops being `None`, and where `min_n` starts costing us
something.

It is also the phase where real vehicle media enters the repository, which makes the
public-vs-private decision in REP 1 time-sensitive.
