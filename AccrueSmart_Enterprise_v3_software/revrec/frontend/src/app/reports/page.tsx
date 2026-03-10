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
  const [loading, setLoading] = useState(false);

  // Disclosure Package state
  const [discFiscalYear, setDiscFiscalYear] = useState(new Date().getFullYear().toString());
  const [discAsOfDate, setDiscAsOfDate] = useState(
    new Date().toISOString().slice(0, 10)
  );
  const [discLoading, setDiscLoading] = useState(false);

  async function generateDisclosurePack() {
    const year = parseInt(discFiscalYear, 10);
    if (!year || year < 2000 || year > 2100) {
      toast.error("Enter a valid fiscal year (e.g. 2025)");
      return;
    }
    if (!discAsOfDate) {
      toast.error("Select an as-of date");
      return;
    }
    try {
      setDiscLoading(true);
      const params = new URLSearchParams({
        fiscal_year: year.toString(),
        as_of_date: discAsOfDate,
      });
      // Fetch the PDF as a blob and trigger browser download
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/reports/disclosure-pack?${params}`
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.detail || `Server error ${res.status}`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `ASC606_Disclosure_FY${year}_${discAsOfDate}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success(`Disclosure package downloaded for FY ${year}`);
    } catch (e: any) {
      toast.error(e?.message || "Failed to generate disclosure package");
    } finally {
      setDiscLoading(false);
    }
  }

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
      toast.success(`Loaded ${rows.length} schedule rows`);
    } catch (e: any) {
      console.error(e);
      toast.error(e?.message || "Failed to load schedule");
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

      {/* ── Disclosure Package ─────────────────────────────────── */}
      <Card className="p-4 space-y-3 border-blue-200 bg-blue-50">
        <div>
          <h2 className="font-semibold text-blue-900">ASC 606 Disclosure Package</h2>
          <p className="text-xs text-blue-700 mt-0.5">
            Generates a PDF with revenue disaggregation, deferred revenue rollforward,
            and remaining performance obligations (RPO).
          </p>
        </div>
        <div className="flex flex-wrap gap-3 items-end">
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-600">Fiscal Year</label>
            <Input
              type="number"
              className="w-28"
              value={discFiscalYear}
              onChange={(e: any) => setDiscFiscalYear(e.target.value)}
              min={2000}
              max={2100}
              placeholder="2025"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-600">As-of Date</label>
            <Input
              type="date"
              className="w-40"
              value={discAsOfDate}
              onChange={(e: any) => setDiscAsOfDate(e.target.value)}
            />
          </div>
          <Button
            onClick={generateDisclosurePack}
            disabled={discLoading}
            className="bg-blue-700 hover:bg-blue-800 text-white"
          >
            {discLoading ? "Generating…" : "Generate Disclosure Package (PDF)"}
          </Button>
        </div>
      </Card>

      {/* ── Schedule section ───────────────────────────────────── */}
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


    </div>
  );
}
