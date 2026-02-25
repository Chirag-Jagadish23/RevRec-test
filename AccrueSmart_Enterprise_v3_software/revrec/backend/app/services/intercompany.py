from __future__ import annotations
from typing import Dict, List

def eliminate_intercompany(balances: List[Dict]) -> Dict:
    """
    balances row example:
    {
      "from_entity": "Parent",
      "to_entity": "SubA",
      "account": "Intercompany AR",
      "amount": 1000
    }
    """
    rows = []
    total_abs = 0.0

    for b in balances:
        amt = float(b.get("amount", 0))
        total_abs += abs(amt)
        rows.append({
            "from_entity": b.get("from_entity"),
            "to_entity": b.get("to_entity"),
            "account": b.get("account", "Intercompany"),
            "book_amount": round(amt, 2),
            "elimination_entry": round(-amt, 2),
            "post_elimination_balance": 0.0,
        })

    return {
        "rows": rows,
        "pairs_processed": len(rows),
        "gross_intercompany_balance": round(total_abs, 2),
        "status": "eliminated",
    }
