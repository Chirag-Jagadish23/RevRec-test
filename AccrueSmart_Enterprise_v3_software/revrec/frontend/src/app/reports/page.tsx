"use client";

import { useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { api } from "@/src/lib/api";
import { Input } from "@/src/components/ui/input";
import { Button } from "@/src/components/ui/button";
import { Card } from "@/src/components/ui/card";
import { toast } from "sonner";

const LockScheduleButton = dynamic(
  () => import("@/src/components/LockScheduleButton"),
  { ssr: false }
);

type GridRow = {
  line_no?: number;
  period: string;
  amount: number;
  product_code?: string;
  product_name?: string;
  revrec_code?: string;
  rule_type?: string;
  source?: string;
  event_type?: string;
  notes?: string;
  is_adjustment?: boolean;
};

export default function ReportsPage() {
  const [contractId, setContractId] = useState("C-TEST");
  const [gridRows, setGridRows] = useState<GridRow[]>([]);
  const [allocResult, setAllocResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  async function loadFromGrid() {
    try {
      setLoading(true);
      const rows = await api(`/schedules/grid/${encodeURIComponent(contractId)}`);

      if (!Array.isArray(rows) || rows.length === 0) {
        setGridRows([]);
        toast.error("No schedule rows found for this contract");
        return;
      }

      setGridRows(rows);
      setAllocResult(null);
      toast.success(`Loaded ${rows.length} schedule rows`);
    } catch (e: any) {
      console.error(e);
      toast.error(e?.message || "Failed to load schedule");
    } finally {
      setLoading(false);
    }
  }

  async function runAllocation() {
    try {
      setLoading(true);

      // Your backend allocate route currently reads contract from DB
      // so it only needs contract_id
      const res = await api("/contracts/allocate", {
        method: "POST",
        body: JSON.stringify({ contract_id: contractId }),
      });

      setAllocResult(res);

      // After allocation, reload the saved grid from backend (source of truth)
      const rows = await api(`/schedules/grid/${encodeURIComponent(contractId)}`);
      setGridRows(Array.isArray(rows) ? rows : []);

      toast.success("Allocation complete");
    } catch (e: any) {
      console.error(e);
      toast.error(e?.message || "Allocation failed");
    } finally {
      setLoading(false);
    }
  }

  const monthlyTotals = useMemo(() => {
    const byPeriod: Record<string, number> = {};
    for (const r of gridRows) {
      byPeriod[r.period] = (byPeriod[r.period] || 0) + Number(r.amount || 0);
    }
    return Object.entries(byPeriod)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([period, amount]) => ({ period, amount }));
  }, [gridRows]);

  const totals = useMemo(() => {
    let recognized = 0;
    let adjustments = 0;

    for (const r of gridRows) {
      const amt = Number(r.amount || 0);
      recognized += amt;

      // adjustment rows may be marked by source or is_adjustment
      if (
        r.is_adjustment ||
        (r.source && r.source.startsWith("adjustment_")) ||
        (r.event_type && r.event_type !== "recognition")
      ) {
        adjustments += amt;
      }
    }

    return {
      recognized,
      adjustments,
      rows: gridRows.length,
    };
  }, [gridRows]);

  // Lock button expects a JSON object; convert monthly totals into {period: amount}
  const lockPayload = useMemo(() => {
    const obj: Record<string, number> = {};
    for (const r of monthlyTotals) obj[r.period] = r.amount;
    return obj;
  }, [monthlyTotals]);

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      <h1 className="text-2xl font-bold">Reports & Schedule Lock</h1>

      <Card className="p-4 space-y-3">
        <h2 className="font-medium text-sm text-gray-700">Load Schedule Data</h2>
        <div className="flex flex-wrap gap-2 items-center">
          <Input
            className="max-w-xs"
            placeholder="Contract ID"
            value={contractId}
            onChange={(e: any) => setContractId(e.target.value)}
          />
          <Button onClick={loadFromGrid} disabled={loading}>
            Load from Grid
          </Button>
          <Button onClick={runAllocation} disabled={loading}>
            Run Allocation
          </Button>
        </div>
      </Card>

      {/* KPI cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="p-4">
          <div className="text-xs text-gray-500">Schedule Rows</div>
          <div className="text-lg font-semibold">{totals.rows}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-gray-500">Total Recognized (Net)</div>
          <div className="text-lg font-semibold">
            ${totals.recognized.toLocaleString(undefined, { maximumFractionDigits: 2 })}
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-gray-500">Adjustments Impact</div>
          <div className="text-lg font-semibold">
            ${totals.adjustments.toLocaleString(undefined, { maximumFractionDigits: 2 })}
          </div>
        </Card>
      </div>

      {/* Monthly summary */}
      {monthlyTotals.length > 0 && (
        <Card className="p-0 overflow-x-auto">
          <div className="p-4 pb-2">
            <h2 className="font-medium text-sm text-gray-700">Monthly Revenue Summary</h2>
          </div>
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="p-2 text-left">Period</th>
                <th className="p-2 text-right">Amount</th>
              </tr>
            </thead>
            <tbody>
              {monthlyTotals.map((r) => (
                <tr key={r.period} className="border-t">
                  <td className="p-2">{r.period}</td>
                  <td className="p-2 text-right">
                    {Number(r.amount).toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {/* Full schedule grid */}
      {gridRows.length > 0 && (
        <Card className="p-0 overflow-x-auto">
          <div className="p-4 pb-2">
            <h2 className="font-medium text-sm text-gray-700">Detailed Schedule Rows</h2>
          </div>
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="p-2 text-left">Period</th>
                <th className="p-2 text-left">Product</th>
                <th className="p-2 text-left">Rule</th>
                <th className="p-2 text-right">Amount</th>
                <th className="p-2 text-left">Source</th>
                <th className="p-2 text-left">Event</th>
                <th className="p-2 text-left">Notes</th>
              </tr>
            </thead>
            <tbody>
              {gridRows.map((r, idx) => (
                <tr key={`${r.period}-${r.product_code || "x"}-${idx}`} className="border-t">
                  <td className="p-2">{r.period}</td>
                  <td className="p-2">{r.product_code || "-"}</td>
                  <td className="p-2">{r.rule_type || r.revrec_code || "-"}</td>
                  <td className="p-2 text-right">
                    {Number(r.amount).toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}
                  </td>
                  <td className="p-2">{r.source || "-"}</td>
                  <td className="p-2">{r.event_type || "recognition"}</td>
                  <td className="p-2">{r.notes || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {/* Lock schedule */}
      {monthlyTotals.length > 0 && (
        <Card className="p-4 space-y-3">
          <h2 className="font-medium text-sm text-gray-700">Lock This Schedule</h2>
          <p className="text-xs text-gray-500">
            Locking creates a tamper-evident hash of the monthly summary JSON.
          </p>
          <LockScheduleButton
            contractId={contractId || "C-TEST"}
            schedule={lockPayload}
            note="Month-end close"
          />
        </Card>
      )}

      {/* Raw allocation debug */}
      {allocResult && (
        <Card className="p-4">
          <h2 className="font-medium text-sm text-gray-700 mb-2">Full Allocation Result</h2>
          <pre className="text-xs bg-slate-50 p-3 rounded border overflow-x-auto">
            {JSON.stringify(allocResult, null, 2)}
          </pre>
        </Card>
      )}
    </div>
  );
}
