import {
  parseReport,
  parseTeaser,
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
      return "var(--tk-accent)";
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

export function titleCase(key: string): string {
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
