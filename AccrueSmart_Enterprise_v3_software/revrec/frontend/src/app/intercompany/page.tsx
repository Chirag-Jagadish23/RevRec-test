"use client";

import { useState } from "react";
import { api } from "@/src/lib/api";
import { Button, Card } from "@/src/components/ui";

export default function IntercompanyPage() {
  const [result, setResult] = useState<any>(null);

  const demoBalances = {
    balances: [
      { from_entity: "ParentCo", to_entity: "SubA", account: "Intercompany AR", amount: 25000 },
      { from_entity: "SubA", to_entity: "ParentCo", account: "Intercompany AP", amount: -25000 },
    ],
  };

  async function run() {
    const res = await api("/intercompany/eliminate", {
      method: "POST",
      body: JSON.stringify(demoBalances),
    });
    setResult(res);
  }

  return (
    <div className="max-w-6xl mx-auto space-y-4">
      <h1 className="text-xl font-semibold">Intercompany Eliminations</h1>

      <Card className="p-4 space-y-2">
        <p className="text-sm text-gray-600">Runs a demo elimination set and shows elimination entries.</p>
        <Button onClick={run}>Run Eliminations</Button>
      </Card>

      {result && (
        <>
          <Card className="p-4 text-sm">
            <div>Pairs processed: {result.pairs_processed}</div>
            <div>Gross intercompany balance: ${result.gross_intercompany_balance}</div>
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
