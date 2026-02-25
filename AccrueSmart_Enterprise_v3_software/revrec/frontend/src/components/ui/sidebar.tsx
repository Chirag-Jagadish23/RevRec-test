"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Home,
  FileText,
  ScanText,
  Bot,
  Shapes,
  Package,
  Table,
  FileChartColumn,
  FileSpreadsheet,
  TrendingDown,
  Calculator,
  TrendingUp,
  ShieldCheck,
  CalendarCheck2,
  type LucideIcon,
} from "lucide-react";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

const items: NavItem[] = [
  { href: "/", label: "Home", icon: Home },
  { href: "/contracts", label: "Contracts", icon: FileText },
  { href: "/viewer", label: "PDF Viewer", icon: ScanText },
  { href: "/negotiation", label: "Deal Desk AI", icon: Bot },

  // ✅ Add Close Dashboard here
  { href: "/close", label: "Close Dashboard", icon: CalendarCheck2 },

  { href: "/revrec_codes", label: "RevRec Codes", icon: Shapes },
  { href: "/catalog", label: "Product Catalog", icon: Package },
  { href: "/schedules/editor", label: "Schedules (Grid)", icon: Table },
  { href: "/costs", label: "Costs (ASC 340-40)", icon: TrendingDown },
  { href: "/reports", label: "Reports", icon: FileChartColumn },
  { href: "/leases", label: "Leases", icon: FileSpreadsheet },
  { href: "/tax", label: "ASC 740", icon: Calculator },
  { href: "/forecast", label: "Forecast", icon: TrendingUp },
  { href: "/auditor", label: "AI Auditor", icon: ShieldCheck },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-56 shrink-0 bg-white border-r min-h-screen flex flex-col">
      <div className="px-4 py-4 border-b font-semibold text-sm tracking-wide text-slate-700">
        AccrueSmart v3
      </div>
      <nav className="flex-1 py-2">
        {items.map((item) => {
          const Icon = item.icon;
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);

          return (
            <Link
              key={item.href}
              href={item.href}
              className={
                "flex items-center gap-3 px-4 py-2 text-sm transition-colors " +
                (active
                  ? "bg-slate-100 text-slate-900 font-medium"
                  : "text-slate-600 hover:bg-slate-50 hover:text-slate-900")
              }
            >
              <Icon size={18} />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
