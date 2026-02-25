"use client";

import Link from "next/link";
import { Card } from "@/src/components/ui";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useWorkspace } from "@/src/components/providers/WorkspaceProvider";

const modules = [
  { name: "Contracts", href: "/contracts", desc: "Create and manage customer contracts", group: "Revenue" },
  { name: "Catalog", href: "/catalog", desc: "Products, SSPs, and pricing inputs", group: "Revenue" },
  { name: "RevRec Codes", href: "/revrec_codes", desc: "Revenue recognition logic setup", group: "Revenue" },
  { name: "Schedule Editor", href: "/schedules/editor", desc: "Review and adjust rev rec schedules", group: "Revenue" },
  { name: "Reports", href: "/reports", desc: "Revenue and compliance reporting", group: "Revenue" },

  { name: "Costs (ASC 340)", href: "/costs", desc: "Contract cost capitalization", group: "Accounting" },
  { name: "Deferred Commissions", href: "/commissions", desc: "ASC 340-40 commission amortization", group: "Accounting" },
  { name: "Leases (ASC 842)", href: "/leases", desc: "Lease schedules and interest amortization", group: "Accounting" },
  { name: "Tax (ASC 740)", href: "/tax", desc: "Deferred tax calculations and memo", group: "Accounting" },
  { name: "Fixed Assets", href: "/fixed-assets", desc: "Depreciation schedules and journals", group: "Accounting" },
  { name: "Equity (ASC 718)", href: "/equity", desc: "Stock comp workflows and schedules", group: "Accounting" },
  { name: "Intercompany", href: "/intercompany", desc: "Intercompany balances and eliminations", group: "Accounting" },
  { name: "Audit Log", href: "/audit-log", desc: "Read-only change history and controls", group: "Accounting" },

  { name: "Viewer", href: "/viewer", desc: "Upload/view CSV and PDFs", group: "AI" },
  { name: "Forecast AI", href: "/forecast", desc: "Revenue forecasting workflows", group: "AI" },
  { name: "AI Auditor", href: "/auditor", desc: "Cross-module audit summary", group: "AI" },
  { name: "Deal Desk AI", href: "/negotiation", desc: "Deal review and risk analysis", group: "AI" },
  { name: "Close Dashboard", href: "/close", desc: "Day-by-day close orchestration and blockers", group: "AI" },
];

function GroupSection({ title, items }: { title: string; items: typeof modules }) {
  return (
    <div className="space-y-3">
      <div className="text-sm font-semibold text-gray-700">{title}</div>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
        {items.map((m) => (
          <Link key={m.href} href={m.href}>
            <Card className="p-4 h-full hover:shadow-sm transition border hover:border-gray-300 cursor-pointer">
              <div className="font-medium text-sm">{m.name}</div>
              <div className="text-xs text-gray-500 mt-1">{m.desc}</div>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const { companyName, isLoggedIn, isHydrated } = useWorkspace();

  useEffect(() => {
    if (isHydrated && !isLoggedIn) {
      router.replace("/login");
    }
  }, [isHydrated, isLoggedIn, router]);

  if (!isHydrated) return null;
  if (!isLoggedIn) return null;

  const revenue = modules.filter((m) => m.group === "Revenue");
  const accounting = modules.filter((m) => m.group === "Accounting");
  const ai = modules.filter((m) => m.group === "AI");

  return (
    <div className="max-w-7xl mx-auto p-4 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-sm text-gray-500 mt-1">
          AccrueSmart Enterprise Revenue, Close & Compliance OS
        </p>
      </div>

      {/* Summary cards (clickable) */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <Card className="p-4">
          <div className="text-xs text-gray-500">Workspace</div>
          <div className="text-lg font-semibold">{companyName}</div>
        </Card>

        <Link href="/contracts">
          <Card className="p-4 hover:shadow-sm transition border hover:border-gray-300 cursor-pointer">
            <div className="text-xs text-gray-500">Revenue Modules</div>
            <div className="text-lg font-semibold">{revenue.length}</div>
          </Card>
        </Link>

        <Link href="/costs">
          <Card className="p-4 hover:shadow-sm transition border hover:border-gray-300 cursor-pointer">
            <div className="text-xs text-gray-500">Accounting Modules</div>
            <div className="text-lg font-semibold">{accounting.length}</div>
          </Card>
        </Link>

        <Link href="/negotiation">
          <Card className="p-4 hover:shadow-sm transition border hover:border-gray-300 cursor-pointer">
            <div className="text-xs text-gray-500">AI Tools</div>
            <div className="text-lg font-semibold">{ai.length}</div>
          </Card>
        </Link>
      </div>

      {/* Quick actions */}
      <Card className="p-4">
        <div className="font-medium mb-3">Quick Actions</div>
        <div className="flex flex-wrap gap-2">
          <Link href="/contracts" className="px-3 py-2 rounded border text-sm hover:bg-gray-50">
            New Contract
          </Link>

          <Link href="/negotiation" className="px-3 py-2 rounded border text-sm hover:bg-gray-50">
            Run Deal Desk AI
          </Link>

          <Link href="/close" className="px-3 py-2 rounded border text-sm hover:bg-gray-50">
            Open Close Dashboard
          </Link>

          <Link href="/fixed-assets" className="px-3 py-2 rounded border text-sm hover:bg-gray-50">
            Run Depreciation
          </Link>

          <Link href="/tax" className="px-3 py-2 rounded border text-sm hover:bg-gray-50">
            Run ASC 740
          </Link>

          <Link href="/leases" className="px-3 py-2 rounded border text-sm hover:bg-gray-50">
            Build Lease Schedule
          </Link>

          <Link href="/auditor" className="px-3 py-2 rounded border text-sm hover:bg-gray-50">
            Run AI Audit
          </Link>
        </div>
      </Card>

      {/* Module sections */}
      <div id="revenue">
        <GroupSection title="Revenue" items={revenue} />
      </div>

      <div id="accounting">
        <GroupSection title="Accounting" items={accounting} />
      </div>

      <div id="ai-tools">
        <GroupSection title="AI Tools" items={ai} />
      </div>

      {/* System status + recent activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card className="p-4">
          <div className="font-medium mb-2">System Status</div>
          <ul className="text-sm space-y-2">
            <li className="flex items-center justify-between">
              <span>Frontend</span>
              <span className="text-green-600">Running</span>
            </li>
            <li className="flex items-center justify-between">
              <span>Backend API</span>
              <span className="text-green-600">Connected</span>
            </li>
            <li className="flex items-center justify-between">
              <span>Database</span>
              <span className="text-green-600">Local SQLite</span>
            </li>
          </ul>
        </Card>

        <Card className="p-4">
          <div className="font-medium mb-2">Recent Activity</div>
          <div className="text-sm text-gray-500">
            No recent activity yet. Once you save contracts, run schedules, generate close packages,
            or run audits, you can surface them here.
          </div>
        </Card>
      </div>
    </div>
  );
}
