"use client";

import { useMemo, useState } from "react";
import { api } from "@/src/lib/api";
import { Button, Card, Input } from "@/src/components/ui";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  BarChart,
  Bar,
} from "recharts";

type DepMethod = "sl" | "ddb" | "db_switch_sl";
type Convention = "full_month" | "mid_month" | "half_year";

type ScheduleRow = {
  period: number | string;
  month: string;
  depreciation_expense: number;
  accumulated_depreciation_opening?: number;
  accumulated_depreciation_ending?: number;
  net_book_value_opening?: number;
  net_book_value_ending?: number;

  // compatible with enhanced backend shape too
  period_end_date?: string;
  method_used?: string;
  convention_factor?: number;
  opening_book_value?: number;
  accumulated_depreciation?: number;
  closing_book_value?: number;
};

type ScheduleResponse = {
  asset_id: string;
  asset_name: string;
  category: string;
  in_service_date?: string;
  rows: ScheduleRow[];
  summary: {
    cost: number;
    salvage_value: number;
    depreciable_basis: number;
    total_depreciation: number;
    ending_nbv?: number;
    ending_book_value?: number;
    method?: string;
    convention?: string;
    decline_rate?: number;
    periods?: number;
  };
};

function downloadTextFile(filename: string, text: string) {
  const blob = new Blob([text], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function FixedAssetsPage() {
  const [form, setForm] = useState({
    asset_id: "FA-1001",
    asset_name: "MacBook Pro Fleet",
    category: "Computer Equipment",
    in_service_date: "2025-01-15",
    cost: 24000,
    salvage_value: 2000,
    useful_life_months: 36,
    method: "db_switch_sl" as DepMethod,
    convention: "mid_month" as Convention,
    decline_rate: 2.0,
    disposal_date: "",
  });

  const [data, setData] = useState<ScheduleResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState<null | "schedule" | "journals">(null);
  const [uploadingCsv, setUploadingCsv] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [bulkUploadResult, setBulkUploadResult] = useState<any>(null);

  function patch<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function buildPayload() {
    return {
      ...form,
      cost: Number(form.cost),
      salvage_value: Number(form.salvage_value),
      useful_life_months: Number(form.useful_life_months),
      decline_rate: Number(form.decline_rate),
      disposal_date: form.disposal_date?.trim() || null,
    };
  }

  async function runSchedule() {
    setLoading(true);
    setError(null);
    try {
      const res = await api("/fixed-assets/depreciation/schedule", {
        method: "POST",
        body: JSON.stringify(buildPayload()),
      });
      setData(res);
    } catch (e: any) {
      console.error(e);
      setError(e?.message || "Failed to compute depreciation schedule.");
    } finally {
      setLoading(false);
    }
  }

  async function download(kind: "schedule" | "journals") {
    setDownloading(kind);
    setError(null);

    try {
      const endpoint =
        kind === "schedule"
          ? "/fixed-assets/depreciation/export"
          : "/fixed-assets/depreciation/export-journals";

      const res = await api(endpoint, {
        method: "POST",
        body: JSON.stringify(buildPayload()),
      });

      // backend expected shape: { filename, content }
      if (res?.content) {
        downloadTextFile(
          res.filename || `fixed_assets_${kind}.csv`,
          res.content
        );
        return;
      }

      // fallback if backend returns raw CSV text
      if (typeof res === "string") {
        downloadTextFile(`fixed_assets_${kind}.csv`, res);
        return;
      }

      throw new Error("CSV export endpoint did not return CSV content.");
    } catch (e: any) {
      console.error(e);

      // fallback for schedule CSV from current table
      if (kind === "schedule" && data?.rows?.length) {
        const header = [
          "period",
          "month",
          "depreciation_expense",
          "accumulated_depreciation_opening",
          "accumulated_depreciation_ending",
          "net_book_value_opening",
          "net_book_value_ending",
          "period_end_date",
          "method_used",
          "convention_factor",
        ];
        const lines = [header.join(",")];

        for (const r of data.rows) {
          const vals = header.map((k) => {
            const v = (r as any)[k];
            if (v === undefined || v === null) return "";
            const s = String(v);
            return s.includes(",") ? `"${s.replace(/"/g, '""')}"` : s;
          });
          lines.push(vals.join(","));
        }

        downloadTextFile(`${form.asset_id}_depreciation_schedule.csv`, lines.join("\n"));
      } else {
        setError(e?.message || "Failed to export CSV.");
      }
    } finally {
      setDownloading(null);
    }
  }

  async function onBulkUpload(file: File) {
    setUploadingCsv(true);
    setError(null);
    setBulkUploadResult(null);

    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("method", form.method);
      fd.append("convention", form.convention);
      fd.append("decline_rate", String(form.decline_rate));

      const base =
        process.env.NEXT_PUBLIC_API_URL ||
        process.env.NEXT_PUBLIC_BACKEND_URL ||
        "http://127.0.0.1:8000";

      const resp = await fetch(`${base}/fixed-assets/depreciation/csv/calc`, {
        method: "POST",
        body: fd,
      });

      const json = await resp.json();
      if (!resp.ok) {
        throw new Error(json?.detail || "Bulk CSV upload failed");
      }

      setBulkUploadResult(json);

      // if backend returns single-schedule shape, render it directly
      if (json?.rows && json?.summary) {
        setData(json as ScheduleResponse);
      }
    } catch (e: any) {
      console.error(e);
      setError(e?.message || "Bulk CSV upload failed.");
    } finally {
      setUploadingCsv(false);
    }
  }

  const chartData = useMemo(() => {
    if (!data?.rows) return [];
    return data.rows.map((r) => ({
      month: r.month,
      depreciation: Number(r.depreciation_expense || 0),
      nbv: Number(r.net_book_value_ending ?? r.closing_book_value ?? 0),
      accum: Number(
        r.accumulated_depreciation_ending ?? r.accumulated_depreciation ?? 0
      ),
    }));
  }, [data]);

  const summary = data?.summary;
  const endingNBV = summary?.ending_nbv ?? summary?.ending_book_value ?? 0;

  return (
    <div className="max-w-7xl mx-auto space-y-4">
      <h1 className="text-xl font-semibold">Fixed Assets & Depreciation</h1>

      <Card className="p-4 space-y-3">
        <div className="font-medium">Asset Inputs</div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <Input value={form.asset_id} onChange={(e: any) => patch("asset_id", e.target.value)} placeholder="Asset ID" />
          <Input value={form.asset_name} onChange={(e: any) => patch("asset_name", e.target.value)} placeholder="Asset Name" />
          <Input value={form.category} onChange={(e: any) => patch("category", e.target.value)} placeholder="Category" />

          <Input type="date" value={form.in_service_date} onChange={(e: any) => patch("in_service_date", e.target.value)} />
          <Input type="number" value={String(form.cost)} onChange={(e: any) => patch("cost", Number(e.target.value))} placeholder="Cost" />
          <Input type="number" value={String(form.salvage_value)} onChange={(e: any) => patch("salvage_value", Number(e.target.value))} placeholder="Salvage Value" />

          <Input type="number" value={String(form.useful_life_months)} onChange={(e: any) => patch("useful_life_months", Number(e.target.value))} placeholder="Useful Life (Months)" />
          <Input type="number" step="0.1" value={String(form.decline_rate)} onChange={(e: any) => patch("decline_rate", Number(e.target.value))} placeholder="Decline Rate" />
          <Input type="date" value={form.disposal_date} onChange={(e: any) => patch("disposal_date", e.target.value)} placeholder="Disposal Date (optional)" />

          <select
            className="w-full border rounded px-2 py-2 text-sm bg-white"
            value={form.method}
            onChange={(e: any) => patch("method", e.target.value as DepMethod)}
          >
            <option value="sl">Straight-Line</option>
            <option value="ddb">Double Declining</option>
            <option value="db_switch_sl">DB Switch to SL</option>
          </select>

          <select
            className="w-full border rounded px-2 py-2 text-sm bg-white"
            value={form.convention}
            onChange={(e: any) => patch("convention", e.target.value as Convention)}
          >
            <option value="full_month">Full Month</option>
            <option value="mid_month">Mid Month</option>
            <option value="half_year">Half Year</option>
          </select>
        </div>

        <div className="flex flex-wrap gap-2 pt-2">
          <Button onClick={runSchedule} disabled={loading}>
            {loading ? "Computing..." : "Compute Depreciation"}
          </Button>

          <Button onClick={() => download("schedule")} disabled={downloading !== null}>
            {downloading === "schedule" ? "Exporting..." : "Export Schedule CSV"}
          </Button>

          <Button onClick={() => download("journals")} disabled={downloading !== null}>
            {downloading === "journals" ? "Exporting..." : "Export Journals CSV"}
          </Button>

          <label className="inline-flex items-center">
            <input
              type="file"
              accept=".csv"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) onBulkUpload(f);
                e.currentTarget.value = "";
              }}
            />
            <span className="inline-flex cursor-pointer items-center rounded border px-3 py-2 text-sm bg-white hover:bg-gray-50">
              {uploadingCsv ? "Uploading CSV..." : "Bulk Upload CSV"}
            </span>
          </label>
        </div>

        <div className="text-xs text-gray-500">
          Bulk upload expected columns:
          <span className="ml-1 font-mono">
            asset_id,asset_name,category,in_service_date,cost,salvage_value,useful_life_months,method,convention,decline_rate
          </span>
        </div>
      </Card>

      {error && <div className="text-red-600 text-sm">{error}</div>}

      {bulkUploadResult && (
        <Card className="p-4">
          <div className="font-medium mb-2">Bulk Upload Result</div>
          <pre className="text-xs bg-slate-50 border rounded p-3 overflow-x-auto max-h-72">
            {JSON.stringify(bulkUploadResult, null, 2)}
          </pre>
        </Card>
      )}

      {summary && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
            <Card className="p-4">
              <div className="text-xs text-gray-500">Cost</div>
              <div className="text-lg font-semibold">${Number(summary.cost || 0).toLocaleString()}</div>
            </Card>
            <Card className="p-4">
              <div className="text-xs text-gray-500">Depreciable Basis</div>
              <div className="text-lg font-semibold">${Number(summary.depreciable_basis || 0).toLocaleString()}</div>
            </Card>
            <Card className="p-4">
              <div className="text-xs text-gray-500">Total Depreciation</div>
              <div className="text-lg font-semibold">${Number(summary.total_depreciation || 0).toLocaleString()}</div>
            </Card>
            <Card className="p-4">
              <div className="text-xs text-gray-500">Ending NBV</div>
              <div className="text-lg font-semibold">${Number(endingNBV || 0).toLocaleString()}</div>
            </Card>
            <Card className="p-4">
              <div className="text-xs text-gray-500">Method / Convention</div>
              <div className="text-sm font-medium">
                {summary.method || form.method} / {summary.convention || form.convention}
              </div>
            </Card>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card className="p-4">
              <div className="font-medium mb-2">Book Value Trend</div>
              <div style={{ width: "100%", height: 300 }}>
                <ResponsiveContainer>
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="month" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Line type="monotone" dataKey="nbv" name="Ending NBV" />
                    <Line type="monotone" dataKey="accum" name="Accum. Depreciation" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </Card>

            <Card className="p-4">
              <div className="font-medium mb-2">Depreciation Expense by Month</div>
              <div style={{ width: "100%", height: 300 }}>
                <ResponsiveContainer>
                  <BarChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="month" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="depreciation" name="Depreciation Expense" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
          </div>

          <Card className="p-4">
            <div className="flex items-center justify-between mb-2">
              <div className="font-medium">Depreciation Schedule</div>
              <div className="text-xs text-gray-500">
                {data?.rows?.length || 0} rows • {data?.asset_name} ({data?.asset_id})
              </div>
            </div>

            <div className="overflow-x-auto border rounded">
              <table className="min-w-full text-sm">
                <thead className="bg-gray-50 border-b">
                  <tr>
                    <th className="text-left px-3 py-2">Period</th>
                    <th className="text-left px-3 py-2">Month</th>
                    <th className="text-right px-3 py-2">Dep Expense</th>
                    <th className="text-right px-3 py-2">Accum Dep (Open)</th>
                    <th className="text-right px-3 py-2">Accum Dep (End)</th>
                    <th className="text-right px-3 py-2">NBV (Open)</th>
                    <th className="text-right px-3 py-2">NBV (End)</th>
                    <th className="text-left px-3 py-2">Method Used</th>
                  </tr>
                </thead>
                <tbody>
                  {(data?.rows || []).map((r, idx) => (
                    <tr key={`${r.month}-${idx}`} className="border-b last:border-b-0">
                      <td className="px-3 py-2">{r.period}</td>
                      <td className="px-3 py-2">{r.month}</td>
                      <td className="px-3 py-2 text-right">${Number(r.depreciation_expense || 0).toFixed(2)}</td>
                      <td className="px-3 py-2 text-right">
                        ${Number(r.accumulated_depreciation_opening ?? 0).toFixed(2)}
                      </td>
                      <td className="px-3 py-2 text-right">
                        ${Number(r.accumulated_depreciation_ending ?? r.accumulated_depreciation ?? 0).toFixed(2)}
                      </td>
                      <td className="px-3 py-2 text-right">
                        ${Number(r.net_book_value_opening ?? r.opening_book_value ?? 0).toFixed(2)}
                      </td>
                      <td className="px-3 py-2 text-right">
                        ${Number(r.net_book_value_ending ?? r.closing_book_value ?? 0).toFixed(2)}
                      </td>
                      <td className="px-3 py-2">{r.method_used || "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
