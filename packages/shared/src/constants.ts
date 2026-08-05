/**
 * Shared constants. These values are duplicated in
 * packages/engines/src/tirekick_engines/models.py and are held in sync by the
 * contract drift test (see DECISIONS.md D-002).
 */

/** Bumped on any breaking change to the report contract. */
export const SCHEMA_VERSION = "1.0.0";

/**
 * LAW 2. Systems that are NEVER cleared remotely, in any report, at any confidence.
 * Mirrored in tirekick_engines/safety.py::LOCKED_SYSTEMS.
 */
export const LOCKED_SYSTEMS = [
  "brakes",
  "restraints",
  "structure",
  "steering",
] as const;

/**
 * Finding types that describe the model year rather than the car in front of you.
 *
 * Mirrored in tirekick_engines/dossier.py::MODEL_LEVEL_TYPES, where they are
 * already excluded from the red-flag score (D-021) and from the teaser sample
 * (D-044) for the same reason: a recall campaign is true of every car of that
 * model, so counting it against this one overstates what was found.
 *
 * The viewer needs the same list to keep them out of the vehicle findings column.
 */
export const MODEL_LEVEL_TYPES = ["open_recall", "complaint_pattern"] as const;

/** The exact sentence rendered for every locked system. Not paraphrased anywhere. */
export const LOCKED_SYSTEM_STATEMENT =
  "Not remotely verifiable - independent mechanic required.";

/**
 * What the paid report costs, in whole US dollars. The only place either
 * language writes that number down.
 *
 * Mirrored in tirekick_engines/teaser.py::PRICE_USD and held to it by
 * packages/engines/tests/test_shared_constants_parity.py, which also forbids a
 * second literal anywhere in the Python tree. There were three: this one for
 * the landing page, `cli.py --price` for the teaser the engine writes into the
 * artifact, and one more in the teaser tests. The landing page printed the
 * TypeScript number and the teaser one click later printed the Python one, and
 * nothing in the repository compared them, because equal literals agree.
 *
 * This is a display price and not a charge. The amount a buyer is billed is
 * configured on the Stripe payment link, outside this repository, and nothing
 * here can read it - changing this constant changes every number on every page
 * and changes nothing at Stripe. See apps/web/src/lib/checkout.ts for the
 * declaration the deployment has to make instead.
 */
export const PRICE_USD = 25;

/** LAW 6 + LIABILITY section 4. Shown above the verdict, never dismissible. */
export const REPORT_BANNER =
  "Automated analysis of media you provided. This is not an inspection, a " +
  "certification, or a warranty. Confidence is not certainty. Have an independent " +
  "mechanic examine any vehicle before you buy it.";

/**
 * The watermark on the most forwardable surfaces the product has: the share
 * page, the paid report's footer, and the running footer of anything printed.
 *
 * The verb here was wrong for six phases: it named the physical act this
 * product never performs, in the passive voice, stamped across a document
 * whose own banner four inches up denies performing it. The copy scanner
 * missed it because the banned phrase names an actor and this wording named
 * nobody. A person does that with a car on a lift; this analyzed media.
 */
export const SHARE_FOOTER = "ANALYZED BY TIREKICK AI";
