"use client";

import { useEffect, useState } from "react";
import { api } from "@/src/lib/api";
import { Button, Card } from "@/src/components/ui";

export default function AuditLogPage() {
  const [rows, setRows] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setError(null);
    try {
      const res = await api("/audit-log/events");
      setRows(res.rows || []);
    } catch (e: any) {
      setError(e?.message || "Failed to load audit log");
    }
  }

  useEffect(() => { load(); }, []);

  return (
    <div className="max-w-7xl mx-auto space-y-4">
      <h1 className="text-xl font-semibold">Audit Log & Internal Controls</h1>

      <Card className="p-4 flex justify-between items-center">
        <div className="text-sm text-gray-600">Read-only trail of contract and schedule changes (SOX-friendly).</div>
        <Button onClick={load}>Refresh</Button>
      </Card>

      {error && <div className="text-red-600 text-sm">{error}</div>}

      <Card className="p-0 overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              {["timestamp","user","module","entity_id","action","field","old_value","new_value"].map((h)=>(
                <th key={h} className="p-2 text-left">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i)=>(
              <tr key={i} className="border-t">
                <td className="p-2">{r.timestamp}</td>
                <td className="p-2">{r.user}</td>
                <td className="p-2">{r.module}</td>
                <td className="p-2">{r.entity_id}</td>
                <td className="p-2">{r.action}</td>
                <td className="p-2">{r.field}</td>
                <td className="p-2">{r.old_value}</td>
                <td className="p-2">{r.new_value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
