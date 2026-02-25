"use client";

import { useMemo, useState } from "react";
import { api } from "@/src/lib/api";
import { Button } from "@/src/components/ui/button";
import { Card } from "@/src/components/ui/card";
import { Input } from "@/src/components/ui/input";
import { toast } from "sonner";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

type ForecastResult = {
  method: "exp_smooth" | "seasonal_ma";
  params?: { alpha?: number; season?: number };
  fitted?: Record<string, number>;
  forecast?: Record<string, number>;
};

const DEFAULT_HISTORY = `2024-01,10000
2024-02,12000
2024-03,9000
2024-04,11000
2024-05,11500
2024-06,13000
2024-07,12500
2024-08,14000
2024-09,13800
2024-10,14500
2024-11,15000
2024-12,17000`;

function parseHistoryText(text: string): Record<string, number> {
  const out: Record<string, number> = {};
  const lines = text
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);

  for (const line of lines) {
    const [monthRaw, valueRaw] = line.split(",").map((x) => x?.trim());
    if (!monthRaw || !valueRaw) {
      throw new Error(`Invalid line "${line}". Use YYYY-MM,amount`);
    }
    if (!/^\d{4}-\d{2}$/.test(monthRaw)) {
      throw new Error(`Invalid month "${monthRaw}". Use YYYY-MM`);
    }
    const value = Number(valueRaw);
    if (Number.isNaN(value)) {
      throw new Error(`Invalid amount "${valueRaw}" in line "${line}"`);
    }
    out[monthRaw] = value;
  }

  return out;
}

function historyToText(history: Record<string, number>): string {
  return Object.entries(history)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([k, v]) => `${k},${v}`)
    .join("\n");
}

function applyScenario(
  forecast: Record<string, number>,
  pct: number
): Record<string, number> {
  const factor = 1 + pct / 100;
  const out: Record<string, number> = {};
  for (const [k, v] of Object.entries(forecast)) {
    out[k] = Number((v * factor).toFixed(2));
  }
  return out;
}

