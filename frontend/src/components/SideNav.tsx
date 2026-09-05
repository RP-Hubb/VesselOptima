"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";

/**
 * Left navigation rail — compact, persistent.
 * Navigation items from Build Spec Section W:
 *   Market, Forecast, Optimizer, Scenarios, Ports,
 *   Backtest, Risk, Data, Audit, Idle & Employment
 *
 * Most pages are placeholders until later phases.
 */

const NAV_ITEMS = [
  { label: "Market", href: "/", shortcut: "01" },
  { label: "Forecast", href: "/forecast", shortcut: "02" },
  { label: "Feasibility", href: "/feasibility", shortcut: "03" },
  { label: "Procurement", href: "/procurement", shortcut: "04" },
  { label: "Optimizer", href: "/optimizer", shortcut: "05" },
  { label: "Idle & Emp", href: "/employment", shortcut: "06" },
  { label: "Scenarios", href: "/scenarios", shortcut: "07" },
  { label: "Ports", href: "/ports", shortcut: "08" },
  { label: "Backtest", href: "/backtest", shortcut: "09" },
  { label: "Risk", href: "/risk", shortcut: "10" },
  { label: "Data", href: "/data", shortcut: "11" },
  { label: "Audit", href: "/audit", shortcut: "12" },
];

export default function SideNav() {
  const pathname = usePathname();

  return (
    <nav
      style={{
        width: "160px",
        minWidth: "160px",
        background: "var(--surface-1)",
        borderRight: "1px solid var(--border)",
        padding: "var(--space-2) 0",
        display: "flex",
        flexDirection: "column",
        fontSize: "0.8125rem",
        overflowY: "auto",
      }}
      aria-label="Main navigation"
    >
      {NAV_ITEMS.map((item) => {
        const isActive = pathname === item.href;
        return (
          <Link
            key={item.href}
            href={item.href}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--space-2)",
              padding: "var(--space-2) var(--space-3)",
              color: isActive ? "var(--text)" : "var(--muted)",
              background: isActive ? "var(--surface-2)" : "transparent",
              borderLeft: isActive ? "2px solid var(--info)" : "2px solid transparent",
              textDecoration: "none",
              transition: "background 120ms ease",
            }}
          >
            <span
              className="tabular-nums"
              style={{ fontSize: "0.6875rem", color: "var(--muted)", width: "16px" }}
            >
              {item.shortcut}
            </span>
            <span>{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
