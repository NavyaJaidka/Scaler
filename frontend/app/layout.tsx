import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Navya Jaidka — AI Representative",
  description:
    "Talk to my AI persona — ask about my background, projects, GitHub repos, or book an interview.",
  openGraph: {
    title: "Navya Jaidka — AI Representative",
    description: "RAG-grounded AI persona for Scaler AI Engineer screening",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
