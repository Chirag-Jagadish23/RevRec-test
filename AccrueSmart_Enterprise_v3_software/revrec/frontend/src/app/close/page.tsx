// frontend/src/app/close/page.tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/src/lib/api";
import { Button, Card, Input } from "@/src/components/ui";

type CloseTask = {
  task_id: string;
  title: string;
  day_bucket: "D+1" | "D+2" | "D+3";
  owner_role?: string;
  owner?: string;
  status: "done" | "pending";
  status_reason?: string;
};

type Blocker = {
  task_id: string;
  task_title: string;
  blocked_by_task_id: string;
  blocked_by_title: string;
  owner?: string;
  severity: "high" | "medium" | "low";
};

type CloseDashboardResponse = {
  status: string;
  period_key: string;
  entity_id: string;
  system_state: Record<string, any>;
  dependencies: { task_id: string; depends_on: string }[];
  tasks: CloseTask[];
  by_day: {
    "D+1": CloseTask[];
    "D+2": CloseTask[];
    "D+3": CloseTask[];
  };
  blockers: Blocker[];
  ai_close_manager_summary: string;
};

type ClosePackageResponse = {
  status: string;
  period_key: string;
  entity_id: string;
  rollforwards: Record<string, any>;
  exception_summary: Record<string, any>;
  memo: string;
  source_refs: { source: string; present: boolean; count: number }[];
  audit_trail_extracts: { row: any }[];
};

