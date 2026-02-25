"use client";

import { useMemo, useState } from "react";
import { api } from "@/src/lib/api";
import { Input } from "@/src/components/ui/input";
import { Button } from "@/src/components/ui/button";
import { Card } from "@/src/components/ui/card";
import { toast } from "sonner";

type TempDiffRow = {
  label: string;
  period: string;
  amount: number; // book - tax
  reversal_year: number;
  va_pct: number;
};

type PermanentDiffRow = {
  label: string;
  amount: number; // if pre_tax: pretax permanent difference amount; if direct_tax: direct tax effect $
  treatment: "pre_tax" | "direct_tax";
  direction: "increase_tax" | "decrease_tax";
  category:
    | "stock_comp"
    | "meals"
    | "penalties"
    | "tax_credits"
    | "other";
};

type TaxCalcResult = {
  gross?: { DTL: number; DTA: number };
  valuation_allowance?: number;
  net_deferred_tax?: number;
  mapping?: any[];
  reversal_buckets?: Record<string, number>;
};

export default function TaxPage() {
  const [company, setCompany] = useState("Acme Inc");

  // rate setup
  const [rateMode, setRateMode] = useState<"statutory" | "blended">("statutory");
  const [statutoryRate, setStatutoryRate] = useState(0.21);
  const [federalRate, setFederalRate] = useState(0.21);
  const [stateRate, setStateRate] = useState(0.05);
  const [stateDeductibleFederal, setStateDeductibleFederal] = useState(true);

  // tax provision inputs
  const [pretaxBookIncome, setPretaxBookIncome] = useState<number>(100000);
  const [beginningCurrentTaxExpense, setBeginningCurrentTaxExpense] = useState<number>(0); // optional placeholder if you expand later
  const [beginningNetDeferredTax, setBeginningNetDeferredTax] = useState<number>(0);
  const [globalVAFallback, setGlobalVAFallback] = useState<number>(0);

  // temporary differences (ASC 740 deferred)
  const [tempDiffs, setTempDiffs] = useState<TempDiffRow[]>([
    { label: "Depreciation", period: "2025-12", amount: 10000, reversal_year: 2026, va_pct: 0 },
    { label: "Warranty Reserve", period: "2026-12", amount: -5000, reversal_year: 2027, va_pct: 0.1 },
  ]);

  // permanent differences (ETR bridge)
  const [permDiffs, setPermDiffs] = useState<PermanentDiffRow[]>([
    {
      label: "Meals (50% nondeductible)",
      amount: 2000,
      treatment: "pre_tax",
      direction: "increase_tax",
      category: "meals",
    },
    {
      label: "Tax credits",
      amount: 1500,
      treatment: "direct_tax",
      direction: "decrease_tax",
      category: "tax_credits",
    },
  ]);

  const [result, setResult] = useState<TaxCalcResult | null>(null);
  const [memo, setMemo] = useState("");
  const [error, setError] = useState("");

  const taxRateUsed = useMemo(() => {
    if (rateMode === "statutory") return statutoryRate;
    return stateDeductibleFederal
      ? federalRate + stateRate * (1 - federalRate)
      : federalRate + stateRate;
  }, [rateMode, statutoryRate, federalRate, stateRate, stateDeductibleFederal]);

  function addTempRow() {
    setTempDiffs((prev) => [
      ...prev,
      { label: "", period: "2026-12", amount: 0, reversal_year: 2027, va_pct: 0 },
    ]);
  }

  function updateTempRow<K extends keyof TempDiffRow>(idx: number, key: K, value: TempDiffRow[K]) {
    setTempDiffs((prev) => {
      const copy = [...prev];
      copy[idx] = { ...copy[idx], [key]: value };
      return copy;
    });
  }

  function removeTempRow(idx: number) {
    setTempDiffs((prev) => prev.filter((_, i) => i !== idx));
  }

  function addPermRow() {
    setPermDiffs((prev) => [
      ...prev,
      {
        label: "",
        amount: 0,
        treatment: "pre_tax",
        direction: "increase_tax",
        category: "other",
      },
    ]);
  }

  function updatePermRow<K extends keyof PermanentDiffRow>(
    idx: number,
    key: K,
    value: PermanentDiffRow[K]
  ) {
    setPermDiffs((prev) => {
      const copy = [...prev];
      copy[idx] = { ...copy[idx], [key]: value };
      return copy;
    });
  }

  function removePermRow(idx: number) {
    setPermDiffs((prev) => prev.filter((_, i) => i !== idx));
  }

  async function runCalc() {
    setError("");
    try {
      const payload: any = {
        company,
        valuation_allowance_pct: globalVAFallback,
        use_blended_rate: rateMode === "blended",
        state_deductible_federal: stateDeductibleFederal,
        beginning_net_deferred_tax: beginningNetDeferredTax,
        pretax_book_income: pretaxBookIncome,
        differences: tempDiffs.map((r) => ({
          label: r.label || "Unlabeled Temp Difference",
          period: r.period,
          amount: Number(r.amount),
          reversal_year: Number(r.reversal_year),
          va_pct: Number(r.va_pct || 0),
        })),
      };

      if (rateMode === "statutory") {
        payload.statutory_rate = Number(statutoryRate);
      } else {
        payload.federal_rate = Number(federalRate);
        payload.state_rate = Number(stateRate);
      }

      const res = await api("/tax/asc740/calc", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      setResult(res);
      toast.success("ASC 740 calculation complete");
    } catch (e: any) {
      setError(e?.message || "Calculation failed");
      toast.error(e?.message || "Calculation failed");
    }
  }

  async function runMemo() {
    setError("");
    try {
      const payload: any = {
        company,
        valuation_allowance_pct: globalVAFallback,
        use_blended_rate: rateMode === "blended",
        state_deductible_federal: stateDeductibleFederal,
        beginning_net_deferred_tax: beginningNetDeferredTax,
        pretax_book_income: pretaxBookIncome,
        differences: tempDiffs.map((r) => ({
          label: r.label || "Unlabeled Temp Difference",
          period: r.period,
          amount: Number(r.amount),
          reversal_year: Number(r.reversal_year),
          va_pct: Number(r.va_pct || 0),
        })),
      };

      if (rateMode === "statutory") {
        payload.statutory_rate = Number(statutoryRate);
      } else {
        payload.federal_rate = Number(federalRate);
        payload.state_rate = Number(stateRate);
      }

      const res = await api("/tax/asc740/memo", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      setMemo(res.memo || "");
      toast.success("Memo generated");
    } catch (e: any) {
      setError(e?.message || "Memo generation failed");
      toast.error(e?.message || "Memo generation failed");
    }
  }

  const etrBridge = useMemo(() => {
    const pretax = Number(pretaxBookIncome || 0);
    const expectedTax = pretax * taxRateUsed;

    // Permanent differences tax effects
    const permRows = permDiffs.map((r) => {
      const sign = r.direction === "increase_tax" ? 1 : -1;

      // pre_tax items are tax-effected by rate
      // direct_tax items are already tax-effect dollars (e.g., credits)
      const taxEffect =
        r.treatment === "pre_tax"
          ? sign * (Number(r.amount || 0) * taxRateUsed)
          : sign * Number(r.amount || 0);

      return {
        ...r,
        taxEffect: Number.isFinite(taxEffect) ? taxEffect : 0,
      };
    });

    const totalPermanentImpact = permRows.reduce((s, r) => s + r.taxEffect, 0);

    const vaImpact = Number(result?.valuation_allowance || 0);

    // Illustrative tax expense = expected + permanent impacts + VA
    // (Deferred impacts are already represented in deferred balances, not directly added here unless you build full provision engine.)
    const totalTaxExpenseIllustrative = expectedTax + totalPermanentImpact + vaImpact;
    const effectiveTaxRate = pretax !== 0 ? totalTaxExpenseIllustrative / pretax : 0;

    return {
      pretax,
      rate: taxRateUsed,
      expectedTax,
      permRows,
      totalPermanentImpact,
      vaImpact,
      totalTaxExpenseIllustrative,
      effectiveTaxRate,
    };
  }, [pretaxBookIncome, taxRateUsed, permDiffs, result?.valuation_allowance]);

  function downloadMemo() {
    if (!memo) return;
    const blob = new Blob([memo], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${company.replace(/\s+/g, "_")}_ASC740_Memo.txt`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <h1 className="text-2xl font-semibold">ASC 740 Deferred Tax + ETR Bridge</h1>

      {/* Setup */}
      <Card className="p-4 space-y-4">
        <h2 className="font-medium text-sm text-gray-700">Tax Setup</h2>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
          <Input value={company} onChange={(e) => setCompany(e.target.value)} placeholder="Company" />
          <select
            className="border rounded px-2 py-1"
            value={rateMode}
            onChange={(e) => setRateMode(e.target.value as any)}
          >
            <option value="statutory">Statutory Rate</option>
            <option value="blended">Federal + State (Blended)</option>
          </select>

          {rateMode === "statutory" ? (
            <Input
              type="number"
              step="0.0001"
              value={statutoryRate}
              onChange={(e) => setStatutoryRate(Number(e.target.value || 0))}
              placeholder="Statutory rate"
            />
          ) : (
            <>
              <Input
                type="number"
                step="0.0001"
                value={federalRate}
                onChange={(e) => setFederalRate(Number(e.target.value || 0))}
                placeholder="Federal rate"
              />
              <Input
                type="number"
                step="0.0001"
                value={stateRate}
                onChange={(e) => setStateRate(Number(e.target.value || 0))}
                placeholder="State rate"
              />
            </>
          )}
        </div>

        {rateMode === "blended" && (
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={stateDeductibleFederal}
              onChange={(e) => setStateDeductibleFederal(e.target.checked)}
            />
            State tax deductible for federal (blended formula)
          </label>
        )}

        <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
          <Input
            type="number"
            value={pretaxBookIncome}
            onChange={(e) => setPretaxBookIncome(Number(e.target.value || 0))}
            placeholder="Pretax book income"
          />
          <Input
            type="number"
            value={beginningNetDeferredTax}
            onChange={(e) => setBeginningNetDeferredTax(Number(e.target.value || 0))}
            placeholder="Beginning net deferred tax"
          />
          <Input
            type="number"
            step="0.0001"
            value={globalVAFallback}
            onChange={(e) => setGlobalVAFallback(Number(e.target.value || 0))}
            placeholder="Global VA fallback %"
          />
          <Input
            type="number"
            value={beginningCurrentTaxExpense}
            onChange={(e) => setBeginningCurrentTaxExpense(Number(e.target.value || 0))}
            placeholder="Current tax exp (optional)"
          />
        </div>

        <div className="text-xs text-gray-500">
          Tax rate used (current view): {(taxRateUsed * 100).toFixed(2)}%
        </div>
      </Card>

      {/* Temporary Differences */}
      <Card className="p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="font-medium text-sm text-gray-700">Temporary Differences (Deferred Tax)</h2>
          <Button onClick={addTempRow} variant="outline">+ Add Temp Diff</Button>
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="p-2 text-left">Label</th>
                <th className="p-2 text-left">Period</th>
                <th className="p-2 text-right">Amount</th>
                <th className="p-2 text-right">Reversal Year</th>
                <th className="p-2 text-right">Row VA %</th>
                <th className="p-2 text-left">Type</th>
                <th className="p-2"></th>
              </tr>
            </thead>
            <tbody>
              {tempDiffs.map((r, idx) => (
                <tr key={idx} className="border-t">
                  <td className="p-2 min-w-[180px]">
                    <Input
                      value={r.label}
                      onChange={(e) => updateTempRow(idx, "label", e.target.value)}
                      placeholder="Depreciation"
                    />
                  </td>
                  <td className="p-2 min-w-[120px]">
                    <Input
                      value={r.period}
                      onChange={(e) => updateTempRow(idx, "period", e.target.value)}
                      placeholder="2026-12"
                    />
                  </td>
                  <td className="p-2 min-w-[120px]">
                    <Input
                      type="number"
                      value={r.amount}
                      onChange={(e) => updateTempRow(idx, "amount", Number(e.target.value || 0))}
                    />
                  </td>
                  <td className="p-2 min-w-[120px]">
                    <Input
                      type="number"
                      value={r.reversal_year}
                      onChange={(e) =>
                        updateTempRow(idx, "reversal_year", Number(e.target.value || 0))
                      }
                    />
                  </td>
                  <td className="p-2 min-w-[100px]">
                    <Input
                      type="number"
                      step="0.0001"
                      value={r.va_pct}
                      onChange={(e) => updateTempRow(idx, "va_pct", Number(e.target.value || 0))}
                    />
                  </td>
                  <td className="p-2 text-xs">
                    {r.amount > 0 ? "DTL" : r.amount < 0 ? "DTA" : "NONE"}
                  </td>
                  <td className="p-2">
                    <Button variant="destructive" onClick={() => removeTempRow(idx)}>
                      Remove
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Permanent Differences / ETR categories */}
      <Card className="p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="font-medium text-sm text-gray-700">Permanent Differences (ETR Bridge)</h2>
          <Button onClick={addPermRow} variant="outline">+ Add Permanent Diff</Button>
        </div>

        <div className="text-xs text-gray-500">
          Use <b>pre_tax</b> for items like meals/penalties/stock comp permanent differences.
          Use <b>direct_tax</b> for tax credits or direct tax adjustments.
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="p-2 text-left">Label</th>
                <th className="p-2 text-left">Category</th>
                <th className="p-2 text-left">Treatment</th>
                <th className="p-2 text-left">Direction</th>
                <th className="p-2 text-right">Amount</th>
                <th className="p-2 text-right">Tax Effect</th>
                <th className="p-2"></th>
              </tr>
            </thead>
            <tbody>
              {permDiffs.map((r, idx) => {
                const sign = r.direction === "increase_tax" ? 1 : -1;
                const taxEffect =
                  r.treatment === "pre_tax"
                    ? sign * r.amount * taxRateUsed
                    : sign * r.amount;

                return (
                  <tr key={idx} className="border-t">
                    <td className="p-2 min-w-[220px]">
                      <Input
                        value={r.label}
                        onChange={(e) => updatePermRow(idx, "label", e.target.value)}
                        placeholder="Meals 50% disallowed"
                      />
                    </td>
                    <td className="p-2 min-w-[140px]">
                      <select
                        className="border rounded px-2 py-1 w-full"
                        value={r.category}
                        onChange={(e) => updatePermRow(idx, "category", e.target.value as any)}
                      >
                        <option value="stock_comp">stock_comp</option>
                        <option value="meals">meals</option>
                        <option value="penalties">penalties</option>
                        <option value="tax_credits">tax_credits</option>
                        <option value="other">other</option>
                      </select>
                    </td>
                    <td className="p-2 min-w-[120px]">
                      <select
                        className="border rounded px-2 py-1 w-full"
                        value={r.treatment}
                        onChange={(e) => updatePermRow(idx, "treatment", e.target.value as any)}
                      >
                        <option value="pre_tax">pre_tax</option>
                        <option value="direct_tax">direct_tax</option>
                      </select>
                    </td>
                    <td className="p-2 min-w-[150px]">
                      <select
                        className="border rounded px-2 py-1 w-full"
                        value={r.direction}
                        onChange={(e) => updatePermRow(idx, "direction", e.target.value as any)}
                      >
                        <option value="increase_tax">increase_tax</option>
                        <option value="decrease_tax">decrease_tax</option>
                      </select>
                    </td>
                    <td className="p-2 min-w-[110px]">
                      <Input
                        type="number"
                        value={r.amount}
                        onChange={(e) => updatePermRow(idx, "amount", Number(e.target.value || 0))}
                      />
                    </td>
                    <td className="p-2 text-right">
                      {taxEffect.toFixed(2)}
                    </td>
                    <td className="p-2">
                      <Button variant="destructive" onClick={() => removePermRow(idx)}>
                        Remove
                      </Button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Actions */}
      <div className="flex gap-2">
        <Button onClick={runCalc}>Compute Deferred Tax</Button>
        <Button onClick={runMemo} variant="secondary">Generate Memo</Button>
        <Button onClick={downloadMemo} variant="outline" disabled={!memo}>
          Download Memo
        </Button>
      </div>

      {error && <div className="text-red-600 text-sm whitespace-pre-wrap">{error}</div>}

      {/* Deferred tax summary */}
      {result && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Card className="p-4">
              <div className="text-xs text-gray-500">Gross DTL</div>
              <div className="text-lg font-semibold">
                ${Number(result.gross?.DTL || 0).toLocaleString()}
              </div>
            </Card>
            <Card className="p-4">
              <div className="text-xs text-gray-500">Gross DTA</div>
              <div className="text-lg font-semibold">
                ${Number(result.gross?.DTA || 0).toLocaleString()}
              </div>
            </Card>
            <Card className="p-4">
              <div className="text-xs text-gray-500">Valuation Allowance</div>
              <div className="text-lg font-semibold">
                ${Number(result.valuation_allowance || 0).toLocaleString()}
              </div>
            </Card>
            <Card className="p-4">
              <div className="text-xs text-gray-500">Net Deferred Tax</div>
              <div className="text-lg font-semibold">
                ${Number(result.net_deferred_tax || 0).toLocaleString()}
              </div>
              <div className="text-xs text-gray-500">
                {Number(result.net_deferred_tax || 0) >= 0 ? "Net DTA" : "Net DTL"}
              </div>
            </Card>
          </div>

          {/* Mapping detail */}
          <Card className="p-4">
            <h2 className="font-medium text-sm text-gray-700 mb-2">Deferred Tax Mapping</h2>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="p-2 text-left">Label</th>
                    <th className="p-2 text-left">Period</th>
                    <th className="p-2 text-right">Temp Diff</th>
                    <th className="p-2 text-left">Type</th>
                    <th className="p-2 text-right">Deferred Tax</th>
                    <th className="p-2 text-right">VA %</th>
                    <th className="p-2 text-right">VA $</th>
                    <th className="p-2 text-right">Reversal Year</th>
                  </tr>
                </thead>
                <tbody>
                  {(result.mapping || []).map((m: any, idx: number) => (
                    <tr key={idx} className="border-t">
                      <td className="p-2">{m.label}</td>
                      <td className="p-2">{m.period}</td>
                      <td className="p-2 text-right">{Number(m.temp_diff || 0).toFixed(2)}</td>
                      <td className="p-2">{m.type}</td>
                      <td className="p-2 text-right">{Number(m.deferred_tax || 0).toFixed(2)}</td>
                      <td className="p-2 text-right">{((Number(m.va_pct || 0)) * 100).toFixed(2)}%</td>
                      <td className="p-2 text-right">{Number(m.valuation_allowance || 0).toFixed(2)}</td>
                      <td className="p-2 text-right">{m.reversal_year}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}

      {/* ETR Bridge */}
      <Card className="p-4 space-y-3">
        <h2 className="font-medium text-sm text-gray-700">ETR Bridge (Illustrative)</h2>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-sm">
          <div className="border rounded p-3">
            <div className="text-xs text-gray-500">Pretax Book Income</div>
            <div className="font-semibold">{etrBridge.pretax.toFixed(2)}</div>
          </div>
          <div className="border rounded p-3">
            <div className="text-xs text-gray-500">Expected Tax @ Rate</div>
            <div className="font-semibold">{etrBridge.expectedTax.toFixed(2)}</div>
          </div>
          <div className="border rounded p-3">
            <div className="text-xs text-gray-500">Permanent Diff Impact</div>
            <div className="font-semibold">{etrBridge.totalPermanentImpact.toFixed(2)}</div>
          </div>
          <div className="border rounded p-3">
            <div className="text-xs text-gray-500">Valuation Allowance Impact</div>
            <div className="font-semibold">{etrBridge.vaImpact.toFixed(2)}</div>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="p-2 text-left">Bridge Line</th>
                <th className="p-2 text-right">Amount</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-t">
                <td className="p-2">Expected tax at statutory/blended rate</td>
                <td className="p-2 text-right">{etrBridge.expectedTax.toFixed(2)}</td>
              </tr>

              {etrBridge.permRows.map((r, idx) => (
                <tr key={idx} className="border-t">
                  <td className="p-2">
                    {r.label || "Permanent Difference"} ({r.category}, {r.treatment})
                  </td>
                  <td className="p-2 text-right">{r.taxEffect.toFixed(2)}</td>
                </tr>
              ))}

              <tr className="border-t">
                <td className="p-2">Valuation allowance</td>
                <td className="p-2 text-right">{etrBridge.vaImpact.toFixed(2)}</td>
              </tr>

              <tr className="border-t font-semibold">
                <td className="p-2">Illustrative total tax expense</td>
                <td className="p-2 text-right">{etrBridge.totalTaxExpenseIllustrative.toFixed(2)}</td>
              </tr>

              <tr className="border-t font-semibold">
                <td className="p-2">Illustrative effective tax rate</td>
                <td className="p-2 text-right">
                  {(etrBridge.effectiveTaxRate * 100).toFixed(2)}%
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </Card>

      {memo && (
        <Card className="p-4">
          <h2 className="font-medium text-sm text-gray-700 mb-2">Memo Preview</h2>
          <pre className="text-xs bg-slate-50 p-3 rounded border overflow-x-auto whitespace-pre-wrap">
            {memo}
          </pre>
        </Card>
      )}
    </div>
  );
}
