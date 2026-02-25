"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/src/lib/api";
import { Button, Card, Input } from "@/src/components/ui";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";

type DealLine = {
  sku: string;
  description: string;
  quantity: number;
  unit_price: number;
  discount_pct: number;
  term_months: number;
  type: "subscription" | "services" | "usage" | "support";
};

type ReviewResult = {
  status: string;
  overall_health_score: number;
  risk_scores: Record<string, number>;
  health_scores: Record<string, number>;
  exceptions: { code: string; severity: string; message: string }[];
  observations: string[];
  recommendations: string[];
  approval_path: string[];
  totals: {
    gross_total: number;
    net_total: number;
    discount_value: number;
    blended_discount_pct: number;
  };
  lines: DealLine[];
  memo: string;
};

type ScenarioResult = {
  status: string;
  baseline: any;
  scenario: any;
  delta: Record<string, any>;
  ebitda: Record<string, any>;
  explanation?: string[];
};

type ParsedPolicyRule = {
  rule_id: string;
  name: string;
  scope: string;
  condition: Record<string, any>;
  action: Record<string, any>;
  source_text?: string;
  parse_status?: string;
};

type PolicyEvalResult = {
  status: string;
  context: Record<string, any>;
  triggered_rules: {
    rule_id: string;
    name: string;
    action: Record<string, any>;
    source_text?: string;
  }[];
  required_approvals: string[];
};

