# PHASE 3 - AUDIO ENGINE

Tag: `v0.4` | Branch: `main` | 33 commits | 173 tracked files
Remote: `github.com/vineetsista/tirekick` (private - D-013, D-022)
Gates: 9/9 green, locally and in CI. 295 tests.

**Gate met, in the specific way `docs/EVAL.md` said it would be.**

P0 wrote down, in advance, what should happen if the audio engine reached this
point without a measured precision: *ship as a spectrogram and a list of things to
ask a mechanic, with no anomaly claims attached.* That is exactly the situation, so
that is exactly what shipped.

**0 of 16 finding types are enabled for a paid report. Fourth phase running.**

---

## 1. What shipped

**A signal layer that measures and does not interpret** (`signal.py`). ffmpeg
decode, STFT, log-frequency spectrogram, and the numbers that belong under it:
level, clipping, dominant frequency, transient onsets, steadiness. Every field is
a property of the waveform.

**A working onset detector.** It locates all three planted impulses in the fixture
clip to within 21ms, at eight times the prominence of the strongest false
positive. It is used to draw markers on a picture and for nothing else.

**The audio section of the report.** The spectrogram, the transient markers, the
measured idle frequency, a player so the buyer can hear it, and a statement at the
top saying no claims are attached to any of it.

**Plate and face redaction** (`redact.py`, `scripts/redact_media.py`), pulled
forward from P6 because D-022 made it a blocker rather than a polish item.

**A much faster image path** (`client.py`), found by accident.

---

## 2. Decisions (D-026 .. D-030, full text in DECISIONS.md)

- **D-026** Audio features are cached, even though computing them is free.
- **D-027** The audio engine ships a picture and says nothing.
- **D-028** Implied RPM only when the VIN supplied the cylinder count.
- **D-029** Redaction is model-proposed and human-signed, and it moved up a phase.
- **D-030** Image encoding: decode small, resize rarely, encode once.

**D-027 is the phase.** Everything else is support.

---

## 3. Real measurements

| | |
|---|---|
| Gates | 9/9 green, local and CI |
| Tests | 295 (230 pytest / 46 web / 14 shared / 5 db) |
| Onset detection on known ground truth | 3 of 3, within 21ms |
| Separation, real impulses vs strongest false positive | 57-59 prominence vs 6.7 |
| Firing fundamental recovered | 32.3 Hz against 31.5 Hz built in (one FFT bin) |
| Implied idle, 4-cylinder | 969 rpm |
| Python suite runtime | **2.7s, from 180s** |
| Pixels decoded per phone photo | **3.0 MP, from 12.2 MP** |
| Image encodes per report | **8, from 22** |
| Finding types enabled for a paid report | **0** |
| Audio claims made | **0** |

Four things worth pulling out.

**The old audio fixture could not test anything.** It was two mixed sine tones. A
pure tone has no onsets, so the detector ran against it, found nothing, and would
have gone on finding nothing forever - indistinguishable from being broken. The
fixture is now a synthetic engine-like signal with three impulses at times the
generator declares, which makes it ground truth by construction.

**A 2% resize was costing a second per image.** Chasing a test suite that had gone
from 2 seconds to 180 turned up three separate faults in twenty lines: no caching
across passes, a `draft()` call asking for a square target when Pillow does integer
division on both axes and takes the minimum - `min(4032//1568, 3024//1568) = 1`,
silently no reduction - and a full-quality resample of a 1600px photo down to
1568px to save 4% of the tokens.

**This machine takes six seconds to multiply two 2000x2000 matrices.** So the
performance work above is reported as pixel counts and cache hit rates, not as a
speedup: the drafted decode has measured *slower* than the full one on pure noise.
Any timing published from here would be fiction. The suite time is quoted because
it is a 60x change, far outside the noise.

**Two prompt families now exist and both are scanned.** The redaction prompt is
the first one written to deliberately over-report: a wrongly included region costs
a smudge on a photograph, a wrongly omitted one publishes a stranger's number
plate permanently.

---

## 4. Gaps

1. **Still no API key.** The live vision path and the redaction proposer have both
   never executed. Fourth phase asking.
2. **Still no labelled photographs**, so still nothing measured, so still nothing
   sellable. This is the only gap that matters.
3. **Still no Vercel deploy.** Fourth phase asking.
4. **The audio anomaly detector is built and disabled.** Everything needed to make
   claims exists except the evidence that the claims would be right. Measuring it
   needs recordings of engines with known faults, which is a harder capture problem
   than photographs - you cannot arrange for a car to knock on demand.
5. **Redaction has never run on a real photograph.** The blur is tested against a
   synthetic high-contrast block. Real plates are smaller, angled, and partly
   occluded.
6. **The transient detector has no false-positive rate.** One weak spurious
   detection on one synthetic clip is not a measurement. On real recordings, wind,
   doors and traffic will all produce onsets.
7. **A prompt change still does not invalidate cached responses** - carried from P2.
8. **`min_n = 50` is still a judgment** - carried from P1.

---

## 5. YOUR 2 HOURS

