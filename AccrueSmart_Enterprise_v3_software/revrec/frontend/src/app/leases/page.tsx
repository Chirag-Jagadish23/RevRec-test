"use client";

import { useState } from "react";
import { api } from "@/src/lib/api";
import { Input } from "@/src/components/ui/input";
import { Button } from "@/src/components/ui/button";
import { Card } from "@/src/components/ui/card";

type LeaseState = {
  lease_id: string;
  start_date: string;
  end_date: string;
  payment: number;
  frequency: "monthly" | "quarterly" | "annual";
  discount_rate_annual: number;
  initial_direct_costs: number;
  incentives: number;
  cpi_escalation_pct: number;
  cpi_escalation_month: number;
};

export default function LeasePage() {
  const [lease, setLease] = useState<LeaseState>({
    lease_id: "L-1001",
    start_date: "2025-01-01",
    end_date: "2027-12-31",
    payment: 5000,
    frequency: "monthly",
    discount_rate_annual: 0.06,
    initial_direct_costs: 0,
    incentives: 0,
    cpi_escalation_pct: 0.03,
    cpi_escalation_month: 12,
  });

  const [schedule, setSchedule] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  function setField<K extends keyof LeaseState>(key: K, value: LeaseState[K]) {
    setLease((prev) => ({ ...prev, [key]: value }));
  }

  async function run() {
    setError(null);
    try {
      const res = await api("/leases/schedule", {
        method: "POST",
        body: JSON.stringify(lease),
      });
      setSchedule(res);
    } catch (e: any) {
      setError(e?.message || "Failed to generate schedule.");
    }
  }

  async function downloadCSV() {
    setDownloading(true);
    setError(null);
    try {
      const res = await api("/leases/export/journals", {
        method: "POST",
        body: JSON.stringify(lease),
      });

      const blob = new Blob([res.content], { type: "text/csv" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = res.filename || "lease_journals.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      setError(e?.message || "Failed to download CSV.");
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      <h1 className="text-2xl font-bold">Lease Accounting (ASC 842)</h1>

      <Card className="p-4 space-y-4">
        <h2 className="font-medium text-sm text-gray-700">Lease Inputs</h2>

        {/* Row 1 */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="space-y-1">
            <label className="text-xs text-gray-600">Lease ID</label>
            <Input
              value={lease.lease_id}
              onChange={(e) => setField("lease_id", e.target.value)}
              placeholder="L-1001"
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs text-gray-600">Start Date</label>
            <Input
              type="date"
              value={lease.start_date}
              onChange={(e) => setField("start_date", e.target.value)}
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs text-gray-600">End Date</label>
            <Input
              type="date"
              value={lease.end_date}
              onChange={(e) => setField("end_date", e.target.value)}
            />
          </div>
        </div>

        {/* Row 2 */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="space-y-1">
            <label className="text-xs text-gray-600">Payment (per period)</label>
            <Input
              type="number"
              value={lease.payment}
              onChange={(e) => setField("payment", Number(e.target.value || 0))}
              placeholder="5000"
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs text-gray-600">Frequency</label>
            <select
              className="border rounded px-2 py-2 text-sm w-full"
              value={lease.frequency}
              onChange={(e) => setField("frequency", e.target.value as LeaseState["frequency"])}
            >
              <option value="monthly">Monthly</option>
              <option value="quarterly">Quarterly</option>
              <option value="annual">Annual</option>
            </select>
          </div>

          <div className="space-y-1">
            <label className="text-xs text-gray-600">Discount Rate (annual)</label>
            <Input
              type="number"
              step="0.001"
              value={lease.discount_rate_annual}
              onChange={(e) =>
                setField("discount_rate_annual", Number(e.target.value || 0))
              }
              placeholder="0.06"
            />
            <div className="text-[11px] text-gray-500">
              Example: 0.06 = 6%
            </div>
          </div>
        </div>

        {/* Row 3 */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div className="space-y-1">
            <label className="text-xs text-gray-600">Initial Direct Costs</label>
            <Input
              type="number"
              value={lease.initial_direct_costs}
              onChange={(e) =>
                setField("initial_direct_costs", Number(e.target.value || 0))
              }
              placeholder="0"
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs text-gray-600">Incentives</label>
            <Input
              type="number"
              value={lease.incentives}
              onChange={(e) => setField("incentives", Number(e.target.value || 0))}
              placeholder="0"
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs text-gray-600">CPI Escalation %</label>
            <Input
              type="number"
              step="0.001"
              value={lease.cpi_escalation_pct}
              onChange={(e) =>
                setField("cpi_escalation_pct", Number(e.target.value || 0))
              }
              placeholder="0.03"
            />
            <div className="text-[11px] text-gray-500">
              Example: 0.03 = 3%
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-xs text-gray-600">Escalation Every (months)</label>
            <Input
              type="number"
              value={lease.cpi_escalation_month}
              onChange={(e) =>
                setField("cpi_escalation_month", Number(e.target.value || 12))
              }
              placeholder="12"
            />
          </div>
        </div>

        <div className="flex gap-2">
          <Button onClick={run}>Generate Schedule</Button>
          <Button variant="secondary" onClick={downloadCSV} disabled={downloading}>
            {downloading ? "Downloading..." : "Download Journals CSV"}
          </Button>
        </div>

        <div className="text-xs text-gray-500">
          Tip: Start with monthly, payment 5000, discount rate 0.06, no CPI escalation.
        </div>
      </Card>

      {error && <div className="text-red-600 text-sm">{error}</div>}

      {schedule && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <Card className="p-3">
            <div className="text-xs text-gray-500">Opening Liability</div>
            <div className="text-lg font-semibold">
              ${Number(schedule.opening_liability || 0).toLocaleString()}
            </div>
          </Card>
          <Card className="p-3">
            <div className="text-xs text-gray-500">Opening ROU Asset</div>
            <div className="text-lg font-semibold">
              ${Number(schedule.opening_rou_asset || 0).toLocaleString()}
            </div>
          </Card>
          <Card className="p-3">
            <div className="text-xs text-gray-500">Total Interest</div>
            <div className="text-lg font-semibold">
              ${Number(schedule.total_interest || 0).toLocaleString()}
            </div>
          </Card>
          <Card className="p-3">
            <div className="text-xs text-gray-500">Total Payments</div>
            <div className="text-lg font-semibold">
              ${Number(schedule.total_payments || 0).toLocaleString()}
            </div>
          </Card>
        </div>
      )}

      {schedule?.rows?.length > 0 && (
        <Card className="p-0 overflow-x-auto">
          <div className="p-4 border-b">
            <h2 className="font-medium">Lease Amortization Schedule</h2>
          </div>
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="p-2 text-left">Period</th>
                <th className="p-2 text-left">Date</th>
                <th className="p-2 text-right">Payment</th>
                <th className="p-2 text-right">Interest</th>
                <th className="p-2 text-right">Principal</th>
                <th className="p-2 text-right">Ending Liability</th>
                <th className="p-2 text-right">ROU Amort.</th>
                <th className="p-2 text-right">ROU Carrying</th>
              </tr>
            </thead>
            <tbody>
              {schedule.rows.map((r: any, idx: number) => (
                <tr key={idx} className="border-t">
                  <td className="p-2">{r.period}</td>
                  <td className="p-2">{r.date}</td>
                  <td className="p-2 text-right">{Number(r.payment).toFixed(2)}</td>
                  <td className="p-2 text-right">{Number(r.interest).toFixed(2)}</td>
                  <td className="p-2 text-right">{Number(r.principal).toFixed(2)}</td>
                  <td className="p-2 text-right">{Number(r.ending_liability).toFixed(2)}</td>
                  <td className="p-2 text-right">{Number(r.rou_amortization).toFixed(2)}</td>
                  <td className="p-2 text-right">{Number(r.rou_carrying_amount).toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
