"use client";

import { useState } from "react";
import { api } from "@/src/lib/api";
import { Button, Card, Input } from "@/src/components/ui";

export default function EquityPage() {
  const [form, setForm] = useState({
    grant_id: "G-1001",
    employee_name: "Demo Employee",
    grant_date: "2026-01-01",
    total_fair_value: 48000,
    vest_months: 48,
    cliff_months: 12,
    method: "straight_line",
  });

  const [result, setResult] = useState<any>(null);

  async function run() {
    const res = await api("/equity/asc718/schedule", {
      method: "POST",
      body: JSON.stringify(form),
    });
    setResult(res);
  }

  const setField = (k:string, v:any) => setForm((p)=>({ ...p, [k]: v }));

  return (
    <div className="max-w-6xl mx-auto space-y-4">
      <h1 className="text-xl font-semibold">Equity & Cap Table (ASC 718)</h1>

      <Card className="p-4 grid grid-cols-1 md:grid-cols-4 gap-2">
        <Input value={form.grant_id} onChange={(e:any)=>setField("grant_id", e.target.value)} placeholder="Grant ID" />
        <Input value={form.employee_name} onChange={(e:any)=>setField("employee_name", e.target.value)} placeholder="Employee" />
        <Input type="date" value={form.grant_date} onChange={(e:any)=>setField("grant_date", e.target.value)} />
        <Input type="number" value={String(form.total_fair_value)} onChange={(e:any)=>setField("total_fair_value", Number(e.target.value))} placeholder="Fair Value" />
        <Input type="number" value={String(form.vest_months)} onChange={(e:any)=>setField("vest_months", Number(e.target.value))} placeholder="Vest Months" />
        <Input type="number" value={String(form.cliff_months)} onChange={(e:any)=>setField("cliff_months", Number(e.target.value))} placeholder="Cliff Months" />
        <Button onClick={run}>Generate ASC 718 Schedule</Button>
      </Card>

      {result && (
        <>
          <Card className="p-4">
            <div className="text-sm">Total recognized: <span className="font-semibold">${result.total_recognized}</span></div>
          </Card>

          <Card className="p-0 overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50">
                <tr>{Object.keys(result.rows[0] || {}).map((h:string)=><th key={h} className="p-2 text-left">{h}</th>)}</tr>
              </thead>
              <tbody>
                {result.rows.map((r:any, i:number)=>(
                  <tr key={i} className="border-t">
                    {Object.values(r).map((v:any, j:number)=><td key={j} className="p-2">{typeof v === "number" ? v.toFixed(2) : String(v)}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </>
      )}
    </div>
  );
}