### Read, in this order (45 min)

1. `packages/engines/src/tirekick_engines/engines/audio.py`, module docstring and
   `_transient_statement` - **10 min**. The copy in that function is the phase.
2. `packages/engines/src/tirekick_engines/redact.py`, docstring and
   `assert_reviewed` - **10 min**. You are the person whose name goes in
   `reviewed_by`, so read what that signature is claiming.
3. `DECISIONS.md` D-027 and D-029 - **10 min**.
4. Look at the audio section in the browser - **5 min**:
   ```
   pnpm --filter web dev
   # then open /report/demo-01 and scroll to Engine audio
   ```
   The three orange lines are where the detector fired. Check they line up with
   the three vertical stripes in the spectrogram, because that correspondence is
   the entire evidential claim being made.
5. `bench/README.md` again, the capture section - **10 min**. It has not changed,
   and it is still the thing standing between this product and a number.

### Assigned reading (30 min)

**A used-car inspection checklist from a mechanic source.** Overdue - it was
deferred from P2 and it decides what P4 builds.

I could not verify a specific link from here: the sites worth reading (AAA,
Consumer Reports, Car Talk) all block automated requests, and I will not send you
to a URL I have not confirmed resolves. So: search for **"pre-purchase inspection
checklist site:aaa.com OR site:cartalk.com"**, or ask the mechanic from REP 2.

What I want out of it is not the list. It is the **ordering**: what does an
experienced person look at first, and how much of that is reachable from a
photograph? My guess is that most of the top five is not - fluid condition on a
dipstick, play in a wheel, how it sounds at operating temperature - and if that is
right, it belongs in `docs/ACCURACY.md` under what we cannot assess, in their
words rather than mine.

*Spectrogram basics turned out to be unnecessary as separate reading - the
spectrogram in the report is annotated, and `signal.py` explains the tradeoffs
where they are made.*

### Drill - answer from the code (45 min)

1. **The detector found three sharp transients. Why does the report not say what
   made them?**
   `engines/audio.py:41` and `:196`, `docs/EVAL.md`. What would we have had to do
   first to earn that sentence?

2. **A V6 idling at 700rpm and a four-cylinder at 1050rpm produce the same firing
   frequency. Which does the report show, and what stops it guessing?**
   `signal.py:291`, `engines/audio.py:81`.

3. **You photograph a car, run the redaction proposer, and it returns no regions
   for one image. What happens if you commit it?**
   `redact.py:184`. Then: what has to happen instead, and whose name is on it?

4. **Why is a spectrogram committed to the repository when the code to generate it
   is right there?**
   `DECISIONS.md` D-026. It is the same argument as D-015 and the same argument as
   the mypy bug in P2 - what is the shape they share?

5. **`draft("RGB", (1568, 1568))` on a 4032x3024 photo does nothing at all. Why?**
   `client.py:109`, and the test that pins it. This one is worth working out on
   paper before reading the answer.

---

## 6. FOUNDER REPS (~30 min)

### REP 1 - Deploy the web app (10 min) - fourth ask

vercel.com, import `vineetsista/tirekick`, root directory `apps/web`, build
command `pnpm --filter web run build`, Next.js, no environment variables.

I am going to keep putting this first until it is done or you tell me to drop it.
Nothing built in four phases has been seen by anyone outside this machine.

### REP 2 - The API key (5 min) - second ask

console.anthropic.com, new key, **low monthly cap - $20 covers everything**, then:
```bash
echo 'ANTHROPIC_API_KEY=sk-ant-...' >> .env
```
`.env` is gitignored. Do not paste it into chat.

### REP 3 - One car, and one recording (15 min)

The eight photographs from `bench/README.md`, plus this, which is new:

**Record 30 seconds of the engine.** Phone at arm's length over the open bonnet,
engine running and warmed up, no talking. Then, if you can, a second clip at a
genuine cold start the next morning - a cold start is where a fault is loudest and
it is the one recording a seller will not have.

Say the car's make and model out loud at the start of the clip. It costs a second
and it means the file identifies itself if it ever gets separated from the folder.

Then write down what you know to be true, including what a photograph and a
microphone cannot show.

Send me the folder. I will run it, label nothing myself, and hand you the output
to check against what you wrote down.

---

## 7. NEXT - P4: UPLOAD, PAY, DELIVER

The phases so far have built a report. P4 builds the thing that gets someone to
pay for one: upload, a free red-flag teaser, Stripe, and the paid dossier behind
it.

Two things in it are already known to be uncomfortable.

**The teaser is the real unit economics.** At 10% conversion, ten teasers at $0.34
make one paid report cost $3.40 - a tenfold swing that no model choice comes near.
That number goes in `docs/UNIT_ECONOMICS.md` from the first teaser onward.

**Charging $25 for a report where every finding type is gate-disabled is not
something I will build quietly.** Either the eval lands first, or the paid product
ships with a page that says plainly what it is measured to do - which, today, is
nothing. That is a decision for you and it is the one I would most like to discuss
before writing the checkout page.
