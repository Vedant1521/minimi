import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Minimi | Search-Grounded Agent with Temporal Memory",
  description: "High-performance conversational agent featuring single-tool web search and cross-session temporal memory.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-slate-950 text-slate-100 antialiased flex flex-col">
        {children}
      </body>
    </html>
  );
}
