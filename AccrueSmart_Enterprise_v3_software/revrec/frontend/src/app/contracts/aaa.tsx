:::writing{variant=“standard” id=“contractsfull01”}
“use client”;
import { useState, useEffect } from “react”;
import { api } from “@/src/lib/api”;
import { Input } from “@/src/components/ui/input”;
import { Button } from “@/src/components/ui/button”;
import { Card } from “@/src/components/ui/card”;
import { toast } from “sonner”;

type LineItem = { product_code: string; amount: number };

export default function ContractsPage() {

// –––––––– Contract Fields ––––––––
const [contract_id, setContractId] = useState(“C-TEST”);
const [customer, setCustomer] = useState(“DemoCo”);
const [transaction_price, setTxnPrice] = useState(50000);

const [startDate, setStartDate] = useState(“2025-01-01”);
const [endDate, setEndDate] = useState(“2025-12-31”);
const [evergreen, setEvergreen] = useState(false);

// –––––––– AI ––––––––
const [contractText, setContractText] = useState(””);

// –––––––– Line items ––––––––
const [items, setItems] = useState<LineItem[]>([
{ product_code: “SKU-001”, amount: 20000 },
{ product_code: “SKU-002”, amount: 30000 },
]);

// –––––––– Results ––––––––
const [payload, setPayload] = useState({});
const [allocResult, setAllocResult] = useState(null);
const [scheduleGrid, setScheduleGrid] = useState<any[]>([]);

// –––––––– Load Saved Schedule ––––––––
async function reloadSchedule() {
if (!contract_id) return;
try {
const data = await api(/schedules/grid/${encodeURIComponent(contract_id)});
setScheduleGrid(data || []);
} catch {
setScheduleGrid([]);
}
}

// –––––––– Sync + Invalidate Schedule ––––––––
useEffect(() => {
setAllocResult(null);

if (contract_id) {
  api(`/schedules/grid/${encodeURIComponent(contract_id)}`, {
    method: "DELETE",
  }).catch(() => {});
}

setPayload({
  contract_id,
  customer,
  transaction_price,
  pos: [
    {
      po_id: "PO-1",
      description: "Subscription",
      ssp: items[0]?.amount || 0,
      method: "straight_line",
      start_date: startDate,
      end_date: evergreen ? null : endDate,
    },
    {
      po_id: "PO-2",
      description: "Implementation",
      ssp: items[1]?.amount || 0,
      method: "milestone",
      params: {
        milestones: [
          { id: "M1", percent_of_price: 0.5, met_date: startDate },
          { id: "M2", percent_of_price: 0.5, met_date: endDate },
        ],
      },
    },
  ],
});
}, [contract_id, customer, transaction_price, startDate, endDate, evergreen, items]);

// reload when contract changes
useEffect(() => {
reloadSchedule();
}, [contract_id]);

// –––––––– Actions ––––––––
async function allocate() {
try {
const res = await api(”/contracts/allocate”, {
method: “POST”,
body: JSON.stringify(payload),
});
  setAllocResult(res);
  await reloadSchedule();

  toast.success("Accounting revenue calculated");
} catch (e) {
  toast.error("Allocation failed");
  console.error(e);
}
}

async function aiGenerate() {
try {
const res = await api(”/schedules/ai-generate”, {
method: “POST”,
body: JSON.stringify({
contract_id,
text: contractText,
default_start: startDate,
line_hints: items,
}),
})
  const rows = Object.entries(res.schedule as Record<string, number>).map(
    ([period, amount], ix) => ({
      line_no: ix + 1,
      period,
      amount,
      product_code: "",
      revrec_code: "",
      source: "ai",
    })
  );

  await api(`/schedules/grid/${encodeURIComponent(contract_id)}`, {
    method: "POST",
    body: JSON.stringify({ rows }),
  });

  await reloadSchedule();

  toast.success("AI schedule generated & refreshed");

} catch (e) {
  toast.error("AI generation failed");
  console.error(e);
};
}

function updateItem(idx: number, field: keyof LineItem, value: string) {
const copy = […items];
copy[idx] = {
…copy[idx],
[field]: field === “amount” ? parseFloat(value || “0”) : value,
};
setItems(copy);
}

// –––––––– UI ––––––––
return (

Contracts
  <Card className="p-4 space-y-3">
    <h2 className="font-medium text-sm text-gray-700">Contract Details</h2>

    <div className="grid grid-cols-3 gap-2">
      <Input value={contract_id} onChange={(e:any)=>setContractId(e.target.value)} placeholder="Contract ID" />
      <Input value={customer} onChange={(e:any)=>setCustomer(e.target.value)} placeholder="Customer" />
      <Input type="number" value={transaction_price} onChange={(e:any)=>setTxnPrice(parseFloat(e.target.value||"0"))} placeholder="Transaction Price" />
    </div>

    <div className="grid grid-cols-3 gap-2 items-center">
      <Input type="date" value={startDate} onChange={(e:any)=>setStartDate(e.target.value)} />
      <Input type="date" disabled={evergreen} value={endDate} onChange={(e:any)=>setEndDate(e.target.value)} />
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={evergreen} onChange={()=>setEvergreen(!evergreen)} />
        Evergreen contract
      </label>
    </div>
  </Card>

  <Card className="p-4 space-y-3">
    <h2 className="font-medium text-sm text-gray-700">Line Items</h2>
    {items.map((item, idx) => (
      <div key={idx} className="grid grid-cols-3 gap-2">
        <Input value={item.product_code} onChange={(e:any)=>updateItem(idx,"product_code",e.target.value)} placeholder="Product Code" />
        <Input type="number" value={item.amount} onChange={(e:any)=>updateItem(idx,"amount",e.target.value)} placeholder="Amount" />
        <Button onClick={()=>setItems(items.filter((_,i)=>i!==idx))}>Remove</Button>
      </div>
    ))}
    <Button onClick={()=>setItems([...items,{product_code:"",amount:0}])}>+ Add Line</Button>
  </Card>

  <Card className="p-4 space-y-3">
    <h2 className="font-medium text-sm text-gray-700">Contract Text (for AI)</h2>
    <textarea className="border rounded p-2 w-full h-32 text-sm" value={contractText} onChange={(e)=>setContractText(e.target.value)} />
  </Card>

  <div className="flex gap-2">
    <Button onClick={allocate}>Allocate Revenue</Button>
    <Button onClick={aiGenerate}>AI Build Schedule</Button>
  </div>

  {allocResult && (
    <Card className="p-4">
      <h2 className="font-medium text-sm text-gray-700 mb-2">Allocation Result</h2>
      <pre className="text-xs bg-slate-50 p-3 rounded border overflow-x-auto">
        {JSON.stringify(allocResult, null, 2)}
      </pre>
    </Card>
  )}

  {scheduleGrid.length > 0 && (
    <Card className="p-4">
      <h2 className="font-medium text-sm text-gray-700 mb-2">Saved Revenue Schedule</h2>
      <table className="w-full text-sm border">
        <thead className="bg-gray-100">
          <tr>
            <th className="p-2 border">Period</th>
            <th className="p-2 border">Amount</th>
            <th className="p-2 border">Source</th>
          </tr>
        </thead>
        <tbody>
          {scheduleGrid.map((r:any,i:number)=>(
            <tr key={i}>
              <td className="p-2 border">{r.period}</td>
              <td className="p-2 border">${Number(r.amount).toLocaleString()}</td>
              <td className="p-2 border">{r.source}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  )}
</div>
