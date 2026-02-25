"use client";

import { useMemo, useState } from "react";
import { Button, Card, Input } from "@/src/components/ui";

type CommissionInput = {
  commission_id: string;
  contract_id: string;
  contract_name: string;
  customer: string;
  commission_amount: number;
  start_date: string;        // YYYY-MM-DD
  amort_months: number;      // e.g. 36
  expected_renewal_months: number; // optional extension for practical expedient modeling
};

type ScheduleRow = {
  period: number;
  month: string; // YYYY-MM
  opening_asset: number;
  amortization_expense: number;
  ending_asset: number;
};

function addMonths(dateStr: string, monthsToAdd: number) {
  const d = new Date(dateStr + "T00:00:00");
  const y = d.getFullYear();
  const m = d.getMonth();
  const day = d.getDate();

  const next = new Date(y, m + monthsToAdd, day);
  return next;
}

function ym(date: Date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  return `${y}-${m}`;
}

function buildCommissionSchedule(inp: CommissionInput): ScheduleRow[] {
  const totalMonths = Math.max(1, Number(inp.amort_months || 0)) + Math.max(0, Number(inp.expected_renewal_months || 0));
  const amount = Number(inp.commission_amount || 0);

  const monthly = totalMonths > 0 ? amount / totalMonths : 0;
  let carrying = amount;

  const rows: ScheduleRow[] = [];

  for (let i = 0; i < totalMonths; i++) {
    const dt = addMonths(inp.start_date, i);
    const opening = carrying;

    // final row cleanup to avoid rounding drift
    const amort =
      i === totalMonths - 1
        ? carrying
        : Number(monthly.toFixed(2));

    carrying = Number((carrying - amort).toFixed(2));

    rows.push({
      period: i + 1,
      month: ym(dt),
      opening_asset: Number(opening.toFixed(2)),
      amortization_expense: Number(amort.toFixed(2)),
      ending_asset: Number(carrying.toFixed(2)),
    });
  }

  return rows;
}

function toCSV(rows: ScheduleRow[], headerMeta: CommissionInput) {
  const lines: string[] = [];

  lines.push(`commission_id,${headerMeta.commission_id}`);
  lines.push(`contract_id,${headerMeta.contract_id}`);
  lines.push(`contract_name,"${headerMeta.contract_name.replace(/"/g, '""')}"`);
  lines.push(`customer,"${headerMeta.customer.replace(/"/g, '""')}"`);
  lines.push(`commission_amount,${headerMeta.commission_amount}`);
  lines.push(`start_date,${headerMeta.start_date}`);
  lines.push(`amort_months,${headerMeta.amort_months}`);
  lines.push(`expected_renewal_months,${headerMeta.expected_renewal_months}`);
  lines.push("");

  lines.push("period,month,opening_asset,amortization_expense,ending_asset");

  for (const r of rows) {
    lines.push(
      [
        r.period,
        r.month,
        r.opening_asset.toFixed(2),
        r.amortization_expense.toFixed(2),
        r.ending_asset.toFixed(2),
      ].join(",")
    );
  }

  return lines.join("\n");
}

export default function CommissionsPage() {
  const [form, setForm] = useState<CommissionInput>({
    commission_id: "COMM-1001",
    contract_id: "C-1001",
    contract_name: "Acme SaaS Annual",
    customer: "Acme",
    commission_amount: 12000,
    start_date: "2025-01-01",
    amort_months: 36,
    expected_renewal_months: 0,
  });

  const schedule = useMemo(() => buildCommissionSchedule(form), [form]);

  const totals = useMemo(() => {
    const totalAmort = schedule.reduce((s, r) => s + r.amortization_expense, 0);
    const ending = schedule.length ? schedule[schedule.length - 1].ending_asset : 0;
    return {
      totalAmort: Number(totalAmort.toFixed(2)),
      ending: Number(ending.toFixed(2)),
    };
  }, [schedule]);

  function setField<K extends keyof CommissionInput>(key: K, value: CommissionInput[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function exportCSV() {
    const csv = toCSV(schedule, form);
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${form.contract_id || "commission"}_asc34040_schedule.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="max-w-7xl mx-auto space-y-4">
      <h1 className="text-xl font-semibold">Deferred Commissions (ASC 340-40)</h1>

      <Card className="p-4 space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
          <Input
            value={form.commission_id}
            onChange={(e: any) => setField("commission_id", e.target.value)}
            placeholder="Commission ID"
          />
          <Input
            value={form.contract_id}
            onChange={(e: any) => setField("contract_id", e.target.value)}
            placeholder="Contract ID"
          />
          <Input
            value={form.contract_name}
            onChange={(e: any) => setField("contract_name", e.target.value)}
            placeholder="Contract Name"
          />
          <Input
            value={form.customer}
            onChange={(e: any) => setField("customer", e.target.value)}
            placeholder="Customer"
          />

          <Input
            type="number"
            value={String(form.commission_amount)}
            onChange={(e: any) => setField("commission_amount", Number(e.target.value))}
            placeholder="Commission Amount"
          />
          <Input
            type="date"
            value={form.start_date}
            onChange={(e: any) => setField("start_date", e.target.value)}
            placeholder="Start Date"
          />
          <Input
            type="number"
            value={String(form.amort_months)}
            onChange={(e: any) => setField("amort_months", Number(e.target.value))}
            placeholder="Amort Months"
          />
          <Input
            type="number"
            value={String(form.expected_renewal_months)}
            onChange={(e: any) => setField("expected_renewal_months", Number(e.target.value))}
            placeholder="Expected Renewal Months"
          />
        </div>

        <div className="flex gap-2">
          <Button onClick={exportCSV}>Export CSV</Button>
        </div>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <Card className="p-4">
          <div className="text-xs text-gray-500">Commission Asset (Initial)</div>
          <div className="text-lg font-semibold">${Number(form.commission_amount || 0).toFixed(2)}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-gray-500">Schedule Months</div>
          <div className="text-lg font-semibold">{schedule.length}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-gray-500">Total Amortization</div>
          <div className="text-lg font-semibold">${totals.totalAmort.toFixed(2)}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-gray-500">Ending Asset</div>
          <div className="text-lg font-semibold">${totals.ending.toFixed(2)}</div>
        </Card>
      </div>

      <Card className="p-0 overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="p-2 text-left">Period</th>
              <th className="p-2 text-left">Month</th>
              <th className="p-2 text-left">Opening Asset</th>
              <th className="p-2 text-left">Amortization Expense</th>
              <th className="p-2 text-left">Ending Asset</th>
            </tr>
          </thead>
          <tbody>
            {schedule.map((r) => (
              <tr key={r.period} className="border-t">
                <td className="p-2">{r.period}</td>
                <td className="p-2">{r.month}</td>
                <td className="p-2">${r.opening_asset.toFixed(2)}</td>
                <td className="p-2">${r.amortization_expense.toFixed(2)}</td>
                <td className="p-2">${r.ending_asset.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
