import type { Metadata } from "next";
import { cookies } from "next/headers";
import { notFound } from "next/navigation";
import { PurchaseGate } from "@/components/PurchaseGate";
import { canRead, grantCookieName, isPubliclyReadable } from "@/lib/access";
import { loadTeaser } from "@/lib/inspections";
import { isValidInspectionId } from "@/lib/media";
import { demoTeaser } from "@/lib/report";

/**
 * The checkout for an uploaded inspection. Reaching it takes the same teaser
 * tier as the teaser itself: the page shows the sample finding and the
 * vehicle's identity, and a stranger who cannot read the teaser has no
 * business at its checkout either.
 */

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "TIREKICK - before you buy",
  description: "What you are buying, what it is not, and what has been measured.",
  robots: { index: false, follow: false },
};

export default async function BuyPage({
  params,
}: {
  params: Promise<{ inspectionId: string }>;
}) {
  const { inspectionId } = await params;
  if (!isValidInspectionId(inspectionId)) notFound();

  if (isPubliclyReadable(inspectionId)) {
    return <PurchaseGate teaser={demoTeaser} />;
  }

  const token = (await cookies()).get(grantCookieName(inspectionId))?.value;
  if (!canRead(inspectionId, "teaser", token).allowed) notFound();

  const teaser = await loadTeaser(inspectionId);
  if (!teaser) notFound();

  return <PurchaseGate teaser={teaser} />;
}
