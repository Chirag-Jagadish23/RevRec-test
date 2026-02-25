"use client";

import { useEffect, useState } from "react";
import { api } from "@/src/lib/api";
import { Input } from "@/src/components/ui/input";
import { Button } from "@/src/components/ui/button";
import { Card } from "@/src/components/ui/card";

type Product = {
  product_code: string;
  name: string;
  ssp: number;
  revrec_code: string;
};

export default function CatalogPage() {
  const [rows, setRows] = useState<Product[]>([]);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [ssp, setSsp] = useState("");
  const [revrec, setRevrec] = useState("STRAIGHT_LINE");

  async function load() {
    const data = await api("/catalog");
    setRows(data);
  }

  async function add() {
    if (!code || !name || !ssp) return;

    await api("/catalog", {
      method: "POST",
      body: JSON.stringify({
        product_code: code,
        name,
        ssp: parseFloat(ssp),
        revrec_code: revrec || "STRAIGHT_LINE",
      }),
    });

    setCode("");
    setName("");
    setSsp("");
    setRevrec("STRAIGHT_LINE");

    await load();
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="max-w-5xl mx-auto space-y-4">
      <h1 className="text-xl font-semibold">Product Catalog</h1>

      <Card className="p-4 space-y-2">
        <div className="grid grid-cols-4 gap-2">
          <Input
            placeholder="SKU Code"
            value={code}
            onChange={(e) => setCode(e.target.value)}
          />
          <Input
            placeholder="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <Input
            placeholder="SSP"
            type="number"
            value={ssp}
            onChange={(e) => setSsp(e.target.value)}
          />
          <Input
            placeholder="RevRec Code"
            value={revrec}
            onChange={(e) => setRevrec(e.target.value)}
          />
        </div>
        <Button onClick={add}>Add Product</Button>
      </Card>

      <Card className="p-0 overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="p-2 text-left">Code</th>
              <th className="p-2 text-left">Name</th>
              <th className="p-2 text-left">SSP</th>
              <th className="p-2 text-left">RevRec</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.product_code} className="border-t">
                <td className="p-2">{r.product_code}</td>
                <td className="p-2">{r.name}</td>
                <td className="p-2">{r.ssp}</td>
                <td className="p-2">{r.revrec_code}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
