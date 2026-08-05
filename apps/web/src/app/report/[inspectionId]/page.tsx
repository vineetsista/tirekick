import type { Metadata } from "next";
import { cookies } from "next/headers";
import { notFound } from "next/navigation";
import { ReportView } from "@/components/ReportView";
import { canRead, grantCookieName, isPubliclyReadable } from "@/lib/access";
import { loadReport } from "@/lib/inspections";
import { isValidInspectionId } from "@/lib/media";
import { demoReport } from "@/lib/report";

/**
 * The paid dossier for an uploaded inspection.
 *
 * The static /report/demo-01 route still exists and wins for the public demo;
 * this route is for everything else, which means everything private. The check
 * here is the same canRead("report") the media handler applies to each
 * photograph, so the page and its evidence open and close together - a grant
 * that renders the findings renders the pictures they cite, and revoking one
 * revokes both.
 *
 * Denial is a 404: an unauthenticated visitor probing ids learns nothing about
 * which inspections exist.
 */

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "TIREKICK report",
  description: "A TIREKICK dossier. Access is granted per inspection.",
  robots: { index: false, follow: false },
};

export default async function ReportPage({
  params,
}: {
  params: Promise<{ inspectionId: string }>;
}) {
  const { inspectionId } = await params;
  if (!isValidInspectionId(inspectionId)) notFound();

  // The dynamic route never receives the public demo (its static page wins),
  // but if that page were ever deleted this branch keeps the demo public
  // rather than letting a routing change silently paywall the showroom.
  if (isPubliclyReadable(inspectionId)) {
    return <ReportView report={demoReport} />;
  }

  const token = (await cookies()).get(grantCookieName(inspectionId))?.value;
  if (!canRead(inspectionId, "report", token).allowed) notFound();

  const report = await loadReport(inspectionId);
  if (!report) notFound();

  return <ReportView report={report} />;
}
