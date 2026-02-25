"use client";

import { useEffect, useMemo, useState } from "react";
import { api, API_BASE } from "@/src/lib/api";
import { Input } from "@/src/components/ui/input";
import { Button } from "@/src/components/ui/button";
import { Card } from "@/src/components/ui/card";
import { toast } from "sonner";

type GridRow = {
  line_no?: number;
  period: string;
  amount: number;
  product_code?: string;
  product_name?: string;
  ssp?: number;
  revrec_code?: string;
  rule_type?: string;
  source?: string;

  // optional audit fields (if backend/model has them)
  event_type?: string;
  notes?: string;
  effective_date?: string;
  is_adjustment?: boolean;
};

type AdjustmentType = "refund" | "delay" | "true_up";

export default function ScheduleEditorPage() {
  const [cid, setCid] = useState("C-TEST");
  const [rows, setRows] = useState<GridRow[]>([]);
  const [file, setFile] = useState<File | null>(null);

  // Adjustment form state
  const [adjType, setAdjType] = useState<AdjustmentType>("refund");
  const [adjProductCode, setAdjProductCode] = useState("SKU-001");
  const [adjPeriod, setAdjPeriod] = useState("2025-06");
  const [adjFromPeriod, setAdjFromPeriod] = useState("2025-03");
  const [adjToPeriod, setAdjToPeriod] = useState("2025-05");
  const [adjAmount, setAdjAmount] = useState<number>(5000);
  const [adjNotes, setAdjNotes] = useState("");
  const [adjEffectiveDate, setAdjEffectiveDate] = useState("");

  async function load() {
    try {
      const data = await api(`/schedules/grid/${encodeURIComponent(cid)}`);
      setRows(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error(e);
      setRows([]);
      toast.error("Failed to load schedule");
    }
  }

  async function save() {
    try {
      await api(`/schedules/grid/${encodeURIComponent(cid)}`, {
        method: "POST",
        body: JSON.stringify({ rows }),
      });
      await load();
      toast.success("Schedule saved");
    } catch (e) {
      console.error(e);
      toast.error("Failed to save schedule");
    }
  }

  function exportCsv() {
    window.open(`${API_BASE}/schedules/grid/${encodeURIComponent(cid)}/export/csv`, "_blank");
  }

  async function importCsv() {
    if (!file) return;

    try {
      const fd = new FormData();
      fd.append("file", file);

      const res = await fetch(`${API_BASE}/schedules/grid/${encodeURIComponent(cid)}/import/csv`, {
        method: "POST",
        body: fd,
      });

      if (!res.ok) throw new Error(`Import failed: ${res.status}`);
      await load();
      toast.success("CSV imported");
    } catch (e) {
      console.error(e);
      toast.error("CSV import failed");
    }
  }

  async function applyAdjustment() {
    try {
      const base: any = {
        contract_id: cid,
        product_code: adjProductCode,
        adjustment_type: adjType,
        amount: Number(adjAmount || 0),
        notes: adjNotes || undefined,
        effective_date: adjEffectiveDate || undefined,
      };

      if (adjType === "delay") {
        base.from_period = adjFromPeriod;
        base.to_period = adjToPeriod;
      } else {
        base.period = adjPeriod;
      }

      await api("/schedules/adjust", {
        method: "POST",
        body: JSON.stringify(base),
      });

      await load();
      toast.success(`${adjType} adjustment applied`);

      // keep values, but clear notes for convenience
      setAdjNotes("");
    } catch (e: any) {
      console.error(e);
      toast.error("Adjustment failed");
    }
  }

  const totals = useMemo(() => {
    const gross = rows.reduce((s, r) => s + Number(r.amount || 0), 0);
    const positive = rows.filter(r => Number(r.amount) >= 0).reduce((s, r) => s + Number(r.amount || 0), 0);
    const negative = rows.filter(r => Number(r.amount) < 0).reduce((s, r) => s + Number(r.amount || 0), 0);
    const adjustments = rows.filter(r => r.is_adjustment || (r.source || "").includes("adjustment")).length;
    return { gross, positive, negative, adjustments };
  }, [rows]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="max-w-7xl mx-auto space-y-4 p-6">
      <h1 className="text-xl font-semibold">ASC-606 Revenue Schedule Editor</h1>

      {/* Top controls */}
      <Card className="p-4 flex flex-wrap gap-2 items-center">
        <Input
          className="max-w-xs"
          value={cid}
          onChange={(e) => setCid(e.target.value)}
          placeholder="Contract ID"
        />
        <Button onClick={load}>Load</Button>
        <Button onClick={save} variant="secondary">Save</Button>

        <input type="file" accept=".csv" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        <Button onClick={importCsv}>Import CSV</Button>
        <Button onClick={exportCsv}>Export CSV</Button>
      </Card>

      {/* Summary */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <Card className="p-3">
          <div className="text-xs text-gray-500">Net Revenue in Grid</div>
          <div className="text-lg font-semibold">${totals.gross.toLocaleString()}</div>
        </Card>
        <Card className="p-3">
          <div className="text-xs text-gray-500">Positive Rows</div>
          <div className="text-lg font-semibold">${totals.positive.toLocaleString()}</div>
        </Card>
        <Card className="p-3">
          <div className="text-xs text-gray-500">Negative Rows</div>
          <div className="text-lg font-semibold">${totals.negative.toLocaleString()}</div>
        </Card>
        <Card className="p-3">
          <div className="text-xs text-gray-500">Adjustment Rows</div>
          <div className="text-lg font-semibold">{totals.adjustments}</div>
        </Card>
      </div>

      {/* Adjustments */}
      <Card className="p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="font-medium">Schedule Adjustments</h2>
          <div className="text-xs text-gray-500">Audit-safe changes (delay / refund / true-up)</div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-2">
          <div>
            <div className="text-xs text-gray-500 mb-1">Adjustment Type</div>
            <select
              className="w-full border rounded px-2 py-2 text-sm"
              value={adjType}
              onChange={(e) => setAdjType(e.target.value as AdjustmentType)}
            >
              <option value="refund">refund</option>
              <option value="delay">delay</option>
              <option value="true_up">true_up</option>
            </select>
          </div>

          <div>
            <div className="text-xs text-gray-500 mb-1">Product Code</div>
            <Input
              value={adjProductCode}
              onChange={(e) => setAdjProductCode(e.target.value)}
              placeholder="SKU-001"
            />
          </div>

          {adjType !== "delay" ? (
            <div>
              <div className="text-xs text-gray-500 mb-1">Period</div>
              <Input
                value={adjPeriod}
                onChange={(e) => setAdjPeriod(e.target.value)}
                placeholder="YYYY-MM"
              />
            </div>
          ) : (
            <>
              <div>
                <div className="text-xs text-gray-500 mb-1">From Period</div>
                <Input
                  value={adjFromPeriod}
                  onChange={(e) => setAdjFromPeriod(e.target.value)}
                  placeholder="YYYY-MM"
                />
              </div>
              <div>
                <div className="text-xs text-gray-500 mb-1">To Period</div>
                <Input
                  value={adjToPeriod}
                  onChange={(e) => setAdjToPeriod(e.target.value)}
                  placeholder="YYYY-MM"
                />
              </div>
            </>
          )}

          <div>
            <div className="text-xs text-gray-500 mb-1">Amount</div>
            <Input
              type="number"
              value={adjAmount}
              onChange={(e) => setAdjAmount(parseFloat(e.target.value || "0"))}
              placeholder="5000"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
          <div>
            <div className="text-xs text-gray-500 mb-1">Effective Date (optional)</div>
            <Input
              type="date"
              value={adjEffectiveDate}
              onChange={(e) => setAdjEffectiveDate(e.target.value)}
            />
          </div>
          <div className="md:col-span-2">
            <div className="text-xs text-gray-500 mb-1">Notes (optional)</div>
            <Input
              value={adjNotes}
              onChange={(e) => setAdjNotes(e.target.value)}
              placeholder="Reason for adjustment (customer delay, partial refund, etc.)"
            />
          </div>
        </div>

        <div className="flex gap-2">
          <Button onClick={applyAdjustment}>Apply Adjustment</Button>
          <div className="text-xs text-gray-500 self-center">
            {adjType === "refund" && "Refund creates a negative revenue row."}
            {adjType === "delay" && "Delay moves revenue by creating a negative row in from-period and positive row in to-period."}
            {adjType === "true_up" && "True-up can be positive or negative and is posted in one period."}
          </div>
        </div>
      </Card>

      {/* Schedule grid */}
      <Card className="p-0 overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="p-2 text-left">Line</th>
              <th className="p-2 text-left">Period</th>
              <th className="p-2 text-right">Amount</th>
              <th className="p-2 text-left">Product Code</th>
              <th className="p-2 text-left">Product Name</th>
              <th className="p-2 text-right">SSP</th>
              <th className="p-2 text-left">RevRec</th>
              <th className="p-2 text-left">Rule</th>
              <th className="p-2 text-left">Source</th>
              <th className="p-2 text-left">Event</th>
              <th className="p-2 text-left">Adj?</th>
              <th className="p-2 text-left">Notes</th>
            </tr>
          </thead>

          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td className="p-4 text-gray-500" colSpan={12}>
                  No rows loaded. Save + Allocate in Contracts page first, then click Load.
                </td>
              </tr>
            ) : (
              rows.map((r, idx) => (
                <tr
                  key={`${r.line_no ?? idx}-${r.period}-${r.product_code ?? ""}`}
                  className={`border-t ${Number(r.amount) < 0 ? "bg-red-50" : ""}`}
                >
                  <td className="p-2">{r.line_no ?? idx + 1}</td>
                  <td className="p-2">{r.period}</td>
                  <td className="p-2 text-right font-medium">
                    ${Number(r.amount || 0).toLocaleString()}
                  </td>
                  <td className="p-2">{r.product_code || "-"}</td>
                  <td className="p-2">{r.product_name || "-"}</td>
                  <td className="p-2 text-right">{r.ssp != null ? `$${Number(r.ssp).toLocaleString()}` : "-"}</td>
                  <td className="p-2">{r.revrec_code || "-"}</td>
                  <td className="p-2">{r.rule_type || "-"}</td>
                  <td className="p-2">{r.source || "-"}</td>
                  <td className="p-2">{r.event_type || "-"}</td>
                  <td className="p-2">{r.is_adjustment ? "Yes" : "-"}</td>
                  <td className="p-2">{r.notes || "-"}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </Card>

      <div className="text-xs text-gray-600">
        This grid now supports audit-safe manual adjustments for delays, refunds, and true-ups.
      </div>
    </div>
  );
}