function exportCsv(filename: string, rows: Array<Record<string, any>>) {
  if (!rows.length) return;

  const headers = Object.keys(rows[0]);
  const lines = [
    headers.join(","),
    ...rows.map((r) =>
      headers
        .map((h) => {
          const val = r[h] ?? "";
          const s = String(val);
          return s.includes(",") || s.includes('"') || s.includes("\n")
            ? `"${s.replace(/"/g, '""')}"`
            : s;
        })
        .join(",")
    ),
  ];

  const blob = new Blob([lines.join("\n")], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function ForecastPage() {
  const [contractId, setContractId] = useState("C-TEST");

  const [historyText, setHistoryText] = useState(DEFAULT_HISTORY);
  const [horizon, setHorizon] = useState(6);
  const [method, setMethod] = useState<"exp_smooth" | "seasonal_ma">("exp_smooth");
  const [alpha, setAlpha] = useState(0.35);
  const [season, setSeason] = useState(12);

  const [baseAdjPct, setBaseAdjPct] = useState(0);
  const [upsideAdjPct, setUpsideAdjPct] = useState(10);
  const [downsideAdjPct, setDownsideAdjPct] = useState(-10);

  const [result, setResult] = useState<ForecastResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadedFromGrid, setLoadedFromGrid] = useState(false);

  const parsedHistory = useMemo(() => {
    try {
      return parseHistoryText(historyText);
    } catch {
      return null;
    }
  }, [historyText]);

  async function loadHistoryFromScheduleGrid() {
    try {
      const rows = await api(`/schedules/grid/${encodeURIComponent(contractId)}`);
      if (!Array.isArray(rows) || rows.length === 0) {
        toast.error("No schedule rows found for this contract");
        return;
      }

      // Aggregate by period (YYYY-MM)
      const hist: Record<string, number> = {};
      for (const r of rows) {
        const period = String(r.period || "").slice(0, 7);
        const amt = Number(r.amount || 0);
        if (!period) continue;
        hist[period] = Number(((hist[period] || 0) + amt).toFixed(2));
      }

      setHistoryText(historyToText(hist));
      setLoadedFromGrid(true);
      setResult(null);
      toast.success(`Loaded ${rows.length} rows from schedule grid`);
    } catch (e: any) {
      toast.error(e?.message || "Failed to load schedule grid");
    }
  }

  async function run() {
    try {
      setLoading(true);
      const history = parseHistoryText(historyText);

      const body: any = {
        history,
        horizon,
        method,
      };

      if (method === "exp_smooth") body.alpha = alpha;
      if (method === "seasonal_ma") body.season = season;

      const res = await api("/forecast/revenue", {
        method: "POST",
        body: JSON.stringify(body),
      });

      setResult(res);
      toast.success("Forecast generated");
    } catch (e: any) {
      toast.error(e?.message || "Failed to run forecast");
    } finally {
      setLoading(false);
    }
  }

  const scenarios = useMemo(() => {
    if (!result?.forecast) return null;
    return {
      base: applyScenario(result.forecast, baseAdjPct),
      upside: applyScenario(result.forecast, upsideAdjPct),
      downside: applyScenario(result.forecast, downsideAdjPct),
    };
  }, [result, baseAdjPct, upsideAdjPct, downsideAdjPct]);

  const chartData = useMemo(() => {
    if (!result || !parsedHistory) return [];

    const months = new Set<string>();
    Object.keys(parsedHistory).forEach((m) => months.add(m));
    Object.keys(result.fitted || {}).forEach((m) => months.add(m));
    Object.keys(result.forecast || {}).forEach((m) => months.add(m));
    Object.keys(scenarios?.base || {}).forEach((m) => months.add(m));
    Object.keys(scenarios?.upside || {}).forEach((m) => months.add(m));
    Object.keys(scenarios?.downside || {}).forEach((m) => months.add(m));

    return Array.from(months)
      .sort()
      .map((m) => ({
        month: m,
        historical: parsedHistory[m] ?? null,
        fitted: result.fitted?.[m] ?? null,
        forecast_base: scenarios?.base?.[m] ?? null,
        forecast_upside: scenarios?.upside?.[m] ?? null,
        forecast_downside: scenarios?.downside?.[m] ?? null,
      }));
  }, [result, parsedHistory, scenarios]);

  const comparisonRows = useMemo(() => {
    if (!parsedHistory || !result?.fitted) return [];
    return Object.keys(parsedHistory)
      .sort()
      .map((m) => {
        const actual = Number(parsedHistory[m] ?? 0);
        const fitted = Number(result.fitted?.[m] ?? 0);
        const variance = Number((actual - fitted).toFixed(2));
        const variancePct =
          fitted === 0 ? null : Number((((actual - fitted) / fitted) * 100).toFixed(2));
        return { month: m, actual, fitted, variance, variancePct };
      });
  }, [parsedHistory, result]);

  const mape = useMemo(() => {
    const usable = comparisonRows.filter((r) => r.actual !== 0);
    if (!usable.length) return null;
    const avg =
      usable.reduce((s, r) => s + Math.abs((r.actual - r.fitted) / r.actual), 0) /
      usable.length;
    return Number((avg * 100).toFixed(2));
  }, [comparisonRows]);

  const forecastRows = useMemo(() => {
    if (!scenarios) return [];
    const months = Object.keys(scenarios.base).sort();
    return months.map((m) => ({
      period: m,
      base: scenarios.base[m],
      upside: scenarios.upside[m],
      downside: scenarios.downside[m],
    }));
  }, [scenarios]);

  const totals = useMemo(() => {
    const sum = (arr: number[]) => Number(arr.reduce((s, v) => s + v, 0).toFixed(2));
    return {
      base: sum(forecastRows.map((r) => r.base)),
      upside: sum(forecastRows.map((r) => r.upside)),
      downside: sum(forecastRows.map((r) => r.downside)),
    };
  }, [forecastRows]);

  function downloadForecastCsv() {
    if (!forecastRows.length) {
      toast.error("Run forecast first");
      return;
    }
    exportCsv("forecast_scenarios.csv", forecastRows);
    toast.success("Forecast CSV downloaded");
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Revenue Forecast AI (v2)</h1>

      <Card className="p-4 space-y-4">
        <h2 className="font-medium text-sm text-gray-700">1) Load Historical Revenue</h2>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div className="space-y-1">
            <label className="text-xs text-gray-500">Contract ID (for schedule grid)</label>
            <Input
              value={contractId}
              onChange={(e) => setContractId(e.target.value)}
              placeholder="C-TEST"
            />
          </div>

          <div className="flex items-end">
            <Button onClick={loadHistoryFromScheduleGrid} className="w-full">
              Load from /schedules/grid
            </Button>
          </div>

          <div className="md:col-span-2 flex items-end text-xs text-gray-500">
            {loadedFromGrid
              ? "Loaded history from schedule grid and aggregated by month."
              : "You can load from schedule grid or type/paste history manually below."}
          </div>
        </div>

        <div className="space-y-1">
          <label className="text-xs text-gray-500">
            Historical recognized revenue (one row per month: <code>YYYY-MM,amount</code>)
          </label>
          <textarea
            value={historyText}
            onChange={(e) => {
              setHistoryText(e.target.value);
              setLoadedFromGrid(false);
            }}
            className="w-full min-h-[180px] border rounded p-2 text-sm font-mono"
            placeholder="2024-01,10000&#10;2024-02,12000"
          />
          {!parsedHistory && (
            <p className="text-xs text-red-600">Fix history formatting before running.</p>
          )}
        </div>
      </Card>

      <Card className="p-4 space-y-4">
        <h2 className="font-medium text-sm text-gray-700">2) Forecast Settings</h2>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div className="space-y-1">
            <label className="text-xs text-gray-500">Horizon (months)</label>
            <Input
              type="number"
              value={String(horizon)}
              onChange={(e) => setHorizon(Math.max(1, Number(e.target.value || 1)))}
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs text-gray-500">Method</label>
            <select
              className="w-full border rounded px-2 py-2 text-sm bg-white"
              value={method}
              onChange={(e) => setMethod(e.target.value as "exp_smooth" | "seasonal_ma")}
            >
              <option value="exp_smooth">Exponential Smoothing</option>
              <option value="seasonal_ma">Seasonal Moving Average</option>
            </select>
          </div>

          {method === "exp_smooth" ? (
            <div className="space-y-1">
              <label className="text-xs text-gray-500">Alpha</label>
              <Input
                type="number"
                step="0.01"
                value={String(alpha)}
                onChange={(e) => setAlpha(Number(e.target.value || 0.35))}
              />
            </div>
          ) : (
            <div className="space-y-1">
              <label className="text-xs text-gray-500">Season Length</label>
              <Input
                type="number"
                value={String(season)}
                onChange={(e) => setSeason(Math.max(2, Number(e.target.value || 12)))}
              />
            </div>
          )}

          <div className="flex items-end">
            <Button onClick={run} disabled={loading} className="w-full">
              {loading ? "Running..." : "Run Forecast"}
            </Button>
          </div>
        </div>
      </Card>

      <Card className="p-4 space-y-4">
        <h2 className="font-medium text-sm text-gray-700">3) Scenario Adjustments</h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="space-y-1">
            <label className="text-xs text-gray-500">Base Adjustment %</label>
            <Input
              type="number"
              value={String(baseAdjPct)}
              onChange={(e) => setBaseAdjPct(Number(e.target.value || 0))}
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-gray-500">Upside Adjustment %</label>
            <Input
              type="number"
              value={String(upsideAdjPct)}
              onChange={(e) => setUpsideAdjPct(Number(e.target.value || 10))}
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-gray-500">Downside Adjustment %</label>
            <Input
              type="number"
              value={String(downsideAdjPct)}
              onChange={(e) => setDownsideAdjPct(Number(e.target.value || -10))}
            />
          </div>
        </div>
      </Card>

      {result && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Card className="p-4">
              <div className="text-xs text-gray-500">Method</div>
              <div className="text-lg font-semibold">{result.method}</div>
            </Card>

            <Card className="p-4">
              <div className="text-xs text-gray-500">Forecast Horizon</div>
              <div className="text-lg font-semibold">{forecastRows.length} months</div>
            </Card>

            <Card className="p-4">
              <div className="text-xs text-gray-500">Base Forecast Total</div>
              <div className="text-lg font-semibold">${totals.base.toLocaleString()}</div>
            </Card>

            <Card className="p-4">
              <div className="text-xs text-gray-500">In-Sample MAPE</div>
              <div className="text-lg font-semibold">
                {mape == null ? "N/A" : `${mape}%`}
              </div>
            </Card>
          </div>

          <Card className="p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-medium">Chart (History + Fitted + Scenarios)</h2>
              <Button onClick={downloadForecastCsv}>Download Forecast CSV</Button>
            </div>

            <div style={{ width: "100%", height: 380 }}>
              <ResponsiveContainer>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="month" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="historical" name="Historical" dot={false} />
                  <Line type="monotone" dataKey="fitted" name="Fitted" dot={false} />
                  <Line type="monotone" dataKey="forecast_base" name="Base" dot={false} />
                  <Line
                    type="monotone"
                    dataKey="forecast_upside"
                    name="Upside"
                    dot={false}
                    strokeDasharray="5 5"
                  />
                  <Line
                    type="monotone"
                    dataKey="forecast_downside"
                    name="Downside"
                    dot={false}
                    strokeDasharray="3 4"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Card>

          {comparisonRows.length > 0 && (
            <Card className="p-4">
              <h2 className="font-medium mb-2">Actual vs Fitted (In-Sample Check)</h2>
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="border-b bg-gray-50">
                      <th className="p-2 text-left">Month</th>
                      <th className="p-2 text-right">Actual</th>
                      <th className="p-2 text-right">Fitted</th>
                      <th className="p-2 text-right">Variance</th>
                      <th className="p-2 text-right">Variance %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {comparisonRows.map((r) => (
                      <tr key={r.month} className="border-b">
                        <td className="p-2">{r.month}</td>
                        <td className="p-2 text-right">{r.actual.toFixed(2)}</td>
                        <td className="p-2 text-right">{r.fitted.toFixed(2)}</td>
                        <td className="p-2 text-right">{r.variance.toFixed(2)}</td>
                        <td className="p-2 text-right">
                          {r.variancePct == null ? "N/A" : `${r.variancePct.toFixed(2)}%`}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          <Card className="p-4">
            <h2 className="font-medium mb-2">Forecast Output (Scenarios)</h2>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="border-b bg-gray-50">
                    <th className="p-2 text-left">Period</th>
                    <th className="p-2 text-right">Base</th>
                    <th className="p-2 text-right">Upside</th>
                    <th className="p-2 text-right">Downside</th>
                  </tr>
                </thead>
                <tbody>
                  {forecastRows.map((r) => (
                    <tr key={r.period} className="border-b">
                      <td className="p-2">{r.period}</td>
                      <td className="p-2 text-right">{r.base.toFixed(2)}</td>
                      <td className="p-2 text-right">{r.upside.toFixed(2)}</td>
                      <td className="p-2 text-right">{r.downside.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="bg-gray-50 font-medium">
                    <td className="p-2">Total</td>
                    <td className="p-2 text-right">{totals.base.toFixed(2)}</td>
                    <td className="p-2 text-right">{totals.upside.toFixed(2)}</td>
                    <td className="p-2 text-right">{totals.downside.toFixed(2)}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
