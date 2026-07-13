import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MAD Engine 2.0 - Multi-Agent Debate & Synthesis Suite",
  description: "Advanced Agentic Coding & Architectural Blueprint Synthesis",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased bg-[#090d16] text-slate-100 font-sans">
        {children}
      </body>
    </html>
  );
}
