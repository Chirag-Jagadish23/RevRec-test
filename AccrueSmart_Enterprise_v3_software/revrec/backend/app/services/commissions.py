from __future__ import annotations
from typing import Dict, List
from datetime import date

def _add_months(d: date, n: int) -> date:
    y = d.year + (d.month - 1 + n) // 12
    m = (d.month - 1 + n) % 12 + 1
    day = min(d.day, 28)
    return date(y, m, day)

def commission_amort_schedule(
    contract_id: str,
    contract_name: str,
    commission_amount: float,
    start_date: str,
    amortization_months: int,
) -> Dict:
    if commission_amount < 0:
        raise ValueError("commission_amount must be >= 0")
    if amortization_months <= 0:
        raise ValueError("amortization_months must be > 0")

    sd = date.fromisoformat(start_date)
    monthly = commission_amount / amortization_months

    rows: List[Dict] = []
    asset_balance = commission_amount
    total_amort = 0.0

    for i in range(amortization_months):
        d = _add_months(sd, i)
        amort = monthly if i < amortization_months - 1 else (commission_amount - total_amort)
        total_amort += amort
        asset_balance -= amort

        rows.append({
            "period": i + 1,
            "date": d.isoformat(),
            "amortization_expense": round(amort, 2),
            "cumulative_amortization": round(total_amort, 2),
            "deferred_commission_asset": round(asset_balance, 2),
        })

    return {
        "contract_id": contract_id,
        "contract_name": contract_name,
        "commission_amount": round(commission_amount, 2),
        "amortization_months": amortization_months,
        "rows": rows,
        "ending_asset_balance": round(asset_balance, 2),
    }
