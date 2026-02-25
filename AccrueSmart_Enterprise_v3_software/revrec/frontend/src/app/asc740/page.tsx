"use client";

import { useMemo, useState } from "react";
import { api } from "@/src/lib/api";
import { Input } from "@/src/components/ui/input";
import { Button } from "@/src/components/ui/button";
import { Card } from "@/src/components/ui/card";
import { toast } from "sonner";

type TempDiffRow = {
  period: string;          // e.g. 2026-12
  amount: number;          // book - tax
  reversal_year: number;   // e.g. 2027
};

type Asc740Result = {
  statutory_rate: number;
  gross: {
    DTL: number;
    DTA: number;
  };
  valuation_allowance: number;
  net_deferred_tax: number;
  reversal_buckets: Record<string, number>;
  mapping: Array<{
    period: string;
    temp_diff: number;
    deferred_tax: number;
    type: "DTL" | "DTA";
  }>;
  memo?: string;
};

export default function ASC740Page() {
  const [company, setCompany] = useState("DemoCo");
  const [statutoryRate, setStatutoryRate] = useState(0.21);
  const [valuationAllowancePct, setValuationAllowancePct] = useState(0.0);

  const [diffs, setDiffs] = useState<TempDiffRow[]>([
    { period: "2026-12", amount: 50000, reversal_year: 2027 },   // DTL
    { period: "2026-12", amount: -20000, reversal_year: 2028 },  // DTA
  ]);

  const [result, setResult] = useState<Asc740Result | null>(null);
  const [memo, setMemo] = useState<string>("");

  function updateDiff(idx: number, field: keyof TempDiffRow, value: string) {
    const next = [...diffs];
    next[idx] = {
      ...next[idx],
      [field]:
        field === "amount"
          ? parseFloat(value || "0")
          : field === "reversal_year"
          ? parseInt(value || "0", 10)
          : value,
    } as TempDiffRow;
    setDiffs(next);
  }

  function addRow() {
    setDiffs([
      ...diffs,
      { period: "2026-12", amount: 0, reversal_year: new Date().getFullYear() + 1 },
    ]);
  }

  function removeRow(idx: number) {
    setDiffs(diffs.filter((_, i) => i !== idx));
  }

  async function runASC740() {
    try {
      const payload = {
        company,
        statutory_rate: Number(statutoryRate || 0),
        valuation_allowance_pct: Number(valuationAllowancePct || 0),
        differences: diffs.map((d) => ({
          period: d.period,
          amount: Number(d.amount || 0),
          reversal_year: Number(d.reversal_year || 0),
        })),
      };

      const res = await api("/tax/asc740", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      // expected shape:
      // { results: {...}, memo: "..." } OR direct result shape
      const parsedResult = res.results ?? res;
      setResult(parsedResult);
      setMemo(res.memo || parsedResult.memo || "");
      toast.success("ASC 740 calculation complete");
    } catch (e: any) {
      console.error(e);
      toast.error(e?.message || "ASC 740 calculation failed");
    }
  }

  const totalTempDiff = useMemo(
    () => diffs.reduce((sum, d) => sum + Number(d.amount || 0), 0),
    [diffs]
  );

  const taxableCount = useMemo(
    () => diffs.filter((d) => Number(d.amount) > 0).length,
    [diffs]
  );

  const deductibleCount = useMemo(
    () => diffs.filter((d) => Number(d.amount) < 0).length,
    [diffs]
  );

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">ASC 740 Deferred Tax</h1>

      {/* Inputs */}
      <Card className="p-4 space-y-3">
        <h2 className="font-medium text-sm text-gray-700">Tax Inputs</h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
          <Input
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            placeholder="Company Name"
          />
          <Input
            type="number"
            step="0.01"
            value={statutoryRate}
            onChange={(e) => setStatutoryRate(parseFloat(e.target.value || "0"))}
            placeholder="Statutory Rate (e.g. 0.21)"
          />
          <Input
            type="number"
            step="0.01"
            value={valuationAllowancePct}
            onChange={(e) => setValuationAllowancePct(parseFloat(e.target.value || "0"))}
            placeholder="Valuation Allowance % (e.g. 0.25)"
          />
        </div>

        <div className="text-xs text-gray-500">
          Enter rates as decimals (0.21 = 21%).
        </div>
      </Card>

      {/* Temp Differences */}
      <Card className="p-4 space-y-3">
        <h2 className="font-medium text-sm text-gray-700">Temporary Differences</h2>

        <div className="text-xs text-gray-500">
          Amount = Book Basis − Tax Basis. Positive = future taxable (DTL). Negative = future deductible (DTA).
        </div>

        {diffs.map((row, idx) => (
          <div key={idx} className="grid grid-cols-1 md:grid-cols-4 gap-2">
            <Input
              value={row.period}
              onChange={(e) => updateDiff(idx, "period", e.target.value)}
              placeholder="Period (YYYY-MM)"
            />
            <Input
              type="number"
              value={row.amount}
              onChange={(e) => updateDiff(idx, "amount", e.target.value)}
              placeholder="Temp Diff Amount"
            />
            <Input
              type="number"
              value={row.reversal_year}
              onChange={(e) => updateDiff(idx, "reversal_year", e.target.value)}
              placeholder="Reversal Year"
            />
            <Button variant="destructive" onClick={() => removeRow(idx)}>
              Remove
            </Button>
          </div>
        ))}

        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={addRow}>
            + Add Difference
          </Button>
          <Button onClick={runASC740}>Compute ASC 740</Button>
        </div>
      </Card>

      {/* Quick Summary */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="p-4">
          <div className="text-xs text-gray-500">Temp Diff Rows</div>
          <div className="text-lg font-semibold">{diffs.length}</div>
        </Card>

        <Card className="p-4">
          <div className="text-xs text-gray-500">Taxable Differences</div>
          <div className="text-lg font-semibold">{taxableCount}</div>
        </Card>

        <Card className="p-4">
          <div className="text-xs text-gray-500">Deductible Differences</div>
          <div className="text-lg font-semibold">{deductibleCount}</div>
        </Card>

        <Card className="p-4">
          <div className="text-xs text-gray-500">Net Temp Difference</div>
          <div className="text-lg font-semibold">
            ${Number(totalTempDiff).toLocaleString(undefined, { maximumFractionDigits: 2 })}
          </div>
        </Card>
      </div>

      {/* Results */}
      {result && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Card className="p-4">
              <div className="text-xs text-gray-500">Gross DTL</div>
              <div className="text-lg font-semibold">
                ${Number(result.gross?.DTL || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}
              </div>
            </Card>

            <Card className="p-4">
              <div className="text-xs text-gray-500">Gross DTA</div>
              <div className="text-lg font-semibold">
                ${Number(result.gross?.DTA || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}
              </div>
            </Card>

            <Card className="p-4">
              <div className="text-xs text-gray-500">Valuation Allowance</div>
              <div className="text-lg font-semibold">
                ${Number(result.valuation_allowance || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}
              </div>
            </Card>

            <Card className="p-4">
              <div className="text-xs text-gray-500">Net Deferred Tax</div>
              <div className="text-lg font-semibold">
                ${Number(result.net_deferred_tax || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}
              </div>
            </Card>
          </div>

          {/* Mapping Table */}
          <Card className="p-4 space-y-3">
            <h2 className="font-medium">Deferred Tax Mapping</h2>

            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="border-b bg-gray-50">
                    <th className="p-2 text-left">Period</th>
                    <th className="p-2 text-right">Temp Diff</th>
                    <th className="p-2 text-right">Deferred Tax</th>
                    <th className="p-2 text-left">Type</th>
                  </tr>
                </thead>
                <tbody>
                  {(result.mapping || []).map((m, idx) => (
                    <tr key={`${m.period}-${idx}`} className="border-b">
                      <td className="p-2">{m.period}</td>
                      <td className="p-2 text-right">
                        ${Number(m.temp_diff).toLocaleString(undefined, { maximumFractionDigits: 2 })}
                      </td>
                      <td className="p-2 text-right">
                        ${Number(m.deferred_tax).toLocaleString(undefined, { maximumFractionDigits: 2 })}
                      </td>
                      <td className="p-2">{m.type}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {/* Reversal Buckets */}
          <Card className="p-4 space-y-3">
            <h2 className="font-medium">Reversal Timing Buckets</h2>

            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="border-b bg-gray-50">
                    <th className="p-2 text-left">Year</th>
                    <th className="p-2 text-right">Net Temporary Difference</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(result.reversal_buckets || {})
                    .sort(([a], [b]) => Number(a) - Number(b))
                    .map(([year, amt]) => (
                      <tr key={year} className="border-b">
                        <td className="p-2">{year}</td>
                        <td className="p-2 text-right">
                          ${Number(amt).toLocaleString(undefined, { maximumFractionDigits: 2 })}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </Card>

          {/* AI Memo */}
          {(memo || result.memo) && (
            <Card className="p-4">
              <h2 className="font-medium mb-2">ASC 740 Memo</h2>
              <pre className="bg-gray-50 p-4 rounded text-xs whitespace-pre-wrap overflow-x-auto">
                {memo || result.memo}
              </pre>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
