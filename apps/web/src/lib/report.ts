import {
  MODEL_LEVEL_TYPES,
  parseReport,
  parseTeaser,
  type Asset,
  type Finding,
  type Report,
  type Severity,
  type SystemStatus,
  type Teaser,
} from "@tirekick/shared";
import raw from "@/generated/demo-01.report.json";
import rawTeaser from "@/generated/demo-01.teaser.json";

/**
 * Parsed at module scope on purpose. The fixture report is emitted by the Python
 * engines; if it stops satisfying the zod contract, the web build fails here
 * rather than the viewer rendering something malformed in front of a buyer.
 */
export const demoReport: Report = parseReport(raw);

/**
 * The free projection, parsed through the same guard the paid report gets.
 *
 * `parseTeaser` throws if the payload carries any paid-only field, so a refactor
 * that starts routing a full report down the free path fails the build rather
 * than shipping the product for nothing.
 */
export const demoTeaser: Teaser = parseTeaser(rawTeaser);

export function severityColor(severity: Severity): string {
  switch (severity) {
    case "info":
      return "var(--tk-sev-info)";
    case "minor":
      return "var(--tk-sev-minor)";
    case "major":
      return "var(--tk-sev-major)";
    case "critical":
      return "var(--tk-sev-critical)";
  }
}

export function statusColor(status: SystemStatus): string {
  switch (status) {
    case "no_issues_visible":
      // Deliberately not a green. "Nothing adverse was visible in the media
      // provided" is a statement about the photographs, not a pass, and the
      // coverage map makes the same choice for the same reason (LAW 2).
      return "var(--tk-paper)";
    case "attention":
      return "var(--tk-sev-major)";
    case "locked_mechanic_required":
      return "var(--tk-locked)";
    case "cannot_determine":
      return "var(--tk-unknown)";
  }
}

export function statusLabel(status: SystemStatus): string {
  switch (status) {
    case "no_issues_visible":
      return "NO ISSUES VISIBLE";
    case "attention":
      return "ATTENTION";
    case "locked_mechanic_required":
      return "MECHANIC REQUIRED";
    case "cannot_determine":
      return "CANNOT DETERMINE";
  }
}

export function assetUrl(inspectionId: string, path: string): string {
  return `/f/${inspectionId}/${path}`;
}

export function assetById(report: Report, id: string): Asset | undefined {
  return report.assets.find((a) => a.id === id);
}

const SEVERITY_RANK: Record<Severity, number> = {
  info: 0,
  minor: 1,
  major: 2,
  critical: 3,
};

/**
 * Split the findings into the two things the verdict already treats as separate.
 *
 * The verdict headline says "2 finding(s) that are likely to cost money.
 * Separately, 5 recall campaign(s) are on record for this model year - free to
 * fix". The findings list then rendered all fourteen in one undifferentiated
 * column, five of them recall campaigns wearing the same MAJOR badge as the
 * corrosion on the rocker panel.
 *
 * A buyer scrolling that sees seven major problems with the car in front of them.
 * There are two. The other five are printed notices about every car of that model
 * year, cost nothing to fix, and are the report's own stated reason for not
 * counting them in the score. Presenting them identically contradicted the
 * paragraph directly above them.
 */
export function partitionFindings(findings: Finding[]): {
  vehicle: Finding[];
  model: Finding[];
} {
  const vehicle: Finding[] = [];
  const model: Finding[] = [];
  for (const f of findings) {
    (MODEL_LEVEL_SET.has(f.type) ? model : vehicle).push(f);
  }
  return { vehicle, model };
}

/**
 * Findings that describe the model rather than this car.
 *
 * Taken from the shared contract rather than retyped here - the Python scoring
 * engine excludes exactly these from the red-flag score (D-021), and a viewer
 * that disagreed about the membership of this set would put a recall campaign in
 * the column headed "found on this vehicle".
 */
const MODEL_LEVEL_SET: ReadonlySet<string> = new Set(MODEL_LEVEL_TYPES);

export function bySeverity(findings: Finding[]): Finding[] {
  return [...findings].sort(
    (a, b) =>
      SEVERITY_RANK[b.severity] - SEVERITY_RANK[a.severity] ||
      b.confidence - a.confidence,
  );
}

/** The finding a stranger should see first: worst, best-evidenced, has a picture. */
export function headlineFinding(report: Report): Finding | null {
  const { vehicle } = partitionFindings(report.findings);
  const withImages = vehicle.filter((f) =>
    f.evidence.some((e) => e.kind === "image_region"),
  );
  return bySeverity(withImages)[0] ?? null;
}

export function titleCase(key: string): string {
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
