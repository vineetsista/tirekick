import type { Metadata } from "next";
import { TeaserView } from "@/components/TeaserView";
import { demoTeaser } from "@/lib/report";

export const metadata: Metadata = {
  title: "TIREKICK - free result",
  description:
    "What TIREKICK found in the media provided, what it could not assess, and what the full report adds.",
};

export default function TeaserPage() {
  return <TeaserView teaser={demoTeaser} />;
}
