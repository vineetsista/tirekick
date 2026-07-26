import type { Metadata } from "next";
import { ReportView } from "@/components/ReportView";
import { demoReport } from "@/lib/report";

export const metadata: Metadata = {
  title: "TIREKICK report - demo-01 (synthetic fixture)",
  description:
    "A TIREKICK dossier rendered from synthetic fixture media. Not a real vehicle.",
};

export default function DemoReportPage() {
  return <ReportView report={demoReport} />;
}
