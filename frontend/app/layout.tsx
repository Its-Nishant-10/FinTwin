import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FinTwin",
  description:
    "Explainable AI personal finance intelligence and simulation. Research prototype.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
