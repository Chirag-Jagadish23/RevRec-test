"use client";

import { useEffect, useState } from "react";
import { api } from "@/src/lib/api";
import { Input } from "@/src/components/ui/input";
import { Button } from "@/src/components/ui/button";
import { Card } from "@/src/components/ui/card";

type RevRec = {
  code: string;
  rule_type: string;
  description?: string;
};

type Product = {
  id: string;
  code: string;
  name: string;
};

export default function RevRecCodesPage() {
  const [list, setList] = useState<RevRec[]>([]);
  const [products, setProducts] = useState<Product[]>([]);

  const [code, setCode] = useState("");
  const [rule, setRule] = useState("straight_line");

  const [mapSku, setMapSku] = useState("");
  const [mapRrc, setMapRrc] = useState("");

  async function load() {
    try {
      setList(await api("/revrec_codes"));

      const prods = await api("/catalog");
      setProducts(
        prods.map((p: any) => ({
          id: p.product_code,
          code: p.product_code,
          name: p.name,
        }))
      );
    } catch (e) {
      console.error(e);
      alert("Failed to load revrec codes or catalog");
    }
  }

  async function add() {
    if (!code) return;

    try {
      await api("/revrec_codes", {
        method: "POST",
        body: JSON.stringify({
          code,
          rule_type: rule,
          description: `Rule ${code}`,
        }),
      });

      alert(`Added/updated RevRec code: ${code}`);
      setCode("");
      await load();
    } catch (e) {
      console.error(e);
      alert("Failed to add revrec code");
    }
  }

  async function map() {
    if (!mapSku || !mapRrc) return;

    try {
      await api("/revrec_codes/map", {
        method: "POST",
        body: JSON.stringify({
          product_code: mapSku,
          revrec_code: mapRrc,
        }),
      });

      alert(`Mapped ${mapSku} → ${mapRrc}`);
      setMapSku("");
      setMapRrc("");
      await load();
    } catch (e) {
      console.error(e);
      alert("Mapping failed");
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <h1 className="text-xl font-semibold">RevRec Codes</h1>

      <Card className="p-4 space-y-2">
        <div className="grid grid-cols-3 gap-2">
          <Input
            placeholder="Code"
            value={code}
            onChange={(e) => setCode(e.target.value)}
          />
          <select
            className="border rounded px-2"
            value={rule}
            onChange={(e) => setRule(e.target.value)}
          >
            <option value="straight_line">straight_line</option>
            <option value="immediate">immediate</option>
          </select>
          <Button onClick={add}>Add RevRec Code</Button>
        </div>
      </Card>

      <Card className="p-4 space-y-2">
        <div className="grid grid-cols-3 gap-2">
          <Input
            placeholder="Product Code (SKU-001)"
            value={mapSku}
            onChange={(e) => setMapSku(e.target.value)}
          />
          <Input
            placeholder="RevRec Code"
            value={mapRrc}
            onChange={(e) => setMapRrc(e.target.value)}
          />
          <Button onClick={map}>Map Product → RevRec</Button>
        </div>

        {products.length > 0 && (
          <div className="text-xs text-gray-600 pt-2">
            Products loaded: {products.map((p) => p.code).join(", ")}
          </div>
        )}
      </Card>

      <Card className="p-0 overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="p-2 text-left">Code</th>
              <th className="p-2 text-left">Rule</th>
              <th className="p-2 text-left">Description</th>
            </tr>
          </thead>
          <tbody>
            {list.map((rr) => (
              <tr key={rr.code} className="border-t">
                <td className="p-2">{rr.code}</td>
                <td className="p-2">{rr.rule_type}</td>
                <td className="p-2">{rr.description || "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
