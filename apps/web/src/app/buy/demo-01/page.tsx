import type { Metadata } from "next";
import { PurchaseGate } from "@/components/PurchaseGate";
import { demoTeaser } from "@/lib/report";

export const metadata: Metadata = {
  title: "TIREKICK - before you buy",
  description: "What you are buying, what it is not, and what has been measured.",
};

export default function BuyPage() {
  return <PurchaseGate teaser={demoTeaser} />;
}
