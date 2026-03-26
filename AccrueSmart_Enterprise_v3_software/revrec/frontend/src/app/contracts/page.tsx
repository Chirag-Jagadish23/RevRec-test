"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/src/lib/api";
import { Input } from "@/src/components/ui/input";
import { Button } from "@/src/components/ui/button";
import { Card } from "@/src/components/ui/card";
import { toast } from "sonner";

type LineItem = { product_code: string; amount: number };

type Milestone = {
  id: number;
  contract_id: string;
  product_code: string;
  milestone_date: string;
  amount: number;
  description: string;
  is_locked: boolean;
  locked_at: string | null;
};

type NewMilestoneForm = {
  milestone_date: string;
  amount: number;
  description: string;
};

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

type ContractModificationRecord = {
  id: number;
  modified_at: string;
  change_type: string;
  treatment: string;
  effective_date: string;
  notes: string | null;
  snapshot_before: { header: any; lines: any[] };
  snapshot_after: { header: any; lines: any[] };
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

  // milestones: keyed by product_code
  const [milestones, setMilestones] = useState<Record<string, Milestone[]>>({});
  // new milestone forms: keyed by product_code
  const [newMilestoneForms, setNewMilestoneForms] = useState<Record<string, NewMilestoneForm>>({});

  // --- Amendment state ---
  const [isExistingContract, setIsExistingContract] = useState(false);
  const [showAmendModal, setShowAmendModal] = useState(false);
  const [amendEffectiveDate, setAmendEffectiveDate] = useState(new Date().toISOString().split("T")[0]);
  const [amendTreatment, setAmendTreatment] = useState<"prospective" | "cumulative_catch_up">("prospective");
  const [amendChangeType, setAmendChangeType] = useState("other");
  const [amendNotes, setAmendNotes] = useState("");
  const [amendSaving, setAmendSaving] = useState(false);
  // Set after a successful amendment; passed to next Allocate Revenue call
  const [pendingAmendment, setPendingAmendment] = useState<{ effective_date: string; treatment: string } | null>(null);
  const [modifications, setModifications] = useState<ContractModificationRecord[]>([]);

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
    loadMilestones(contract_id);
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

      // Contract exists in DB — enable amendment workflow
      setIsExistingContract(true);
      setPendingAmendment(null);
      await loadModifications(contract_id);
    } catch {
      // fine if contract not saved yet
      setIsExistingContract(false);
      setModifications([]);
    }
  }

  async function loadModifications(cid: string) {
    try {
      const res = await api(`/contracts/${encodeURIComponent(cid)}/modifications`);
      setModifications(Array.isArray(res) ? res : []);
    } catch {
      setModifications([]);
    }
  }

  async function submitAmendment() {
    if (!amendEffectiveDate) {
      toast.error("Effective date is required");
      return;
    }
    setAmendSaving(true);
    try {
      const res = await api(`/contracts/${encodeURIComponent(contract_id)}/modify`, {
        method: "POST",
        body: JSON.stringify({
          customer,
          transaction_price: Number(transaction_price || 0),
          start_date: startDate,
          end_date: endDate,
          lines: items.map((i) => ({ product_code: i.product_code, amount: Number(i.amount || 0) })),
          effective_date: amendEffectiveDate,
          treatment: amendTreatment,
          change_type: amendChangeType,
          notes: amendNotes || null,
        }),
      });

      setShowAmendModal(false);
      setPendingAmendment({ effective_date: amendEffectiveDate, treatment: amendTreatment });
      await loadModifications(contract_id);
      toast.success(`Amendment recorded (ID: ${res.modification_id}). Re-allocate to apply.`);
    } catch (e) {
      console.error(e);
      toast.error("Failed to save amendment");
    } finally {
      setAmendSaving(false);
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

  async function loadMilestones(cid: string) {
    try {
      const res = await api(`/milestones/${encodeURIComponent(cid)}`);
      const list: Milestone[] = Array.isArray(res) ? res : [];
      const grouped: Record<string, Milestone[]> = {};
      for (const m of list) {
        if (!grouped[m.product_code]) grouped[m.product_code] = [];
        grouped[m.product_code].push(m);
      }
      setMilestones(grouped);
    } catch {
      setMilestones({});
    }
  }

  async function addMilestone(product_code: string) {
    const form = newMilestoneForms[product_code];
    if (!form?.milestone_date || !form?.amount) {
      toast.error("Date and amount are required");
      return;
    }
    try {
      await api("/milestones", {
        method: "POST",
        body: JSON.stringify({
          contract_id,
          product_code,
          milestone_date: form.milestone_date,
          amount: Number(form.amount),
          description: form.description || "",
        }),
      });
      // clear this product's form
      setNewMilestoneForms((prev) => ({ ...prev, [product_code]: { milestone_date: "", amount: 0, description: "" } }));
      await loadMilestones(contract_id);
      toast.success("Milestone added");
    } catch {
      toast.error("Failed to add milestone");
    }
  }

  async function lockMilestone(id: number) {
    try {
      await api(`/milestones/${id}/lock`, { method: "PATCH" });
      await loadMilestones(contract_id);
      toast.success("Milestone locked — re-allocate to generate schedule row");
    } catch {
      toast.error("Failed to lock milestone");
    }
  }

  async function unlockMilestone(id: number) {
    try {
      await api(`/milestones/${id}/unlock`, { method: "PATCH" });
      await loadMilestones(contract_id);
      toast.success("Milestone unlocked");
    } catch {
      toast.error("Failed to unlock milestone");
    }
  }

  async function deleteMilestone(id: number) {
    try {
      await api(`/milestones/${id}`, { method: "DELETE" });
      await loadMilestones(contract_id);
      toast.success("Milestone deleted");
    } catch (e: any) {
      toast.error(e?.message || "Failed to delete milestone");
    }
  }

  function updateMilestoneForm(product_code: string, field: keyof NewMilestoneForm, value: string) {
    setNewMilestoneForms((prev) => ({
      ...prev,
      [product_code]: {
        ...prev[product_code],
        [field]: field === "amount" ? parseFloat(value || "0") : value,
      },
    }));
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
      const body: any = { contract_id };
      if (pendingAmendment) {
        body.effective_date = pendingAmendment.effective_date;
        body.treatment = pendingAmendment.treatment;
      }

      const res = await api("/contracts/allocate", {
        method: "POST",
        body: JSON.stringify(body),
      });

      setAllocResult(res);
      setPendingAmendment(null); // amendment has been applied
      await reloadSchedule();
      await loadReferenceData();

      if (res.warnings?.length) {
        res.warnings.forEach((w: string) => toast.message(w));
      } else {
        toast.success("Allocation complete");
      }
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
          const enriched = lineEnriched[idx];
          const isMilestone = enriched?.rule_type === "milestone";
          const productMilestones = milestones[item.product_code] || [];
          const form = newMilestoneForms[item.product_code] || { milestone_date: "", amount: 0, description: "" };

          const backendAlloc = backendAllocations.find(a => a.product_code === item.product_code);
          const allocatedTotal = backendAlloc?.allocated_total ?? sspAllocationPreview[idx]?.alloc_preview ?? 0;
          const milestoneTotal = productMilestones.reduce((s, m) => s + Number(m.amount), 0);
          const milestoneDiff = allocatedTotal - milestoneTotal;
          const showCoverageWarning = isMilestone && allocatedTotal > 0 && Math.abs(milestoneDiff) > 0.01;

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

              {/* Milestone management — only shown for milestone rule_type */}
              {isMilestone && (
                <div className="border border-amber-200 rounded-md p-3 bg-amber-50 space-y-3 mt-2">
                  <div className="flex items-center justify-between">
                    <div className="text-xs font-semibold text-amber-800">Milestones</div>
                    {allocatedTotal > 0 && (
                      <div className="text-xs text-gray-600">
                        Allocated: <span className="font-medium">${Number(allocatedTotal).toLocaleString(undefined, { maximumFractionDigits: 2 })}</span>
                        {" · "}Milestones total: <span className="font-medium">${milestoneTotal.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span>
                      </div>
                    )}
                  </div>

                  {showCoverageWarning && (
                    <div className={`text-xs rounded px-2 py-1 ${milestoneDiff > 0 ? "bg-yellow-100 text-yellow-800 border border-yellow-300" : "bg-red-100 text-red-800 border border-red-300"}`}>
                      {milestoneDiff > 0
                        ? `$${milestoneDiff.toFixed(2)} of allocated revenue is not covered by any milestone — add more milestones or increase amounts.`
                        : `Milestones exceed allocated revenue by $${Math.abs(milestoneDiff).toFixed(2)} — reduce milestone amounts.`
                      }
                    </div>
                  )}

                  {/* Existing milestones */}
                  {productMilestones.length > 0 && (
                    <table className="min-w-full text-xs">
                      <thead>
                        <tr className="border-b border-amber-200">
                          <th className="p-1 text-left">Date</th>
                          <th className="p-1 text-left">Description</th>
                          <th className="p-1 text-right">Amount</th>
                          <th className="p-1 text-center">Status</th>
                          <th className="p-1 text-center">Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {productMilestones.map((m) => (
                          <tr key={m.id} className="border-b border-amber-100">
                            <td className="p-1">{m.milestone_date}</td>
                            <td className="p-1 text-gray-600">{m.description || "-"}</td>
                            <td className="p-1 text-right">${Number(m.amount).toLocaleString()}</td>
                            <td className="p-1 text-center">
                              {m.is_locked ? (
                                <span className="text-green-700 font-semibold">Locked</span>
                              ) : (
                                <span className="text-gray-500">Pending</span>
                              )}
                            </td>
                            <td className="p-1 text-center flex gap-1 justify-center">
                              {m.is_locked ? (
                                <Button size="sm" variant="outline" onClick={() => unlockMilestone(m.id)}>
                                  Unlock
                                </Button>
                              ) : (
                                <Button size="sm" onClick={() => lockMilestone(m.id)}>
                                  Lock
                                </Button>
                              )}
                              {!m.is_locked && (
                                <Button size="sm" variant="destructive" onClick={() => deleteMilestone(m.id)}>
                                  Delete
                                </Button>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}

                  {/* Add new milestone form */}
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-2 items-end">
                    <Input
                      type="date"
                      value={form.milestone_date}
                      onChange={(e) => updateMilestoneForm(item.product_code, "milestone_date", e.target.value)}
                      placeholder="Milestone date"
                    />
                    <Input
                      type="number"
                      value={form.amount || ""}
                      onChange={(e) => updateMilestoneForm(item.product_code, "amount", e.target.value)}
                      placeholder="Amount"
                    />
                    <Input
                      value={form.description}
                      onChange={(e) => updateMilestoneForm(item.product_code, "description", e.target.value)}
                      placeholder="Description (optional)"
                    />
                    <Button variant="outline" onClick={() => addMilestone(item.product_code)}>
                      + Add Milestone
                    </Button>
                  </div>
                  <div className="text-xs text-amber-700">
                    Lock a milestone to recognize revenue. Then click <span className="font-medium">Allocate Revenue</span> to generate the schedule row.
                  </div>
                </div>
              )}
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

      {/* Pending amendment banner */}
      {pendingAmendment && (
        <div className="rounded-md border border-blue-300 bg-blue-50 px-4 py-3 text-sm text-blue-800">
          <span className="font-semibold">Amendment pending:</span>{" "}
          {pendingAmendment.treatment === "prospective"
            ? `Prospective — new terms will apply from ${pendingAmendment.effective_date} forward.`
            : `Cumulative catch-up — a delta row will be posted to ${pendingAmendment.effective_date.slice(0, 7)} and full schedule restated.`}
          {" "}Click <span className="font-medium">Allocate Revenue</span> to apply.
          <button
            className="ml-3 text-blue-600 underline text-xs"
            onClick={() => setPendingAmendment(null)}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Actions */}
      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" onClick={saveContract}>
          Save Contract
        </Button>
        {isExistingContract && (
          <Button variant="outline" onClick={() => setShowAmendModal(true)}>
            Save as Amendment
          </Button>
        )}
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

      {/* Amendment history */}
      {modifications.length > 0 && (
        <Card className="p-4 space-y-3">
          <h2 className="font-medium text-sm text-gray-700">Amendment History ({modifications.length})</h2>
          <div className="overflow-x-auto">
            <table className="min-w-full text-xs">
              <thead>
                <tr className="border-b bg-gray-50">
                  <th className="p-2 text-left">#</th>
                  <th className="p-2 text-left">Date Recorded</th>
                  <th className="p-2 text-left">Effective Date</th>
                  <th className="p-2 text-left">Change Type</th>
                  <th className="p-2 text-left">Treatment</th>
                  <th className="p-2 text-left">Notes</th>
                  <th className="p-2 text-right">Txn Price Before</th>
                  <th className="p-2 text-right">Txn Price After</th>
                </tr>
              </thead>
              <tbody>
                {modifications.map((m) => (
                  <tr key={m.id} className="border-b">
                    <td className="p-2">{m.id}</td>
                    <td className="p-2">{m.modified_at.slice(0, 16).replace("T", " ")}</td>
                    <td className="p-2 font-medium">{m.effective_date}</td>
                    <td className="p-2">{m.change_type}</td>
                    <td className="p-2">
                      <span className={`px-1 rounded text-xs ${m.treatment === "prospective" ? "bg-blue-100 text-blue-800" : "bg-purple-100 text-purple-800"}`}>
                        {m.treatment}
                      </span>
                    </td>
                    <td className="p-2 text-gray-600">{m.notes || "-"}</td>
                    <td className="p-2 text-right">${Number(m.snapshot_before.header.transaction_price).toLocaleString()}</td>
                    <td className="p-2 text-right">${Number(m.snapshot_after.header.transaction_price).toLocaleString()}</td>
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

      {/* Amendment modal */}
      {showAmendModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-lg space-y-4">
            <h2 className="text-lg font-semibold">Record Contract Amendment</h2>
            <p className="text-sm text-gray-600">
              This will save the current form values as an amendment and record a full before/after snapshot.
              You can then re-allocate to apply the new terms.
            </p>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-gray-700 block mb-1">Effective Date <span className="text-red-500">*</span></label>
                <input
                  type="date"
                  className="border rounded px-3 py-2 text-sm w-full"
                  value={amendEffectiveDate}
                  onChange={(e) => setAmendEffectiveDate(e.target.value)}
                />
                <p className="text-xs text-gray-500 mt-1">The date from which the new contract terms apply.</p>
              </div>

              <div>
                <label className="text-xs font-medium text-gray-700 block mb-1">ASC 606 Treatment</label>
                <select
                  className="border rounded px-3 py-2 text-sm w-full"
                  value={amendTreatment}
                  onChange={(e) => setAmendTreatment(e.target.value as "prospective" | "cumulative_catch_up")}
                >
                  <option value="prospective">Prospective — new terms apply from effective date forward</option>
                  <option value="cumulative_catch_up">Cumulative catch-up — post delta adjustment to current period</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-medium text-gray-700 block mb-1">Change Type</label>
                <select
                  className="border rounded px-3 py-2 text-sm w-full"
                  value={amendChangeType}
                  onChange={(e) => setAmendChangeType(e.target.value)}
                >
                  <option value="price_change">Price change</option>
                  <option value="add_product">Add product / performance obligation</option>
                  <option value="remove_product">Remove product / performance obligation</option>
                  <option value="other">Other</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-medium text-gray-700 block mb-1">Notes (optional)</label>
                <textarea
                  className="border rounded px-3 py-2 text-sm w-full"
                  rows={2}
                  placeholder="e.g. Customer requested price reduction per email 2025-06-01"
                  value={amendNotes}
                  onChange={(e) => setAmendNotes(e.target.value)}
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setShowAmendModal(false)}>
                Cancel
              </Button>
              <Button onClick={submitAmendment} disabled={amendSaving}>
                {amendSaving ? "Saving…" : "Save Amendment"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