export default function DealDeskPage() {
  const [form, setForm] = useState({
    customer_name: "Acme Corp",
    quote_name: "Q-2026-001",
    contract_term_months: 36,
    billing_frequency: "monthly",
    payment_terms: "Net 60",
    currency: "USD",
    nonstandard_terms:
      "Customer requests termination for convenience after 6 months and milestone acceptance for implementation.",
    notes: "",
    approval_policy: {
      max_standard_discount_pct: 20,
      max_auto_approve_term_months: 12,
      require_legal_for_nonstandard_terms: true,
      require_finance_for_services_discount: true,
    },
  });

  const [lines, setLines] = useState<DealLine[]>([
    {
      sku: "SUB-PLATFORM",
      description: "Platform subscription",
      quantity: 1,
      unit_price: 120000,
      discount_pct: 25,
      term_months: 36,
      type: "subscription",
    },
    {
      sku: "SERV-IMP",
      description: "Implementation services",
      quantity: 1,
      unit_price: 30000,
      discount_pct: 15,
      term_months: 3,
      type: "services",
    },
    {
      sku: "USG-API",
      description: "API usage overage",
      quantity: 1,
      unit_price: 10000,
      discount_pct: 0,
      term_months: 36,
      type: "usage",
    },
  ]);

  const [scenarioInputs, setScenarioInputs] = useState({
    target_discount_pct: 15,
    target_term_months: 24,
    target_billing_frequency: "quarterly",
    lease_discount_rate_annual: 0.08,
    fixed_asset_useful_life_months: 48,
    fixed_asset_cost: 24000,
    fixed_asset_salvage_value: 2000,
  });

  const [policyText, setPolicyText] = useState(
    [
      "Any services discount >10% requires finance approval",
      "Net terms >45 need CFO approval",
      "Termination for convenience triggers legal review",
      "Contracts >24 months need revrec review",
    ].join("\n")
  );

  const [parsedRules, setParsedRules] = useState<ParsedPolicyRule[]>([]);

  const [loading, setLoading] = useState(false);
  const [scenarioLoading, setScenarioLoading] = useState(false);
  const [policyLoading, setPolicyLoading] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ReviewResult | null>(null);
  const [scenarioResult, setScenarioResult] = useState<ScenarioResult | null>(null);
  const [policyEvalResult, setPolicyEvalResult] = useState<PolicyEvalResult | null>(null);

  useEffect(() => {
    try {
      const raw = localStorage.getItem("dealDeskDraft");
      if (!raw) return;
      const parsed = JSON.parse(raw);

      setForm((prev) => ({
        ...prev,
        customer_name: parsed.customer_name || prev.customer_name,
        quote_name: parsed.quote_name || prev.quote_name,
        contract_term_months:
          Number(parsed.contract_term_months) || prev.contract_term_months,
        billing_frequency: parsed.billing_frequency || prev.billing_frequency,
        payment_terms: parsed.payment_terms || prev.payment_terms,
        currency: parsed.currency || prev.currency,
        nonstandard_terms: parsed.nonstandard_terms || prev.nonstandard_terms,
        notes: parsed.notes || prev.notes,
        approval_policy: {
          ...prev.approval_policy,
          ...(parsed.approval_policy || {}),
        },
      }));

      if (Array.isArray(parsed.lines) && parsed.lines.length > 0) {
        const normalized: DealLine[] = parsed.lines.map((l: any, idx: number) => ({
          sku: String(l.sku || `LINE-${idx + 1}`),
          description: String(l.description || ""),
          quantity: Number(l.quantity ?? 1),
          unit_price: Number(l.unit_price ?? 0),
          discount_pct: Number(l.discount_pct ?? 0),
          term_months: Number(l.term_months ?? parsed.contract_term_months ?? 12),
          type: (["subscription", "services", "usage", "support"].includes(l.type)
            ? l.type
            : "subscription") as DealLine["type"],
        }));
        setLines(normalized);
      }
    } catch (e) {
      console.error("Failed to load dealDeskDraft", e);
    }
  }, []);

  function patch<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function patchPolicy<K extends keyof typeof form.approval_policy>(
    key: K,
    value: (typeof form.approval_policy)[K]
  ) {
    setForm((prev) => ({
      ...prev,
      approval_policy: { ...prev.approval_policy, [key]: value },
    }));
  }

  function patchScenario<K extends keyof typeof scenarioInputs>(
    key: K,
    value: (typeof scenarioInputs)[K]
  ) {
    setScenarioInputs((prev) => ({ ...prev, [key]: value }));
  }

  function updateLine<K extends keyof DealLine>(idx: number, key: K, value: DealLine[K]) {
    setLines((prev) => prev.map((l, i) => (i === idx ? { ...l, [key]: value } : l)));
  }

  function addLine() {
    setLines((prev) => [
      ...prev,
      {
        sku: `LINE-${prev.length + 1}`,
        description: "",
        quantity: 1,
        unit_price: 0,
        discount_pct: 0,
        term_months: form.contract_term_months,
        type: "subscription",
      },
    ]);
  }

  function removeLine(idx: number) {
    setLines((prev) => prev.filter((_, i) => i !== idx));
  }

  function buildDealPayload() {
    return {
      ...form,
      contract_term_months: Number(form.contract_term_months),
      lines: lines.map((l) => ({
        ...l,
        quantity: Number(l.quantity),
        unit_price: Number(l.unit_price),
        discount_pct: Number(l.discount_pct),
        term_months: Number(l.term_months),
      })),
      approval_policy: {
        ...form.approval_policy,
        max_standard_discount_pct: Number(form.approval_policy.max_standard_discount_pct),
        max_auto_approve_term_months: Number(form.approval_policy.max_auto_approve_term_months),
      },
    };
  }

  async function runReview() {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await api("/deal-desk/review", {
        method: "POST",
        body: JSON.stringify(buildDealPayload()),
      });
      setResult(res);
    } catch (e: any) {
      console.error(e);
      setError(e?.message || "Deal Desk review failed.");
    } finally {
      setLoading(false);
    }
  }

  async function runScenarioMode() {
    setScenarioLoading(true);
    setError(null);
    setScenarioResult(null);

    try {
      const basePayload = {
        ...buildDealPayload(),
        lease_discount_rate_annual: Number(scenarioInputs.lease_discount_rate_annual),
        fixed_asset_useful_life_months: Number(scenarioInputs.fixed_asset_useful_life_months),
        fixed_asset_cost: Number(scenarioInputs.fixed_asset_cost),
        fixed_asset_salvage_value: Number(scenarioInputs.fixed_asset_salvage_value),
      };

      const lineChanges = lines
        .filter((l) => l.type === "subscription")
        .map((l) => ({
          sku: l.sku,
          discount_pct: Number(scenarioInputs.target_discount_pct),
          term_months: Number(scenarioInputs.target_term_months),
        }));

      const res = await api("/intelligence/scenario-mode", {
        method: "POST",
        body: JSON.stringify({
          base_payload: basePayload,
          changes: {
            contract_term_months: Number(scenarioInputs.target_term_months),
            billing_frequency: scenarioInputs.target_billing_frequency,
            lease_discount_rate_annual: Number(scenarioInputs.lease_discount_rate_annual),
            fixed_asset_useful_life_months: Number(scenarioInputs.fixed_asset_useful_life_months),
            fixed_asset_cost: Number(scenarioInputs.fixed_asset_cost),
            fixed_asset_salvage_value: Number(scenarioInputs.fixed_asset_salvage_value),
            line_changes: lineChanges,
          },
        }),
      });

      setScenarioResult(res);
    } catch (e: any) {
      console.error(e);
      setError(e?.message || "Scenario mode failed.");
    } finally {
      setScenarioLoading(false);
    }
  }

  async function evaluatePolicies() {
    setPolicyLoading(true);
    setError(null);
    setPolicyEvalResult(null);

    try {
      const policyLines = policyText
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean);

      const parsed = await api("/intelligence/policy/parse", {
        method: "POST",
        body: JSON.stringify({ policy_lines: policyLines }),
      });

      const rules = (parsed?.rules || []) as ParsedPolicyRule[];
      setParsedRules(rules);

      const evalRes = await api("/intelligence/policy/evaluate", {
        method: "POST",
        body: JSON.stringify({
          rules,
          deal_payload: buildDealPayload(),
        }),
      });

      setPolicyEvalResult(evalRes);
    } catch (e: any) {
      console.error(e);
      setError(e?.message || "Policy evaluation failed.");
    } finally {
      setPolicyLoading(false);
    }
  }

  function applyScenarioToDeal() {
    setForm((prev) => ({
      ...prev,
      contract_term_months: Number(scenarioInputs.target_term_months) || prev.contract_term_months,
      billing_frequency: scenarioInputs.target_billing_frequency || prev.billing_frequency,
    }));

    setLines((prev) =>
      prev.map((l) =>
        l.type === "subscription"
          ? {
              ...l,
              discount_pct: Number(scenarioInputs.target_discount_pct),
              term_months: Number(scenarioInputs.target_term_months),
            }
          : l
      )
    );

    // optional: clear stale outputs so user re-runs review with applied scenario
    // setResult(null);
  }

  const riskChart = useMemo(() => {
    if (!result?.risk_scores) return [];
    return Object.entries(result.risk_scores).map(([k, v]) => ({ category: k, risk: v }));
  }, [result]);

  const previewTotals = useMemo(() => {
    let gross = 0;
    let net = 0;
    let disc = 0;

    for (const l of lines) {
      const lineGross = Number(l.quantity || 0) * Number(l.unit_price || 0);
      const lineDisc = lineGross * (Number(l.discount_pct || 0) / 100);
      gross += lineGross;
      disc += lineDisc;
      net += lineGross - lineDisc;
    }

    return {
      gross,
      net,
      disc,
      blendedPct: gross > 0 ? (disc / gross) * 100 : 0,
    };
  }, [lines]);

  const scenarioCompareCards = useMemo(() => {
    if (!scenarioResult?.baseline || !scenarioResult?.scenario) return [];

    const b = scenarioResult.baseline || {};
    const s = scenarioResult.scenario || {};

    const bt = b.totals || {};
    const st = s.totals || {};

    const baseLease = Number(b.lease_monthly_cost ?? b.lease?.monthly_cost ?? 0);
    const scenLease = Number(s.lease_monthly_cost ?? s.lease?.monthly_cost ?? 0);

    const baseDep = Number(b.depreciation_monthly ?? b.fixed_asset?.depreciation_monthly ?? 0);
    const scenDep = Number(s.depreciation_monthly ?? s.fixed_asset?.depreciation_monthly ?? 0);

    const baseComm = Number(
      b.commission_asset ?? b.commission_asset_balance ?? b.commissions?.asset_balance ?? 0
    );
    const scenComm = Number(
      s.commission_asset ?? s.commission_asset_balance ?? s.commissions?.asset_balance ?? 0
    );

    const baseDefRev = Number(
      b.opening_deferred_revenue ?? b.deferred_revenue ?? b.deferred?.opening_balance ?? 0
    );
    const scenDefRev = Number(
      s.opening_deferred_revenue ?? s.deferred_revenue ?? s.deferred?.opening_balance ?? 0
    );

    const baseFY1Cash = Number(b.first_year_cash ?? b.cash_flow?.first_year ?? 0);
    const scenFY1Cash = Number(s.first_year_cash ?? s.cash_flow?.first_year ?? 0);

    const baseBlend = Number(bt.blended_discount_pct ?? b.blended_discount_pct ?? 0);
    const scenBlend = Number(st.blended_discount_pct ?? s.blended_discount_pct ?? 0);

    const cards = [
      {
        label: "Net Total",
        baseline: Number(bt.net_total ?? b.net_total ?? 0),
        scenario: Number(st.net_total ?? s.net_total ?? 0),
        delta: Number(scenarioResult.delta?.net_total_delta ?? 0),
      },
      {
        label: "Deferred Revenue",
        baseline: baseDefRev,
        scenario: scenDefRev,
        delta: Number(scenarioResult.delta?.opening_deferred_revenue_delta ?? scenDefRev - baseDefRev),
      },
      {
        label: "Commission Asset",
        baseline: baseComm,
        scenario: scenComm,
        delta: Number(scenarioResult.delta?.commission_asset_delta ?? scenComm - baseComm),
      },
      {
        label: "Cash (FY1)",
        baseline: baseFY1Cash,
        scenario: scenFY1Cash,
        delta: Number(scenarioResult.delta?.first_year_cash_delta ?? scenFY1Cash - baseFY1Cash),
      },
      {
        label: "Lease Monthly Cost",
        baseline: baseLease,
        scenario: scenLease,
        delta: Number(scenarioResult.delta?.lease_monthly_cost_delta ?? scenLease - baseLease),
      },
      {
        label: "Depreciation Monthly",
        baseline: baseDep,
        scenario: scenDep,
        delta: Number(scenarioResult.delta?.depreciation_monthly_delta ?? scenDep - baseDep),
      },
      {
        label: "Monthly EBITDA (proxy)",
        baseline: Number(scenarioResult.ebitda?.baseline_monthly_ebitda_proxy ?? 0),
        scenario: Number(scenarioResult.ebitda?.scenario_monthly_ebitda_proxy ?? 0),
        delta: Number(scenarioResult.ebitda?.monthly_ebitda_delta_proxy ?? 0),
      },
      {
        label: "Annual EBITDA (proxy)",
        baseline: Number(scenarioResult.ebitda?.baseline_annualized_ebitda_proxy ?? 0),
        scenario: Number(scenarioResult.ebitda?.scenario_annualized_ebitda_proxy ?? 0),
        delta: Number(scenarioResult.ebitda?.annualized_ebitda_delta_proxy ?? 0),
      },
      {
        label: "Blended Discount %",
        baseline: baseBlend,
        scenario: scenBlend,
        delta: scenBlend - baseBlend,
        isPercent: true,
      },
    ];

    return cards;
  }, [scenarioResult]);

  return (
    <div className="max-w-7xl mx-auto space-y-4">
      <h1 className="text-xl font-semibold">Deal Desk AI</h1>

      <Card className="p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="font-medium">Deal Inputs</div>
          <Button
            variant="outline"
            onClick={() => {
              try {
                const raw = localStorage.getItem("dealDeskDraft");
                if (!raw) return;
                const parsed = JSON.parse(raw);

                setForm((prev) => ({
                  ...prev,
                  customer_name: parsed.customer_name || prev.customer_name,
                  quote_name: parsed.quote_name || prev.quote_name,
                  contract_term_months:
                    Number(parsed.contract_term_months) || prev.contract_term_months,
                  billing_frequency: parsed.billing_frequency || prev.billing_frequency,
                  payment_terms: parsed.payment_terms || prev.payment_terms,
                  currency: parsed.currency || prev.currency,
                  nonstandard_terms: parsed.nonstandard_terms || prev.nonstandard_terms,
                  notes: parsed.notes || prev.notes,
                  approval_policy: {
                    ...prev.approval_policy,
                    ...(parsed.approval_policy || {}),
                  },
                }));

                if (Array.isArray(parsed.lines) && parsed.lines.length > 0) {
                  const normalized: DealLine[] = parsed.lines.map((l: any, idx: number) => ({
                    sku: String(l.sku || `LINE-${idx + 1}`),
                    description: String(l.description || ""),
                    quantity: Number(l.quantity ?? 1),
                    unit_price: Number(l.unit_price ?? 0),
                    discount_pct: Number(l.discount_pct ?? 0),
                    term_months: Number(l.term_months ?? parsed.contract_term_months ?? 12),
                    type: (["subscription", "services", "usage", "support"].includes(l.type)
                      ? l.type
                      : "subscription") as DealLine["type"],
                  }));
                  setLines(normalized);
                }
              } catch (e) {
                console.error("Failed to load dealDeskDraft", e);
              }
            }}
          >
            Load Viewer Draft
          </Button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div>
            <div className="text-xs text-gray-500 mb-1">Customer</div>
            <Input
              value={form.customer_name}
              onChange={(e: any) => patch("customer_name", e.target.value)}
            />
          </div>

          <div>
            <div className="text-xs text-gray-500 mb-1">Quote Name</div>
            <Input value={form.quote_name} onChange={(e: any) => patch("quote_name", e.target.value)} />
          </div>

          <div>
            <div className="text-xs text-gray-500 mb-1">Contract Term (months)</div>
            <Input
              type="number"
              value={String(form.contract_term_months)}
              onChange={(e: any) => patch("contract_term_months", Number(e.target.value))}
            />
          </div>

          <div>
            <div className="text-xs text-gray-500 mb-1">Billing Frequency</div>
            <select
              className="w-full border rounded px-2 py-2 text-sm bg-white"
              value={form.billing_frequency}
              onChange={(e) => patch("billing_frequency", e.target.value)}
            >
              <option value="monthly">Monthly</option>
              <option value="quarterly">Quarterly</option>
              <option value="annual">Annual</option>
            </select>
          </div>

          <div>
            <div className="text-xs text-gray-500 mb-1">Payment Terms</div>
            <Input value={form.payment_terms} onChange={(e: any) => patch("payment_terms", e.target.value)} />
          </div>

          <div>
            <div className="text-xs text-gray-500 mb-1">Currency</div>
            <Input value={form.currency} onChange={(e: any) => patch("currency", e.target.value)} />
          </div>
        </div>

        <div>
          <div className="text-xs text-gray-500 mb-1">Non-standard Terms</div>
          <textarea
            className="w-full border rounded px-3 py-2 text-sm min-h-[90px]"
            value={form.nonstandard_terms}
            onChange={(e) => patch("nonstandard_terms", e.target.value)}
            placeholder="Paste non-standard legal/commercial terms here..."
          />
        </div>
      </Card>

      <Card className="p-4 space-y-3">
        <div className="font-medium">Approval Policy (Configurable)</div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div>
            <div className="text-xs text-gray-500 mb-1">Max Standard Discount %</div>
            <Input
              type="number"
              value={String(form.approval_policy.max_standard_discount_pct)}
              onChange={(e: any) =>
                patchPolicy("max_standard_discount_pct", Number(e.target.value))
              }
            />
          </div>

          <div>
            <div className="text-xs text-gray-500 mb-1">Max Auto-Approve Term (months)</div>
            <Input
              type="number"
              value={String(form.approval_policy.max_auto_approve_term_months)}
              onChange={(e: any) =>
                patchPolicy("max_auto_approve_term_months", Number(e.target.value))
              }
            />
          </div>

          <label className="flex items-center gap-2 text-sm mt-6">
            <input
              type="checkbox"
              checked={form.approval_policy.require_legal_for_nonstandard_terms}
              onChange={(e) =>
                patchPolicy("require_legal_for_nonstandard_terms", e.target.checked)
              }
            />
            Legal for non-standard terms
          </label>

          <label className="flex items-center gap-2 text-sm mt-6">
            <input
              type="checkbox"
              checked={form.approval_policy.require_finance_for_services_discount}
              onChange={(e) =>
                patchPolicy("require_finance_for_services_discount", e.target.checked)
              }
            />
            Finance for services discount
          </label>
        </div>
      </Card>

      <Card className="p-4 space-y-3">
        <div className="font-medium">AI Scenario Mode</div>
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-3">
          <div>
            <div className="text-xs text-gray-500 mb-1">Target Discount % (subscription)</div>
            <Input
              type="number"
              value={String(scenarioInputs.target_discount_pct)}
              onChange={(e: any) => patchScenario("target_discount_pct", Number(e.target.value))}
            />
          </div>

          <div>
            <div className="text-xs text-gray-500 mb-1">Target Term (months)</div>
            <Input
              type="number"
              value={String(scenarioInputs.target_term_months)}
              onChange={(e: any) => patchScenario("target_term_months", Number(e.target.value))}
            />
          </div>

          <div>
            <div className="text-xs text-gray-500 mb-1">Target Billing</div>
            <select
              className="w-full border rounded px-2 py-2 text-sm bg-white"
              value={scenarioInputs.target_billing_frequency}
              onChange={(e) => patchScenario("target_billing_frequency", e.target.value)}
            >
              <option value="monthly">Monthly</option>
              <option value="quarterly">Quarterly</option>
              <option value="annual">Annual</option>
            </select>
          </div>

          <div>
            <div className="text-xs text-gray-500 mb-1">Lease Rate (annual)</div>
            <Input
              type="number"
              step="0.01"
              value={String(scenarioInputs.lease_discount_rate_annual)}
              onChange={(e: any) =>
                patchScenario("lease_discount_rate_annual", Number(e.target.value))
              }
            />
          </div>

          <div>
            <div className="text-xs text-gray-500 mb-1">Useful Life (months)</div>
            <Input
              type="number"
              value={String(scenarioInputs.fixed_asset_useful_life_months)}
              onChange={(e: any) =>
                patchScenario("fixed_asset_useful_life_months", Number(e.target.value))
              }
            />
          </div>

          <div>
            <div className="text-xs text-gray-500 mb-1">Fixed Asset Cost</div>
            <Input
              type="number"
              value={String(scenarioInputs.fixed_asset_cost)}
              onChange={(e: any) => patchScenario("fixed_asset_cost", Number(e.target.value))}
            />
          </div>

          <div>
            <div className="text-xs text-gray-500 mb-1">Salvage Value</div>
            <Input
              type="number"
              value={String(scenarioInputs.fixed_asset_salvage_value)}
              onChange={(e: any) =>
                patchScenario("fixed_asset_salvage_value", Number(e.target.value))
              }
            />
          </div>
        </div>
      </Card>

      <Card className="p-4 space-y-3">
        <div className="font-medium">AI Policy Engine (Plain English)</div>
        <div>
          <div className="text-xs text-gray-500 mb-1">
            One policy per line (will parse → rules → evaluate on current deal)
          </div>
          <textarea
            className="w-full border rounded px-3 py-2 text-sm min-h-[120px]"
            value={policyText}
            onChange={(e) => setPolicyText(e.target.value)}
            placeholder="Example: Net terms >45 need CFO approval"
          />
        </div>
      </Card>

      <Card className="p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="font-medium">Deal Lines</div>
          <Button onClick={addLine} variant="outline">Add Line</Button>
        </div>

        <div className="overflow-x-auto border rounded">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="text-left px-2 py-2">SKU</th>
                <th className="text-left px-2 py-2">Description</th>
                <th className="text-left px-2 py-2">Type</th>
                <th className="text-right px-2 py-2">Qty</th>
                <th className="text-right px-2 py-2">Unit Price</th>
                <th className="text-right px-2 py-2">Discount %</th>
                <th className="text-right px-2 py-2">Term (mo)</th>
                <th className="text-right px-2 py-2">Net</th>
                <th className="text-right px-2 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {lines.map((l, idx) => {
                const gross = Number(l.quantity) * Number(l.unit_price);
                const net = gross * (1 - Number(l.discount_pct) / 100);

                return (
                  <tr key={`${l.sku}-${idx}`} className="border-b last:border-b-0">
                    <td className="px-2 py-2">
                      <Input value={l.sku} onChange={(e: any) => updateLine(idx, "sku", e.target.value)} />
                    </td>
                    <td className="px-2 py-2">
                      <Input value={l.description} onChange={(e: any) => updateLine(idx, "description", e.target.value)} />
                    </td>
                    <td className="px-2 py-2">
                      <select
                        className="border rounded px-2 py-2 text-sm bg-white"
                        value={l.type}
                        onChange={(e) => updateLine(idx, "type", e.target.value as DealLine["type"])}
                      >
                        <option value="subscription">subscription</option>
                        <option value="services">services</option>
                        <option value="usage">usage</option>
                        <option value="support">support</option>
                      </select>
                    </td>
                    <td className="px-2 py-2">
                      <Input
                        type="number"
                        value={String(l.quantity)}
                        onChange={(e: any) => updateLine(idx, "quantity", Number(e.target.value))}
                      />
                    </td>
                    <td className="px-2 py-2">
                      <Input
                        type="number"
                        value={String(l.unit_price)}
                        onChange={(e: any) => updateLine(idx, "unit_price", Number(e.target.value))}
                      />
                    </td>
                    <td className="px-2 py-2">
                      <Input
                        type="number"
                        value={String(l.discount_pct)}
                        onChange={(e: any) => updateLine(idx, "discount_pct", Number(e.target.value))}
                      />
                    </td>
                    <td className="px-2 py-2">
                      <Input
                        type="number"
                        value={String(l.term_months)}
                        onChange={(e: any) => updateLine(idx, "term_months", Number(e.target.value))}
                      />
                    </td>
                    <td className="px-2 py-2 text-right">{net.toLocaleString()}</td>
                    <td className="px-2 py-2 text-right">
                      <button
                        className="text-xs text-red-600 hover:underline"
                        onClick={() => removeLine(idx)}
                        disabled={lines.length <= 1}
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <Card className="p-3">
            <div className="text-xs text-gray-500">Gross</div>
            <div className="font-semibold">{previewTotals.gross.toLocaleString()}</div>
          </Card>
          <Card className="p-3">
            <div className="text-xs text-gray-500">Discount Value</div>
            <div className="font-semibold">{previewTotals.disc.toLocaleString()}</div>
          </Card>
          <Card className="p-3">
            <div className="text-xs text-gray-500">Net</div>
            <div className="font-semibold">{previewTotals.net.toLocaleString()}</div>
          </Card>
          <Card className="p-3">
            <div className="text-xs text-gray-500">Blended Discount %</div>
            <div className="font-semibold">{previewTotals.blendedPct.toFixed(2)}%</div>
          </Card>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button onClick={runReview} disabled={loading}>
            {loading ? "Reviewing..." : "Run Deal Desk AI Review"}
          </Button>

          <Button onClick={runScenarioMode} disabled={scenarioLoading} variant="outline">
            {scenarioLoading ? "Running Scenario..." : "Run Scenario Mode"}
          </Button>

          <Button onClick={evaluatePolicies} disabled={policyLoading} variant="outline">
            {policyLoading ? "Evaluating Policies..." : "Evaluate Policies"}
          </Button>
        </div>
      </Card>

      {error && <div className="text-red-600 text-sm">{error}</div>}

      {result && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
            <Card className="p-4">
              <div className="text-xs text-gray-500">Overall Health Score</div>
              <div className="text-2xl font-semibold">{result.overall_health_score}</div>
            </Card>

            <Card className="p-4">
              <div className="text-xs text-gray-500">Gross</div>
              <div className="text-lg font-semibold">{result.totals.gross_total.toLocaleString()}</div>
            </Card>

            <Card className="p-4">
              <div className="text-xs text-gray-500">Net</div>
              <div className="text-lg font-semibold">{result.totals.net_total.toLocaleString()}</div>
            </Card>

            <Card className="p-4">
              <div className="text-xs text-gray-500">Discount</div>
              <div className="text-lg font-semibold">{result.totals.discount_value.toLocaleString()}</div>
            </Card>

            <Card className="p-4">
              <div className="text-xs text-gray-500">Blended Discount %</div>
              <div className="text-lg font-semibold">{result.totals.blended_discount_pct}%</div>
            </Card>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card className="p-4">
              <div className="font-medium mb-2">Risk Scores</div>
              <div style={{ width: "100%", height: 280 }}>
                <ResponsiveContainer>
                  <BarChart data={riskChart}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="category" />
                    <YAxis domain={[0, 100]} />
                    <Tooltip />
                    <Bar dataKey="risk" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>

            <Card className="p-4">
              <div className="font-medium mb-2">Approval Path</div>
              <div className="space-y-2">
                {result.approval_path.map((step, idx) => (
                  <div key={`${step}-${idx}`} className="flex items-center gap-2 text-sm">
                    <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-gray-900 text-white text-xs">
                      {idx + 1}
                    </span>
                    <span>{step}</span>
                  </div>
                ))}
              </div>
            </Card>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card className="p-4">
              <div className="font-medium mb-2">Policy Exceptions</div>
              {result.exceptions?.length ? (
                <ul className="space-y-2 text-sm">
                  {result.exceptions.map((ex, i) => (
                    <li key={`${ex.code}-${i}`} className="border rounded p-2">
                      <div className="flex items-center justify-between">
                        <span className="font-medium">{ex.code}</span>
                        <span
                          className={`text-xs rounded px-2 py-0.5 ${
                            ex.severity === "high"
                              ? "bg-red-100 text-red-700"
                              : ex.severity === "medium"
                              ? "bg-yellow-100 text-yellow-700"
                              : "bg-blue-100 text-blue-700"
                          }`}
                        >
                          {ex.severity}
                        </span>
                      </div>
                      <div className="text-gray-700 mt-1">{ex.message}</div>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="text-sm text-gray-500">No policy exceptions detected.</div>
              )}
            </Card>

            <Card className="p-4">
              <div className="font-medium mb-2">AI Recommendations</div>
              {result.recommendations?.length ? (
                <ul className="list-disc ml-5 text-sm space-y-1">
                  {result.recommendations.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
              ) : (
                <div className="text-sm text-gray-500">No recommendations generated.</div>
              )}
            </Card>
          </div>

          <Card className="p-4">
            <div className="font-medium mb-2">Deal Desk AI Memo</div>
            <pre className="whitespace-pre-wrap text-sm bg-slate-50 border rounded p-3">
              {result.memo}
            </pre>
          </Card>
        </>
      )}

      {scenarioResult && (
        <>
          <Card className="p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="font-medium">Scenario Mode Impact</div>
              <Button variant="outline" onClick={applyScenarioToDeal}>
                Apply Scenario to Deal
              </Button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {scenarioCompareCards.map((c) => {
                const fmt = (v: any) => {
                  if (typeof v !== "number") return String(v);
                  if ((c as any).isPercent) return `${v.toFixed(2)}%`;
                  return v.toLocaleString();
                };

                const deltaNum = typeof c.delta === "number" ? c.delta : 0;
                const deltaClass =
                  deltaNum > 0
                    ? "text-green-700 bg-green-50 border-green-200"
                    : deltaNum < 0
                    ? "text-red-700 bg-red-50 border-red-200"
                    : "text-gray-700 bg-gray-50 border-gray-200";

                return (
                  <Card key={c.label} className="p-3">
                    <div className="text-xs text-gray-500">{c.label}</div>

                    <div className="mt-2 grid grid-cols-3 gap-2 text-xs">
                      <div>
                        <div className="text-gray-400">Baseline</div>
                        <div className="font-semibold text-sm">{fmt(c.baseline)}</div>
                      </div>
                      <div>
                        <div className="text-gray-400">Scenario</div>
                        <div className="font-semibold text-sm">{fmt(c.scenario)}</div>
                      </div>
                      <div>
                        <div className="text-gray-400">Delta</div>
                        <div
                          className={`inline-flex rounded border px-2 py-0.5 text-xs font-medium ${deltaClass}`}
                        >
                          {fmt(c.delta)}
                        </div>
                      </div>
                    </div>
                  </Card>
                );
              })}
            </div>
          </Card>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card className="p-4">
              <div className="font-medium mb-2">Baseline Approval Path</div>
              <div className="space-y-2">
                {(scenarioResult.baseline?.approval_path || []).map((step: string, idx: number) => (
                  <div key={`b-${step}-${idx}`} className="flex items-center gap-2 text-sm">
                    <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-gray-700 text-white text-xs">
                      {idx + 1}
                    </span>
                    <span>{step}</span>
                  </div>
                ))}
              </div>
            </Card>

            <Card className="p-4">
              <div className="font-medium mb-2">Scenario Approval Path</div>
              <div className="space-y-2">
                {(scenarioResult.scenario?.approval_path || []).map((step: string, idx: number) => (
                  <div key={`s-${step}-${idx}`} className="flex items-center gap-2 text-sm">
                    <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-black text-white text-xs">
                      {idx + 1}
                    </span>
                    <span>{step}</span>
                  </div>
                ))}
              </div>
            </Card>
          </div>

          <Card className="p-4">
            <div className="font-medium mb-2">Scenario Notes</div>
            <ul className="list-disc ml-5 text-sm space-y-1">
              {(scenarioResult.explanation || []).map((x, i) => (
                <li key={i}>{x}</li>
              ))}
            </ul>
          </Card>
        </>
      )}

      {(parsedRules.length > 0 || policyEvalResult) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Card className="p-4">
            <div className="font-medium mb-2">Parsed Policy Rules</div>
            {parsedRules.length ? (
              <div className="space-y-2 text-sm">
                {parsedRules.map((r) => (
                  <div key={r.rule_id} className="border rounded p-2">
                    <div className="font-medium">{r.name}</div>
                    <div className="text-gray-600 text-xs mt-1">{r.source_text}</div>
                    <div className="text-xs mt-1">
                      Condition: <code>{JSON.stringify(r.condition)}</code>
                    </div>
                    <div className="text-xs">
                      Action: <code>{JSON.stringify(r.action)}</code>
                    </div>
                    {r.parse_status && (
                      <div className="text-xs text-amber-700 mt-1">
                        Parse status: {r.parse_status}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-sm text-gray-500">No rules parsed yet.</div>
            )}
          </Card>

          <Card className="p-4">
            <div className="font-medium mb-2">Policy Evaluation Result</div>
            {policyEvalResult ? (
              <div className="space-y-3 text-sm">
                <div>
                  <div className="text-xs text-gray-500">Required Approvals</div>
                  <div className="mt-1 flex flex-wrap gap-2">
                    {(policyEvalResult.required_approvals || []).length ? (
                      policyEvalResult.required_approvals.map((a) => (
                        <span key={a} className="text-xs rounded px-2 py-1 bg-slate-100 border">
                          {a}
                        </span>
                      ))
                    ) : (
                      <span className="text-gray-500">None triggered</span>
                    )}
                  </div>
                </div>

                <div>
                  <div className="text-xs text-gray-500 mb-1">Triggered Rules</div>
                  {(policyEvalResult.triggered_rules || []).length ? (
                    <ul className="space-y-2">
                      {policyEvalResult.triggered_rules.map((tr) => (
                        <li key={tr.rule_id} className="border rounded p-2">
                          <div className="font-medium">{tr.name}</div>
                          <div className="text-xs text-gray-600">{tr.source_text}</div>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <div className="text-gray-500">No policy rules triggered.</div>
                  )}
                </div>

                <div>
                  <div className="text-xs text-gray-500 mb-1">Evaluation Context</div>
                  <pre className="whitespace-pre-wrap text-xs bg-slate-50 border rounded p-2">
                    {JSON.stringify(policyEvalResult.context || {}, null, 2)}
                  </pre>
                </div>
              </div>
            ) : (
              <div className="text-sm text-gray-500">Run “Evaluate Policies” to test on this deal.</div>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
