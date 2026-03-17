import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "GetVul",
  description: "Unified Vulnerability Aggregation Platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
