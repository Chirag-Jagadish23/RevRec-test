"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/src/lib/api";
import { Button, Card, Input } from "@/src/components/ui";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

type AuditResult = {
  avg_score: number;
  scores: Record<string, number>;
  notes: string[];
  summary_memo: string;
  findings?: Record<string, any>;
  errors?: Record<string, string>;
};

type ContractOption = {
  id: string;
  name: string;
};

type EndpointStatus = "idle" | "loading" | "ok" | "error";

export default function AuditorPage() {
  const [contracts, setContracts] = useState<ContractOption[]>([]);
  const [contractSearch, setContractSearch] = useState("");
  const [selectedContractId, setSelectedContractId] = useState("");
  const [selectedContractName, setSelectedContractName] = useState("");

  const [data, setData] = useState<AuditResult | null>(null);
  const [findings, setFindings] = useState<Record<string, any> | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [rowCounts, setRowCounts] = useState<Record<string, number>>({});

  const [loading, setLoading] = useState(false);
  const [pageError, setPageError] = useState<string | null>(null);

  const [statuses, setStatuses] = useState<Record<string, EndpointStatus>>({
    contracts: "idle",
    revrec: "idle",
    leases: "idle",
    tax: "idle",
    forecast: "idle",
    fixed_assets: "idle", // NEW
    auditor: "idle",
  });

  // Load contracts on page load
  useEffect(() => {
    (async () => {
      setStatuses((s) => ({ ...s, contracts: "loading" }));
      try {
        const res = await api("/contracts?limit=100", { method: "GET" });

        const rawRows = Array.isArray(res)
          ? res
          : Array.isArray(res?.items)
          ? res.items
          : Array.isArray(res?.rows)
          ? res.rows
          : [];

        const normalized: ContractOption[] = rawRows.map((r: any, idx: number) => {
          const id = r.contract_id || r.id || r.code || `CONTRACT-${idx + 1}`;
          const name = r.contract_name || r.name || r.customer || r.customer_name || id;
          return { id: String(id), name: String(name) };
        });

        setContracts(normalized);

        if (normalized.length > 0) {
          setSelectedContractId(normalized[0].id);
          setSelectedContractName(normalized[0].name);
        }

        setStatuses((s) => ({ ...s, contracts: "ok" }));
      } catch (e: any) {
        console.error("Failed to load contracts", e);
        setStatuses((s) => ({ ...s, contracts: "error" }));
        setPageError("Failed to load contracts.");
      }
    })();
  }, []);

  function updateStatus(key: string, value: EndpointStatus) {
    setStatuses((s) => ({ ...s, [key]: value }));
  }

  function safeErrorMessage(err: any) {
    if (!err) return "Unknown error";
    if (typeof err === "string") return err;
    if (err.message) return err.message;
    try {
      return JSON.stringify(err);
    } catch {
      return "Unknown error";
    }
  }

  async function runAudit() {
    setLoading(true);
    setPageError(null);
    setData(null);
    setFindings(null);
    setErrors({});
    setRowCounts({});

    const moduleFindings: Record<string, any> = {};
    const moduleErrors: Record<string, string> = {};
    const counts: Record<string, number> = {};

    try {
      // ---- REVREC (real contract-based) ----
      updateStatus("revrec", "loading");
      try {
        if (!selectedContractId) {
          throw new Error("No contract selected.");
        }

        const revrecRes = await api(
          `/schedules/grid/${encodeURIComponent(selectedContractId)}`,
          { method: "GET" }
        );

        moduleFindings.revrec = revrecRes;
        counts.revrec = Array.isArray(revrecRes)
          ? revrecRes.length
          : Array.isArray(revrecRes?.rows)
          ? revrecRes.rows.length
          : 0;
        updateStatus("revrec", "ok");
      } catch (e: any) {
        moduleErrors.revrec = safeErrorMessage(e);
        updateStatus("revrec", "error");
      }

      // ---- LEASES ----
      updateStatus("leases", "loading");
      try {
        const leasesRes = await api("/leases/schedule", {
          method: "POST",
          body: JSON.stringify({
            lease_id: "AUTO-AUDIT",
            start_date: "2025-01-01",
            end_date: "2026-12-31",
            payment: 4500,
            frequency: "monthly",
            discount_rate_annual: 0.06,
          }),
        });

        moduleFindings.leases = leasesRes;
        counts.leases = Array.isArray(leasesRes?.rows) ? leasesRes.rows.length : 0;
        updateStatus("leases", "ok");
      } catch (e: any) {
        moduleErrors.leases = safeErrorMessage(e);
        updateStatus("leases", "error");
      }

      // ---- TAX ----
      updateStatus("tax", "loading");
      try {
        const taxRes = await api("/tax/asc740/calc", {
          method: "POST",
          body: JSON.stringify({
            company: "AuditTestCo",
            statutory_rate: 0.21,
            valuation_allowance_pct: 0.05,
            differences: [
              {
                label: "Depreciation",
                period: "2025-12",
                amount: 8000,
                reversal_year: 2026,
                va_pct: 0.0,
              },
              {
                label: "Warranty Reserve",
                period: "2026-12",
                amount: -4000,
                reversal_year: 2027,
                va_pct: 0.1,
              },
            ],
          }),
        });

        moduleFindings.tax = taxRes;
        counts.tax = Array.isArray(taxRes?.mapping) ? taxRes.mapping.length : 0;
        updateStatus("tax", "ok");
      } catch (e: any) {
        moduleErrors.tax = safeErrorMessage(e);
        updateStatus("tax", "error");
      }

      // ---- FORECAST ----
      updateStatus("forecast", "loading");
      try {
        const forecastRes = await api("/forecast/revenue", {
          method: "POST",
          body: JSON.stringify({
            history: {
              "2024-09": 10000,
              "2024-10": 12000,
              "2024-11": 11000,
              "2024-12": 11500,
            },
            horizon: 6,
            method: "exp_smooth",
          }),
        });

        moduleFindings.forecast = forecastRes;
        counts.forecast = forecastRes?.forecast
          ? Object.keys(forecastRes.forecast).length
          : 0;
        updateStatus("forecast", "ok");
      } catch (e: any) {
        moduleErrors.forecast = safeErrorMessage(e);
        updateStatus("forecast", "error");
      }

      // ---- FIXED ASSETS (NEW) ----
      updateStatus("fixed_assets", "loading");
      try {
        const faRes = await api("/fixed-assets/depreciation/schedule", {
          method: "POST",
          body: JSON.stringify({
            asset_id: "FA-AUDIT",
            asset_name: "Server Rack",
            category: "IT Equipment",
            in_service_date: "2025-01-15",
            cost: 50000,
            salvage_value: 5000,
            useful_life_months: 60,
            method: "db_switch_sl",
            convention: "mid_month",
            decline_rate: 2.0,
          }),
        });

        moduleFindings.fixed_assets = faRes;
        counts.fixed_assets = Array.isArray(faRes?.rows) ? faRes.rows.length : 0;
        updateStatus("fixed_assets", "ok");
      } catch (e: any) {
        moduleErrors.fixed_assets = safeErrorMessage(e);
        updateStatus("fixed_assets", "error");
      }

      // ---- AUDITOR SUMMARY ----
      updateStatus("auditor", "loading");
      const audit = await api("/auditor/summary", {
        method: "POST",
        body: JSON.stringify(moduleFindings),
      });
      updateStatus("auditor", "ok");

      setFindings(moduleFindings);
      setErrors(moduleErrors);
      setRowCounts(counts);
      setData({
        ...audit,
        findings: moduleFindings,
        errors: moduleErrors,
      });
    } catch (e: any) {
      console.error(e);
      updateStatus("auditor", "error");
      setPageError(e?.message || "Audit failed.");
    } finally {
      setLoading(false);
    }
  }

  const chartData = useMemo(() => {
    if (!data?.scores) return [];
    return Object.entries(data.scores).map(([module, score]) => ({ module, score }));
  }, [data]);

  const statusBadge = (label: string, status: EndpointStatus) => {
    const classes =
      status === "ok"
        ? "bg-green-100 text-green-700"
        : status === "error"
        ? "bg-red-100 text-red-700"
        : status === "loading"
        ? "bg-yellow-100 text-yellow-700"
        : "bg-gray-100 text-gray-600";

    return (
      <div className="flex items-center justify-between rounded border px-3 py-2 text-sm">
        <span className="font-medium">{label}</span>
        <span className={`rounded px-2 py-0.5 text-xs ${classes}`}>{status}</span>
      </div>
    );
  };

  return (
    <div className="max-w-7xl mx-auto space-y-4">
      <h1 className="text-xl font-semibold">AI Auditor Dashboard</h1>

      <Card className="p-4 space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 items-end">
          <div className="space-y-1">
            <div className="text-xs text-gray-500">Contract</div>
            <input
              className="w-full border rounded px-2 py-1 text-xs mb-1"
              placeholder="Filter by name or ID…"
              value={contractSearch}
              onChange={(e) => setContractSearch(e.target.value)}
            />
            <select
              className="w-full border rounded px-2 py-2 text-sm bg-white"
              value={selectedContractId}
              onChange={(e) => {
                const id = e.target.value;
                const c = contracts.find((x) => x.id === id);
                setSelectedContractId(id);
                setSelectedContractName(c?.name || "");
              }}
            >
              {contracts.length === 0 ? (
                <option value="">No contracts found</option>
              ) : (
                contracts
                  .filter((c) => {
                    const q = contractSearch.toLowerCase();
                    return !q || c.id.toLowerCase().includes(q) || c.name.toLowerCase().includes(q);
                  })
                  .map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} ({c.id})
                    </option>
                  ))
              )}
            </select>
          </div>

          <div className="space-y-1">
            <div className="text-xs text-gray-500">Selected Contract Name</div>
            <Input value={selectedContractName} readOnly />
          </div>

          <div className="flex gap-2">
            <Button onClick={runAudit} disabled={loading || !selectedContractId}>
              {loading ? "Analyzing..." : "Run Full Audit"}
            </Button>
          </div>
        </div>
      </Card>

      <Card className="p-4 space-y-2">
        <div className="font-medium mb-1">Endpoint Status</div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
          {statusBadge("Contracts", statuses.contracts)}
          {statusBadge("RevRec", statuses.revrec)}
          {statusBadge("Leases", statuses.leases)}
          {statusBadge("Tax", statuses.tax)}
          {statusBadge("Forecast", statuses.forecast)}
          {statusBadge("Fixed Assets", statuses.fixed_assets)}
          {statusBadge("Auditor Summary", statuses.auditor)}
        </div>
      </Card>

      {pageError && <div className="text-red-600 text-sm">{pageError}</div>}

      {data && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-6 gap-3">
            <Card className="p-4">
              <div className="text-xs text-gray-500">Overall Score</div>
              <div className="text-2xl font-semibold">{data.avg_score}</div>
            </Card>

            {Object.entries(data.scores || {}).map(([k, v]) => (
              <Card key={k} className="p-4">
                <div className="text-xs text-gray-500 uppercase">{k}</div>
                <div className="text-xl font-semibold">{v}</div>
                <div className="text-xs text-gray-500 mt-1">
                  rows: {rowCounts[k] ?? 0}
                </div>
              </Card>
            ))}
          </div>

          <Card className="p-4">
            <div className="font-medium mb-2">Key Observations</div>
            <ul className="list-disc ml-6 text-sm space-y-1">
              {(data.notes || []).map((n: string, i: number) => (
                <li key={i}>{n}</li>
              ))}
            </ul>
          </Card>

          {Object.keys(errors).length > 0 && (
            <Card className="p-4 border-red-200">
              <div className="font-medium text-red-700 mb-2">Module Errors</div>
              <ul className="list-disc ml-6 text-sm text-red-600 space-y-1">
                {Object.entries(errors).map(([k, v]) => (
                  <li key={k}>
                    <span className="font-medium">{k}:</span> {v}
                  </li>
                ))}
              </ul>
            </Card>
          )}

          <Card className="p-4">
            <div className="font-medium mb-2">Module Scores</div>
            <div style={{ width: "100%", height: 320 }}>
              <ResponsiveContainer>
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="module" />
                  <YAxis domain={[0, 100]} />
                  <Tooltip />
                  <Bar dataKey="score" radius={[6, 6, 0, 0]}>
                    {chartData.map((_, idx) => (
                      <Cell key={idx} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {Object.entries(findings || {}).map(([module, payload]) => (
              <Card key={module} className="p-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="font-medium">{module} payload</div>
                  <div className="text-xs text-gray-500">
                    rows: {rowCounts[module] ?? 0}
                  </div>
                </div>
                <pre className="text-xs bg-slate-50 border rounded p-3 overflow-x-auto max-h-80">
                  {JSON.stringify(payload, null, 2)}
                </pre>
              </Card>
            ))}
          </div>

          <Card className="p-4 whitespace-pre-wrap text-sm bg-gray-50">
            {data.summary_memo}
          </Card>
        </>
      )}
    </div>
  );
}
