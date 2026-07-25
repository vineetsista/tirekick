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

/** The exact sentence rendered for every locked system. Not paraphrased anywhere. */
export const LOCKED_SYSTEM_STATEMENT =
  "Not remotely verifiable - independent mechanic required.";

/** LAW 6 + LIABILITY section 4. Shown above the verdict, never dismissible. */
export const REPORT_BANNER =
  "Automated analysis of media you provided. This is not an inspection, a " +
  "certification, or a warranty. Confidence is not certainty. Have an independent " +
  "mechanic examine any vehicle before you buy it.";

export const SHARE_FOOTER = "INSPECTED BY TIREKICK AI";
