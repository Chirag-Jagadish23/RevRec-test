"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useWorkspace } from "@/src/components/providers/WorkspaceProvider";

type NavItem = {
  label: string;
  href: string;
  badge?: string;
};

type NavSection = {
  title: string;
  items: NavItem[];
};

const NAV_SECTIONS: NavSection[] = [
  {
    title: "Revenue",
    items: [
      { label: "Contracts", href: "/contracts" },
      { label: "Catalog", href: "/catalog" },
      { label: "RevRec Codes", href: "/revrec_codes" },
      { label: "Schedule Editor", href: "/schedules/editor" },
      { label: "Reports", href: "/reports" },
    ],
  },
  {
    title: "Accounting",
    items: [
      { label: "Costs (ASC 340)", href: "/costs" },
      { label: "Deferred Commissions (ASC 340-40)", href: "/commissions" },
      { label: "Leases (ASC 842)", href: "/leases" },
      { label: "Tax (ASC 740)", href: "/tax" },
      { label: "Fixed Assets", href: "/fixed-assets" },
      { label: "Equity (ASC 718)", href: "/equity" },
      { label: "Intercompany", href: "/intercompany" },
      { label: "Audit Log", href: "/audit-log" },
    ],
  },
  {
    title: "AI Tools",
    items: [
      { label: "Viewer", href: "/viewer", badge: "AI" },
      { label: "Forecast AI", href: "/forecast", badge: "AI" },
      { label: "AI Auditor", href: "/auditor", badge: "AI" },
      { label: "Deal Desk AI", href: "/negotiation", badge: "AI" },
      { label: "Close Dashboard", href: "/close", badge: "AI" },
    ],
  },
  {
    title: "General",
    items: [{ label: "Dashboard", href: "/" }],
  },
];

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(href + "/");
}

export default function AppSidebar() {
  const pathname = usePathname() || "/";
  const router = useRouter();
  const { companyName, logout, setCompanyName } = useWorkspace();

  const handleLogout = () => {
    logout();
    router.replace("/login");
  };

  const handleRename = () => {
    const next = window.prompt("Enter new workspace name", companyName || "");
    if (next && next.trim()) {
      setCompanyName(next.trim());
    }
  };

  return (
    <aside className="w-72 min-h-screen border-r bg-white flex flex-col">
      <div className="border-b px-4 py-4">
        <div className="text-lg font-semibold tracking-tight">AccrueSmart</div>
        <div className="text-xs text-gray-500">Enterprise Revenue & Compliance OS</div>
      </div>

      <div className="px-4 py-3 border-b">
        <div className="rounded-lg border bg-gray-50 px-3 py-2">
          <div className="text-xs text-gray-500">Workspace</div>
          <div className="text-sm font-medium">{companyName}</div>

          <div className="mt-2 flex gap-2">
            <button
              onClick={handleRename}
              className="text-xs px-2 py-1 rounded border hover:bg-white"
              type="button"
            >
              Edit name
            </button>
            <button
              onClick={handleLogout}
              className="text-xs px-2 py-1 rounded border hover:bg-white"
              type="button"
            >
              Logout
            </button>
          </div>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-3 space-y-4">
        {NAV_SECTIONS.map((section) => (
          <div key={section.title}>
            <div className="px-2 pb-1 text-[11px] uppercase tracking-wide text-gray-500 font-medium">
              {section.title}
            </div>

            <div className="space-y-1">
              {section.items.map((item) => {
                const active = isActive(pathname, item.href);

                return (
                  <Link
                    key={`${section.title}-${item.href}-${item.label}`}
                    href={item.href}
                    className={`group flex items-center justify-between rounded-md px-3 py-2 text-sm transition ${
                      active ? "bg-gray-900 text-white" : "text-gray-700 hover:bg-gray-100"
                    }`}
                  >
                    <span className="truncate">{item.label}</span>

                    {item.badge && (
                      <span
                        className={`ml-2 rounded px-1.5 py-0.5 text-[10px] font-medium ${
                          active ? "bg-white/20 text-white" : "bg-gray-200 text-gray-700"
                        }`}
                      >
                        {item.badge}
                      </span>
                    )}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="border-t px-4 py-3">
        <div className="text-xs text-gray-500">Status</div>
        <div className="flex items-center gap-2 text-sm">
          <span className="inline-block h-2 w-2 rounded-full bg-green-500" />
          Local dev running
        </div>
      </div>
    </aside>
  );
}
