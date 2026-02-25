"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/src/lib/api";
import { Input } from "@/src/components/ui/input";
import { Button } from "@/src/components/ui/button";
import { Card } from "@/src/components/ui/card";
import { toast } from "sonner";

type LineItem = { product_code: string; amount: number };

type CatalogProduct = {
  product_code: string;
  name: string;
  ssp: number;
  revrec_code?: string;
};

type RevRecCode = {
  code: string;
  rule_type: string;
  description?: string;
};

type AllocationRow = {
  product_code: string;
  revrec_code?: string;
  rule_type?: string;
  allocated_total?: number;
  monthly_amount?: number;
  months?: number;
};

type ScheduleGridRow = {
  line_no?: number;
  period: string;
  amount: number;
  source?: string;
  product_code?: string;
  product_name?: string;
  ssp?: number;
  revrec_code?: string;
  rule_type?: string;
};

export default function ContractsPage() {
  const [contract_id, setContractId] = useState("C-TEST");
  const [customer, setCustomer] = useState("DemoCo");
  const [transaction_price, setTxnPrice] = useState(50000);
  const [startDate, setStartDate] = useState("2025-01-01");
  const [endDate, setEndDate] = useState("2025-12-31");

  const [items, setItems] = useState<LineItem[]>([
    { product_code: "SKU-001", amount: 20000 },
    { product_code: "SKU-002", amount: 30000 },
  ]);

  const [catalog, setCatalog] = useState<CatalogProduct[]>([]);
  const [revrecCodes, setRevrecCodes] = useState<RevRecCode[]>([]);

  const [allocResult, setAllocResult] = useState<any>(null);
  const [scheduleGrid, setScheduleGrid] = useState<ScheduleGridRow[]>([]);

  // -----------------------------
  // Maps / derived data
  // -----------------------------
  const catalogMap = useMemo(() => {
    const m: Record<string, CatalogProduct> = {};
    for (const p of catalog) m[p.product_code] = p;
    return m;
  }, [catalog]);

  const revrecMap = useMemo(() => {
    const m: Record<string, RevRecCode> = {};
    for (const r of revrecCodes) m[r.code] = r;
    return m;
  }, [revrecCodes]);

  const lineEnriched = useMemo(() => {
    return items.map((it) => {
      const p = catalogMap[it.product_code];
      const revCode = p?.revrec_code || "";
      const rr = revCode ? revrecMap[revCode] : undefined;
      return {
        ...it,
        product_name: p?.name || "",
        ssp: Number(p?.ssp ?? 0),
        revrec_code: revCode,
        rule_type: rr?.rule_type || "",
      };
    });
  }, [items, catalogMap, revrecMap]);

  const totalLineSellPrices = useMemo(
    () => lineEnriched.reduce((s, i) => s + Number(i.amount || 0), 0),
    [lineEnriched]
  );

  const totalSSP = useMemo(
    () => lineEnriched.reduce((s, i) => s + Number(i.ssp || 0), 0),
    [lineEnriched]
  );

  const sspAllocationPreview = useMemo(() => {
    if (totalSSP <= 0) {
      return lineEnriched.map((i) => ({
        ...i,
        ssp_pct: 0,
        alloc_preview: 0,
      }));
    }

    return lineEnriched.map((i) => {
      const pct = Number(i.ssp || 0) / totalSSP;
      return {
        ...i,
        ssp_pct: pct,
        alloc_preview: pct * Number(transaction_price || 0),
      };
    });
  }, [lineEnriched, totalSSP, transaction_price]);

  const previewAllocatedTotal = useMemo(
    () => sspAllocationPreview.reduce((s, i) => s + Number(i.alloc_preview || 0), 0),
    [sspAllocationPreview]
  );

  const backendAllocations: AllocationRow[] = useMemo(
    () => (allocResult?.allocations || []) as AllocationRow[],
    [allocResult]
  );

  const backendAllocatedTotal = useMemo(
    () => backendAllocations.reduce((s, a) => s + Number(a.allocated_total || 0), 0),
    [backendAllocations]
  );

  const displayedAllocatedTotal =
    backendAllocations.length > 0 ? backendAllocatedTotal : previewAllocatedTotal;

  const contractVsAllocatedDiff = Number(transaction_price || 0) - displayedAllocatedTotal;

  const monthlyWaterfall = useMemo(() => {
    const byPeriod: Record<string, number> = {};
    for (const row of scheduleGrid) {
      byPeriod[row.period] = (byPeriod[row.period] || 0) + Number(row.amount || 0);
    }
    return Object.entries(byPeriod)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([period, amount]) => ({ period, amount }));
  }, [scheduleGrid]);

  const maxWaterfall = useMemo(() => {
    const max = Math.max(0, ...monthlyWaterfall.map((r) => Number(r.amount || 0)));
    return max || 1;
  }, [monthlyWaterfall]);

  // -----------------------------
  // Loaders
  // -----------------------------
  useEffect(() => {
    loadReferenceData();
  }, []);

  useEffect(() => {
    loadContract();
    reloadSchedule();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [contract_id]);

  async function loadReferenceData() {
    try {
      const [prods, rules] = await Promise.all([api("/catalog"), api("/revrec_codes")]);
      setCatalog(Array.isArray(prods) ? prods : []);
      setRevrecCodes(Array.isArray(rules) ? rules : []);
    } catch (e) {
      console.error(e);
      setCatalog([]);
      setRevrecCodes([]);
      toast.error("Failed to load catalog / RevRec codes");
    }
  }

  async function loadContract() {
    try {
      const res = await api(`/contracts/${encodeURIComponent(contract_id)}`);

      setCustomer(res.customer || "DemoCo");
      setTxnPrice(Number(res.transaction_price || 0));
      setStartDate(res.start_date || "2025-01-01");
      setEndDate(res.end_date || "2025-12-31");

      setItems(
        (res.lines || []).map((l: any) => ({
          product_code: l.product_code || l.sku || "",
          amount: Number(l.amount || 0),
        }))
      );
    } catch {
      // fine if contract not saved yet
    }
  }

  async function reloadSchedule() {
    try {
      const res = await api(`/schedules/grid/${encodeURIComponent(contract_id)}`);
      setScheduleGrid(Array.isArray(res) ? res : []);
    } catch {
      setScheduleGrid([]);
    }
  }

  // -----------------------------
  // Actions
  // -----------------------------
  async function saveContract() {
    try {
      await api("/contracts/save", {
        method: "POST",
        body: JSON.stringify({
          contract_id,
          customer,
          transaction_price: Number(transaction_price || 0),
          start_date: startDate,
          end_date: endDate,
          lines: items.map((i) => ({
            product_code: i.product_code,
            amount: Number(i.amount || 0),
          })),
        }),
      });

      toast.success("Contract saved");
    } catch (err) {
      console.error(err);
      toast.error("Failed to save contract");
    }
  }

  async function allocate() {
    try {
      const res = await api("/contracts/allocate", {
        method: "POST",
        body: JSON.stringify({ contract_id }),
      });

      setAllocResult(res);
      await reloadSchedule();
      await loadReferenceData();

      toast.success("Allocation complete");
    } catch (e) {
      console.error(e);
      toast.error("Allocation failed");
    }
  }

  // Keep non-destructive until your AI route is finalized
  async function aiGenerate() {
    toast.message("AI Build Schedule is temporarily disabled (non-destructive mode). Use Allocate Revenue.");
  }

  function updateItem(idx: number, field: keyof LineItem, value: string) {
    const next = [...items];
    next[idx] = {
      ...next[idx],
      [field]: field === "amount" ? parseFloat(value || "0") : value,
    };
    setItems(next);
  }

  function getRulePreview(productCode: string) {
    const p = catalogMap[productCode];
    if (!p) return "Unknown product";

    const revCode = p.revrec_code || "";
    const rr = revCode ? revrecMap[revCode] : undefined;
    const ruleType = rr?.rule_type || "unknown";

    if (ruleType === "immediate") return "Immediate: recognize all revenue at start";
    if (ruleType === "straight_line") return "Straight-line: recognize evenly over contract term";
    return `${ruleType}: custom rule`;
  }

  // -----------------------------
  // UI
  // -----------------------------
  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Contracts</h1>

      <Card className="p-4 space-y-3">
        <h2 className="font-medium text-sm text-gray-700">Contract Details</h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
          <Input
            value={contract_id}
            onChange={(e) => setContractId(e.target.value)}
            placeholder="Contract ID"
          />
          <Input
            value={customer}
            onChange={(e) => setCustomer(e.target.value)}
            placeholder="Customer"
          />
          <Input
            type="number"
            value={transaction_price}
            onChange={(e) => setTxnPrice(parseFloat(e.target.value || "0"))}
            placeholder="Transaction Price"
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
          <Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
          <Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
          <Button variant="secondary" onClick={loadReferenceData}>
            Refresh Catalog / Rules
          </Button>
        </div>
      </Card>

      {/* Summary cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="p-4">
          <div className="text-xs text-gray-500">Contract Transaction Price</div>
          <div className="text-lg font-semibold">
            ${Number(transaction_price || 0).toLocaleString()}
          </div>
        </Card>

        <Card className="p-4">
          <div className="text-xs text-gray-500">Line Sell Prices Total</div>
          <div className="text-lg font-semibold">${totalLineSellPrices.toLocaleString()}</div>
        </Card>

        <Card className="p-4">
          <div className="text-xs text-gray-500">
            {backendAllocations.length > 0 ? "Allocated Total (Backend)" : "Allocated Preview (SSP)"}
          </div>
          <div className="text-lg font-semibold">
            ${Number(displayedAllocatedTotal).toLocaleString(undefined, { maximumFractionDigits: 2 })}
          </div>
          <div
            className={`text-xs ${
              Math.abs(contractVsAllocatedDiff) < 0.01 ? "text-green-600" : "text-amber-600"
            }`}
          >
            Diff vs contract: {contractVsAllocatedDiff.toFixed(2)}
          </div>
        </Card>

        <Card className="p-4">
          <div className="text-xs text-gray-500">Total SSP</div>
          <div className="text-lg font-semibold">
            ${Number(totalSSP).toLocaleString(undefined, { maximumFractionDigits: 2 })}
          </div>
        </Card>
      </div>

      {/* Line items + previews */}
      <Card className="p-4 space-y-3">
        <h2 className="font-medium text-sm text-gray-700">Line Items + Rule Previews</h2>

        {items.map((item, idx) => {
          const p = catalogMap[item.product_code];
          return (
            <div key={idx} className="border rounded-md p-3 space-y-2">
              <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
                <Input
                  value={item.product_code}
                  onChange={(e) => updateItem(idx, "product_code", e.target.value)}
                  placeholder="SKU-001"
                />
                <Input
                  value={item.amount}
                  type="number"
                  onChange={(e) => updateItem(idx, "amount", e.target.value)}
                  placeholder="Selling Price"
                />
                <div className="border rounded px-3 py-2 text-sm bg-gray-50">
                  SSP: {p ? `$${Number(p.ssp || 0).toLocaleString()}` : "Not found"}
                </div>
                <Button
                  variant="destructive"
                  onClick={() => setItems(items.filter((_, i) => i !== idx))}
                >
                  Remove
                </Button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-xs">
                <div className="border rounded px-2 py-2 bg-gray-50">
                  <span className="text-gray-500">Name: </span>
                  <span>{p?.name || "Unknown"}</span>
                </div>
                <div className="border rounded px-2 py-2 bg-gray-50">
                  <span className="text-gray-500">RevRec Code: </span>
                  <span>{p?.revrec_code || "None"}</span>
                </div>
                <div className="border rounded px-2 py-2 bg-gray-50">
                  <span className="text-gray-500">Rule Preview: </span>
                  <span>{getRulePreview(item.product_code)}</span>
                </div>
              </div>
            </div>
          );
        })}

        <Button
          variant="outline"
          onClick={() => setItems([...items, { product_code: "", amount: 0 }])}
        >
          + Add Line
        </Button>
      </Card>

      {/* SSP Allocation Preview */}
      <Card className="p-4 space-y-3">
        <h2 className="font-medium text-sm text-gray-700">SSP Allocation Preview</h2>

        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50">
                <th className="p-2 text-left">Product</th>
                <th className="p-2 text-left">Name</th>
                <th className="p-2 text-right">Sell Price</th>
                <th className="p-2 text-right">SSP</th>
                <th className="p-2 text-right">SSP %</th>
                <th className="p-2 text-right">Allocated Preview</th>
                <th className="p-2 text-left">Rule</th>
              </tr>
            </thead>
            <tbody>
              {sspAllocationPreview.map((r, idx) => (
                <tr key={`${r.product_code}-${idx}`} className="border-b">
                  <td className="p-2">{r.product_code}</td>
                  <td className="p-2">{r.product_name || "-"}</td>
                  <td className="p-2 text-right">${Number(r.amount || 0).toLocaleString()}</td>
                  <td className="p-2 text-right">${Number(r.ssp || 0).toLocaleString()}</td>
                  <td className="p-2 text-right">{(r.ssp_pct * 100).toFixed(2)}%</td>
                  <td className="p-2 text-right">
                    ${Number(r.alloc_preview || 0).toLocaleString(undefined, {
                      maximumFractionDigits: 2,
                    })}
                  </td>
                  <td className="p-2">{r.rule_type || r.revrec_code || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Actions */}
      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" onClick={saveContract}>
          Save Contract
        </Button>
        <Button onClick={allocate}>Allocate Revenue</Button>
        <Button variant="secondary" onClick={aiGenerate}>
          AI Build Schedule
        </Button>
        <Button variant="outline" onClick={reloadSchedule}>
          Reload Schedule
        </Button>
      </div>

      {/* Backend allocation result */}
      {backendAllocations.length > 0 && (
        <Card className="p-4 space-y-3">
          <h2 className="font-medium">Backend Allocation Result</h2>

          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50">
                  <th className="p-2 text-left">Product</th>
                  <th className="p-2 text-left">RevRec Code</th>
                  <th className="p-2 text-left">Rule</th>
                  <th className="p-2 text-right">Allocated Total</th>
                  <th className="p-2 text-right">Monthly Amount</th>
                  <th className="p-2 text-right">Months</th>
                </tr>
              </thead>
              <tbody>
                {backendAllocations.map((a, i) => (
                  <tr key={`${a.product_code}-${i}`} className="border-b">
                    <td className="p-2">{a.product_code}</td>
                    <td className="p-2">{a.revrec_code || "-"}</td>
                    <td className="p-2">{a.rule_type || "-"}</td>
                    <td className="p-2 text-right">
                      ${Number(a.allocated_total || 0).toLocaleString(undefined, {
                        maximumFractionDigits: 2,
                      })}
                    </td>
                    <td className="p-2 text-right">
                      ${Number(a.monthly_amount || 0).toLocaleString(undefined, {
                        maximumFractionDigits: 2,
                      })}
                    </td>
                    <td className="p-2 text-right">{a.months ?? "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Waterfall */}
      <Card className="p-4 space-y-3">
        <h2 className="font-medium">Interactive Revenue Waterfall</h2>

        {monthlyWaterfall.length === 0 ? (
          <div className="text-sm text-gray-500">
            No schedule rows yet. Click <span className="font-medium">Save Contract</span> then{" "}
            <span className="font-medium">Allocate Revenue</span>.
          </div>
        ) : (
          <div className="space-y-2">
            {monthlyWaterfall.map((r) => (
              <div
                key={r.period}
                className="grid grid-cols-[90px_1fr_120px] gap-2 items-center text-sm"
              >
                <div>{r.period}</div>
                <div className="h-4 bg-gray-100 rounded overflow-hidden">
                  <div
                    className="h-4 bg-blue-500"
                    style={{ width: `${(Number(r.amount || 0) / maxWaterfall) * 100}%` }}
                    title={`${r.period}: $${Number(r.amount).toLocaleString()}`}
                  />
                </div>
                <div className="text-right">${Number(r.amount).toLocaleString()}</div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Full schedule grid */}
      {scheduleGrid.length > 0 && (
        <Card className="p-4 space-y-3">
          <h2 className="font-medium">Revenue Schedule Grid</h2>

          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50">
                  <th className="p-2">Line</th>
                  <th className="p-2 text-left">Period</th>
                  <th className="p-2 text-right">Amount</th>
                  <th className="p-2 text-left">Product</th>
                  <th className="p-2 text-left">Product Name</th>
                  <th className="p-2 text-right">SSP</th>
                  <th className="p-2 text-left">RevRec</th>
                  <th className="p-2 text-left">Rule</th>
                  <th className="p-2 text-left">Source</th>
                </tr>
              </thead>
              <tbody>
                {scheduleGrid.map((r, idx) => (
                  <tr key={`${r.period}-${r.product_code}-${idx}`} className="border-b">
                    <td className="p-2 text-center">{r.line_no ?? idx + 1}</td>
                    <td className="p-2">{r.period}</td>
                    <td className="p-2 text-right">
                      ${Number(r.amount || 0).toLocaleString(undefined, {
                        maximumFractionDigits: 2,
                      })}
                    </td>
                    <td className="p-2">{r.product_code || "-"}</td>
                    <td className="p-2">{r.product_name || "-"}</td>
                    <td className="p-2 text-right">
                      {r.ssp != null ? `$${Number(r.ssp).toLocaleString()}` : "-"}
                    </td>
                    <td className="p-2">{r.revrec_code || "-"}</td>
                    <td className="p-2">{r.rule_type || "-"}</td>
                    <td className="p-2">{r.source || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Raw JSON */}
      {allocResult && (
        <Card className="p-4">
          <h2 className="font-medium mb-2">Raw Allocation JSON</h2>
          <pre className="bg-gray-50 p-4 rounded text-xs overflow-x-auto">
            {JSON.stringify(allocResult, null, 2)}
          </pre>
        </Card>
      )}
    </div>
  );
}