export default function ClosePage() {
  const [periodKey, setPeriodKey] = useState("2026-01");
  const [entityId, setEntityId] = useState("US_PARENT");

  const [loading, setLoading] = useState(false);
  const [pkgLoading, setPkgLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [dashboard, setDashboard] = useState<CloseDashboardResponse | null>(null);
  const [closePackage, setClosePackage] = useState<ClosePackageResponse | null>(null);

  // local editable owner assignments (UI-side for now)
  const [ownerOverrides, setOwnerOverrides] = useState<Record<string, string>>({});

  async function loadDashboard() {
    setLoading(true);
    setError(null);
    try {
      const res = await api(
        `/close/dashboard?period_key=${encodeURIComponent(periodKey)}&entity_id=${encodeURIComponent(entityId)}`
      );
      setDashboard(res);
      setClosePackage(null); // reset package when refreshing dashboard
    } catch (e: any) {
      setError(e?.message || "Failed to load close dashboard.");
    } finally {
      setLoading(false);
    }
  }

  async function generatePackage() {
    setPkgLoading(true);
    setError(null);
    try {
      const res = await api("/close/package/generate", {
        method: "POST",
        body: JSON.stringify({
          period_key: periodKey,
          entity_id: entityId,
        }),
      });
      setClosePackage(res);
    } catch (e: any) {
      setError(e?.message || "Failed to generate close package.");
    } finally {
      setPkgLoading(false);
    }
  }

  useEffect(() => {
    loadDashboard();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const tasksWithOwners = useMemo(() => {
    if (!dashboard?.tasks) return [];
    return dashboard.tasks.map((t) => ({
      ...t,
      owner: ownerOverrides[t.task_id] ?? t.owner ?? t.owner_role ?? "",
    }));
  }, [dashboard, ownerOverrides]);

  const byDay = useMemo(() => {
    const groups: Record<string, CloseTask[]> = { "D+1": [], "D+2": [], "D+3": [] };
    for (const t of tasksWithOwners) {
      groups[t.day_bucket] = groups[t.day_bucket] || [];
      groups[t.day_bucket].push(t);
    }
    return groups as { "D+1": CloseTask[]; "D+2": CloseTask[]; "D+3": CloseTask[] };
  }, [tasksWithOwners]);

  const blockersWithOwners = useMemo(() => {
    const taskOwnerMap = new Map(tasksWithOwners.map((t) => [t.task_id, t.owner]));
    return (dashboard?.blockers || []).map((b) => ({
      ...b,
      owner: taskOwnerMap.get(b.task_id) || b.owner || "",
    }));
  }, [dashboard, tasksWithOwners]);

  function patchOwner(taskId: string, owner: string) {
    setOwnerOverrides((prev) => ({ ...prev, [taskId]: owner }));
  }

  const doneCount = tasksWithOwners.filter((t) => t.status === "done").length;
  const totalCount = tasksWithOwners.length;
  const completionPct = totalCount > 0 ? Math.round((doneCount / totalCount) * 100) : 0;

  return (
    <div className="max-w-7xl mx-auto space-y-4">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Close Dashboard</h1>
          <p className="text-sm text-gray-500">
            Day-by-day close orchestration with auto-status from actual system state
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button onClick={loadDashboard} disabled={loading}>
            {loading ? "Refreshing..." : "Refresh Close Status"}
          </Button>
          <Button variant="outline" onClick={generatePackage} disabled={pkgLoading}>
            {pkgLoading ? "Generating..." : "Generate Close Package"}
          </Button>
        </div>
      </div>

      {/* Controls */}
      <Card className="p-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div>
            <div className="text-xs text-gray-500 mb-1">Period Key</div>
            <Input
              value={periodKey}
              onChange={(e: any) => setPeriodKey(e.target.value)}
              placeholder="2026-01"
            />
          </div>

          <div>
            <div className="text-xs text-gray-500 mb-1">Entity</div>
            <select
              className="w-full border rounded px-2 py-2 text-sm bg-white"
              value={entityId}
              onChange={(e) => setEntityId(e.target.value)}
            >
              <option value="US_PARENT">US Parent</option>
              <option value="SUB_001">Subsidiary 001</option>
              <option value="SUB_002">Subsidiary 002</option>
            </select>
          </div>

          <div>
            <div className="text-xs text-gray-500 mb-1">Close Completion</div>
            <div className="h-10 rounded border bg-white px-3 flex items-center justify-between text-sm">
              <span>{doneCount}/{totalCount} tasks done</span>
              <span className="font-medium">{completionPct}%</span>
            </div>
          </div>
        </div>
      </Card>

      {error && <div className="text-sm text-red-600">{error}</div>}

      {/* AI Close Manager banner */}
      {dashboard && (
        <Card className="p-4 border-slate-300 bg-slate-50">
          <div className="text-xs uppercase tracking-wide text-gray-500 mb-1">AI Close Manager</div>
          <div className="text-sm">{dashboard.ai_close_manager_summary}</div>
        </Card>
      )}

      {/* System state */}
      {dashboard?.system_state && (
        <Card className="p-4">
          <div className="font-medium mb-3">Auto-Status from Actual System State</div>
          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-3 text-sm">
            {[
              ["Contracts Posted", dashboard.system_state.contracts_posted, dashboard.system_state.contracts_posted_count],
              ["RevRec Schedules", dashboard.system_state.revrec_schedules_exist, dashboard.system_state.revrec_schedules_count],
              ["Commissions Run", dashboard.system_state.commissions_run, dashboard.system_state.commissions_count],
              ["Leases Run", dashboard.system_state.leases_run, dashboard.system_state.leases_count],
              ["Depreciation Run", dashboard.system_state.depreciation_run, dashboard.system_state.fixed_assets_count],
              ["Tax Complete", dashboard.system_state.tax_complete, dashboard.system_state.tax_rows_count],
              ["GL Batches", (dashboard.system_state.gl_batches_count || 0) > 0, dashboard.system_state.gl_batches_count],
              ["Period Locked", dashboard.system_state.period_locked, null],
            ].map(([label, ok, count]) => (
              <Card key={String(label)} className="p-3">
                <div className="text-xs text-gray-500">{String(label)}</div>
                <div className="mt-1 flex items-center justify-between">
                  <span
                    className={`text-xs rounded px-2 py-0.5 border ${
                      ok
                        ? "bg-green-50 text-green-700 border-green-200"
                        : "bg-yellow-50 text-yellow-700 border-yellow-200"
                    }`}
                  >
                    {ok ? "Complete" : "Pending"}
                  </span>
                  {typeof count === "number" && <span className="font-medium">{count}</span>}
                </div>
              </Card>
            ))}
          </div>
        </Card>
      )}

      {/* D+1 / D+2 / D+3 columns */}
      {dashboard && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {(["D+1", "D+2", "D+3"] as const).map((bucket) => (
            <Card key={bucket} className="p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="font-medium">{bucket}</div>
                <span className="text-xs text-gray-500">{byDay[bucket]?.length || 0} tasks</span>
              </div>

              <div className="space-y-3">
                {(byDay[bucket] || []).map((task) => (
                  <div key={task.task_id} className="border rounded p-3 space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="text-sm font-medium">{task.title}</div>
                        <div className="text-xs text-gray-500">{task.task_id}</div>
                      </div>
                      <span
                        className={`text-xs rounded px-2 py-0.5 border ${
                          task.status === "done"
                            ? "bg-green-50 text-green-700 border-green-200"
                            : "bg-gray-50 text-gray-700 border-gray-200"
                        }`}
                      >
                        {task.status}
                      </span>
                    </div>

                    <div>
                      <div className="text-xs text-gray-500 mb-1">Owner Assignment</div>
                      <Input
                        value={task.owner || ""}
                        onChange={(e: any) => patchOwner(task.task_id, e.target.value)}
                        placeholder={task.owner_role || "Assign owner"}
                      />
                    </div>

                    <div className="text-xs text-gray-600">{task.status_reason}</div>
                  </div>
                ))}

                {!byDay[bucket]?.length && (
                  <div className="text-sm text-gray-500">No tasks in {bucket}.</div>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Blockers */}
      {dashboard && (
        <Card className="p-4">
          <div className="font-medium mb-3">Blockers</div>
          {blockersWithOwners.length ? (
            <div className="space-y-2">
              {blockersWithOwners.map((b, i) => (
                <div key={`${b.task_id}-${i}`} className="border rounded p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="text-sm font-medium">{b.task_title}</div>
                    <span
                      className={`text-xs rounded px-2 py-0.5 border ${
                        b.severity === "high"
                          ? "bg-red-50 text-red-700 border-red-200"
                          : "bg-yellow-50 text-yellow-700 border-yellow-200"
                      }`}
                    >
                      {b.severity}
                    </span>
                  </div>
                  <div className="text-xs text-gray-600 mt-1">
                    Blocked by: <span className="font-medium">{b.blocked_by_title}</span>
                  </div>
                  <div className="text-xs text-gray-600">
                    Owner: <span className="font-medium">{b.owner || "Unassigned"}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-sm text-gray-500">No blockers detected.</div>
          )}
        </Card>
      )}

      {/* Close Package Output */}
      {closePackage && (
        <>
          <Card className="p-4">
            <div className="font-medium mb-2">Period Close Package Memo</div>
            <pre className="whitespace-pre-wrap text-sm bg-slate-50 border rounded p-3">
              {closePackage.memo}
            </pre>
          </Card>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card className="p-4">
              <div className="font-medium mb-2">Rollforwards</div>
              <pre className="whitespace-pre-wrap text-xs bg-slate-50 border rounded p-3">
                {JSON.stringify(closePackage.rollforwards, null, 2)}
              </pre>
            </Card>

            <Card className="p-4">
              <div className="font-medium mb-2">Exception Summary</div>
              <pre className="whitespace-pre-wrap text-xs bg-slate-50 border rounded p-3">
                {JSON.stringify(closePackage.exception_summary, null, 2)}
              </pre>
            </Card>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card className="p-4">
              <div className="font-medium mb-2">Source References</div>
              <div className="space-y-2 text-sm">
                {(closePackage.source_refs || []).map((s) => (
                  <div key={s.source} className="flex items-center justify-between border rounded p-2">
                    <div>{s.source}</div>
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-xs rounded px-2 py-0.5 border ${
                          s.present
                            ? "bg-green-50 text-green-700 border-green-200"
                            : "bg-gray-50 text-gray-700 border-gray-200"
                        }`}
                      >
                        {s.present ? "present" : "missing"}
                      </span>
                      <span className="font-medium">{s.count}</span>
                    </div>
                  </div>
                ))}
              </div>
            </Card>

            <Card className="p-4">
              <div className="font-medium mb-2">Audit Trail Extracts (Preview)</div>
              {(closePackage.audit_trail_extracts || []).length ? (
                <pre className="whitespace-pre-wrap text-xs bg-slate-50 border rounded p-3 max-h-80 overflow-auto">
                  {JSON.stringify(closePackage.audit_trail_extracts.slice(0, 10), null, 2)}
                </pre>
              ) : (
                <div className="text-sm text-gray-500">No audit log rows found yet.</div>
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
