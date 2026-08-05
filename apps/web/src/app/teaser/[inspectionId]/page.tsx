import type { Metadata } from "next";
import { cookies } from "next/headers";
import { notFound } from "next/navigation";
import { TeaserView } from "@/components/TeaserView";
import { canRead, grantCookieName, isPubliclyReadable } from "@/lib/access";
import { loadTeaser } from "@/lib/inspections";
import { isValidInspectionId } from "@/lib/media";
import { demoTeaser } from "@/lib/report";

/**
 * The free projection of an uploaded inspection.
 *
 * Free does not mean public. The teaser of somebody's prospective car - their
 * photographs, the year and model, the sample finding - is theirs; "free" is a
 * statement about money, not about who may look. The tier check accepts the
 * `owner` grant issued at upload time, so the person who provided the media
 * reads the teaser without paying, and nobody else reads it at all.
 */

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "TIREKICK - free result",
  description:
    "What TIREKICK found in the media provided, what it could not assess, and what the full report adds.",
  robots: { index: false, follow: false },
};

export default async function TeaserPage({
  params,
}: {
  params: Promise<{ inspectionId: string }>;
}) {
  const { inspectionId } = await params;
  if (!isValidInspectionId(inspectionId)) notFound();

  if (isPubliclyReadable(inspectionId)) {
    return <TeaserView teaser={demoTeaser} />;
  }

  const token = (await cookies()).get(grantCookieName(inspectionId))?.value;
  if (!canRead(inspectionId, "teaser", token).allowed) notFound();

  const teaser = await loadTeaser(inspectionId);
  if (!teaser) notFound();

  return <TeaserView teaser={teaser} />;
}
