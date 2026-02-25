"use client";

import { useState } from "react";
import Link from "next/link";
import { api } from "@/src/lib/api";
import { Button, Card, Input } from "@/src/components/ui";

type ExtractResult = {
  source: string;
  source_name?: string;
  summary?: {
    customer_name?: string;
    quote_name?: string;
    contract_term_months?: number;
    billing_frequency?: string;
    payment_terms?: string;
    estimated_gross_total?: number;
    line_count_detected?: number;
  };
  risk_flags?: { code: string; severity: "low" | "medium" | "high"; message: string }[];
  deal_desk_autofill?: any;
  raw_extraction?: any;
};

export default function ViewerPage() {
  const [text, setText] = useState("");
  const [sourceName, setSourceName] = useState("Pasted Contract");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ExtractResult | null>(null);

  async function analyze() {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await api("/viewer/extract", {
        method: "POST",
        body: JSON.stringify({
          text,
          source_name: sourceName || "Pasted Contract",
        }),
      });
      setResult(res);
    } catch (e: any) {
      console.error(e);
      setError(e?.message || "Failed to analyze contract text.");
    } finally {
      setLoading(false);
    }
  }

  function sendToDealDesk() {
    if (!result?.deal_desk_autofill) return;
    try {
      localStorage.setItem("dealDeskDraft", JSON.stringify(result.deal_desk_autofill));
      alert("Sent to Deal Desk draft. Open Deal Desk AI page.");
    } catch (e) {
      console.error(e);
      alert("Could not save deal desk draft.");
    }
  }

  const risks = result?.risk_flags || [];
  const summary = result?.summary || {};

  return (
    <div className="max-w-7xl mx-auto space-y-4">
      <h1 className="text-xl font-semibold">Viewer AI</h1>

      <Card className="p-4 space-y-3">
        <div className="font-medium">Contract Intake</div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="md:col-span-1">
            <div className="text-xs text-gray-500 mb-1">Source Name</div>
            <Input
              value={sourceName}
              onChange={(e: any) => setSourceName(e.target.value)}
              placeholder="MSA / Order Form / Quote"
            />
          </div>
          <div className="md:col-span-2 flex items-end gap-2">
            <Button onClick={analyze} disabled={loading || !text.trim()}>
              {loading ? "Analyzing..." : "Analyze Contract Text"}
            </Button>

            <Button variant="outline" onClick={sendToDealDesk} disabled={!result?.deal_desk_autofill}>
              Send to Deal Desk
            </Button>

            <Link href="/negotiation" className="inline-flex items-center rounded border px-3 py-2 text-sm hover:bg-gray-50">
              Open Deal Desk AI
            </Link>
          </div>
        </div>

        <div>
          <div className="text-xs text-gray-500 mb-1">Paste Contract / Quote / Order Form Text</div>
          <textarea
            className="w-full min-h-[220px] border rounded p-3 text-sm"
            placeholder="Paste customer order form, MSA, quote text, redlines, or legal clauses here..."
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </div>

        <div className="text-xs text-gray-500">
          Best use: paste order forms + nonstandard legal terms. Viewer AI extracts billing, payment terms, term length, and risk flags for Deal Desk.
        </div>
      </Card>

      {error && <div className="text-red-600 text-sm">{error}</div>}

      {result && (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-1 md:grid-cols-6 gap-3">
            <Card className="p-4">
              <div className="text-xs text-gray-500">Extractor</div>
              <div className="text-sm font-semibold uppercase">{result.source || "unknown"}</div>
            </Card>
            <Card className="p-4">
              <div className="text-xs text-gray-500">Customer</div>
              <div className="text-sm font-semibold">{summary.customer_name || "-"}</div>
            </Card>
            <Card className="p-4">
              <div className="text-xs text-gray-500">Quote</div>
              <div className="text-sm font-semibold">{summary.quote_name || "-"}</div>
            </Card>
            <Card className="p-4">
              <div className="text-xs text-gray-500">Term</div>
              <div className="text-sm font-semibold">{summary.contract_term_months || 0} mo</div>
            </Card>
            <Card className="p-4">
              <div className="text-xs text-gray-500">Billing</div>
              <div className="text-sm font-semibold">{summary.billing_frequency || "-"}</div>
            </Card>
            <Card className="p-4">
              <div className="text-xs text-gray-500">Payment</div>
              <div className="text-sm font-semibold">{summary.payment_terms || "-"}</div>
            </Card>
          </div>

          {/* Risk flags */}
          <Card className="p-4">
            <div className="flex items-center justify-between mb-2">
              <div className="font-medium">Risk Flags</div>
              <div className="text-xs text-gray-500">{risks.length} detected</div>
            </div>

            {risks.length === 0 ? (
              <div className="text-sm text-gray-500">No obvious risks detected from pasted text.</div>
            ) : (
              <div className="space-y-2">
                {risks.map((r, idx) => {
                  const cls =
                    r.severity === "high"
                      ? "bg-red-100 text-red-700"
                      : r.severity === "medium"
                      ? "bg-yellow-100 text-yellow-700"
                      : "bg-blue-100 text-blue-700";
                  return (
                    <div key={`${r.code}-${idx}`} className="border rounded p-2 flex items-start justify-between gap-3">
                      <div className="text-sm">
                        <div className="font-medium">{r.code}</div>
                        <div className="text-gray-700">{r.message}</div>
                      </div>
                      <span className={`rounded px-2 py-0.5 text-xs ${cls}`}>{r.severity}</span>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>

          {/* Deal desk autofill preview */}
          <Card className="p-4">
            <div className="flex items-center justify-between mb-2">
              <div className="font-medium">Deal Desk Autofill Payload</div>
              <Button variant="outline" onClick={sendToDealDesk} disabled={!result.deal_desk_autofill}>
                Send to Deal Desk
              </Button>
            </div>
            <pre className="text-xs bg-slate-50 border rounded p-3 overflow-x-auto max-h-80">
              {JSON.stringify(result.deal_desk_autofill || {}, null, 2)}
            </pre>
          </Card>

          {/* Raw extraction */}
          <Card className="p-4">
            <div className="font-medium mb-2">Extraction Details</div>
            <pre className="text-xs bg-slate-50 border rounded p-3 overflow-x-auto max-h-72">
              {JSON.stringify(result.raw_extraction || {}, null, 2)}
            </pre>
          </Card>
        </>
      )}
    </div>
  );
}
