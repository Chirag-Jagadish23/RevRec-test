from __future__ import annotations
from typing import Dict, List
from datetime import date

def _add_months(d: date, n: int) -> date:
    y = d.year + (d.month - 1 + n) // 12
    m = (d.month - 1 + n) % 12 + 1
    day = min(d.day, 28)
    return date(y, m, day)

def stock_comp_schedule(
    grant_id: str,
    employee_name: str,
    grant_date: str,
    total_fair_value: float,
    vest_months: int,
    cliff_months: int = 12,
    method: str = "straight_line",
) -> Dict:
    if vest_months <= 0:
      raise ValueError("vest_months must be > 0")
    if total_fair_value < 0:
      raise ValueError("total_fair_value must be >= 0")
    if cliff_months < 0 or cliff_months > vest_months:
      raise ValueError("cliff_months must be between 0 and vest_months")

    gd = date.fromisoformat(grant_date)
    monthly = total_fair_value / vest_months
    rows: List[Dict] = []
    recognized = 0.0

    for i in range(vest_months):
        d = _add_months(gd, i)
        expense = monthly if method == "straight_line" else monthly
        if i == vest_months - 1:
            expense = total_fair_value - recognized
        recognized += expense

        vested_pct = round(((i + 1) / vest_months) * 100, 2)
        if (i + 1) < cliff_months:
            vested_shares_pct = 0.0
        else:
            vested_shares_pct = vested_pct

        rows.append({
            "period": i + 1,
            "date": d.isoformat(),
            "comp_expense": round(expense, 2),
            "cumulative_comp_expense": round(recognized, 2),
            "vested_percent": vested_shares_pct,
            "unrecognized_comp": round(total_fair_value - recognized, 2),
        })

    return {
        "grant_id": grant_id,
        "employee_name": employee_name,
        "grant_date": grant_date,
        "total_fair_value": round(total_fair_value, 2),
        "vest_months": vest_months,
        "cliff_months": cliff_months,
        "rows": rows,
        "total_recognized": round(recognized, 2),
    }
