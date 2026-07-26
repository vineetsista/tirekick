import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "TIREKICK - automated used-car analysis",
  description:
    "AI analysis of the photos, audio, and VIN of a used car you are considering. " +
    "Evidence-cited findings, stated confidence, and the questions to ask before you buy.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
