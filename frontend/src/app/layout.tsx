import type { Metadata } from "next";
import "./globals.css";
import TerminalHeader from "@/components/TerminalHeader";
import SideNav from "@/components/SideNav";

export const metadata: Metadata = {
  title: "VesselOptima — Freight Intelligence Terminal",
  description:
    "Integrated freight intelligence, chartering feasibility, and procurement optimization platform for bulk-cargo logistics. SIH26006.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            height: "100vh",
            overflow: "hidden",
          }}
        >
          {/* Terminal header — always visible */}
          <TerminalHeader />

          {/* Main workspace: side nav + content */}
          <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
            <SideNav />
            <main
              style={{
                flex: 1,
                overflow: "auto",
                padding: "var(--space-4)",
                background: "var(--bg)",
              }}
            >
              {children}
            </main>
          </div>
        </div>
      </body>
    </html>
  );
}
