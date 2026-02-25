"use client";

import { usePathname } from "next/navigation";
import AppSidebar from "@/src/components/AppSidebar";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() || "/";
  const hideSidebar = pathname === "/login";

  if (hideSidebar) {
    return <main className="min-h-screen bg-gray-50">{children}</main>;
  }

  return (
    <div className="flex min-h-screen">
      <AppSidebar />
      <main className="flex-1 bg-gray-50">
        <div className="p-6">{children}</div>
      </main>
    </div>
  );
}
