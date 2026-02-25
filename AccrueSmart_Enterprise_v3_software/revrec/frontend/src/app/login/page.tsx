"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Card } from "@/src/components/ui";
import { useWorkspace } from "@/src/components/providers/WorkspaceProvider";

export default function LoginPage() {
  const router = useRouter();
  const { login, isLoggedIn, companyName } = useWorkspace();

  const [name, setName] = useState(companyName || "");

  useEffect(() => {
    if (isLoggedIn) {
      router.replace("/");
    }
  }, [isLoggedIn, router]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    login(name);
    router.replace("/");
  };

  return (
    <div className="min-h-[calc(100vh-3rem)] flex items-center justify-center p-4">
      <Card className="w-full max-w-md p-6 border shadow-sm">
        <div className="mb-5">
          <h1 className="text-2xl font-semibold tracking-tight">Welcome to AccrueSmart</h1>
          <p className="text-sm text-gray-500 mt-1">
            Enter your workspace name to continue.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="companyName"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Company / Workspace Name
            </label>
            <input
              id="companyName"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Fintra Finance, Foundry, DemoCo Finance"
              className="w-full rounded-md border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-gray-300"
              autoFocus
            />
          </div>

          <button
            type="submit"
            className="w-full rounded-md bg-gray-900 text-white text-sm font-medium py-2.5 hover:bg-black transition"
          >
            Continue
          </button>
        </form>

        <div className="mt-4 text-xs text-gray-500">
          This is a local workspace login for development. Your workspace name is saved in your browser.
        </div>
      </Card>
    </div>
  );
}
