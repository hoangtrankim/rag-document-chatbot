import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DocChat · Ask your PDFs",
  description: "Upload PDFs and get answers with sources, powered by Claude and LangChain.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
