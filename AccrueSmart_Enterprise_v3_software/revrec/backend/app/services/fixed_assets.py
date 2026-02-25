# backend/app/services/fixed_assets.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, List, Literal, Optional, Any
import calendar
import csv
import io

# Backward-compatible method names + enterprise aliases
Method = Literal["sl", "ddb", "db_switch_sl", "straight_line", "double_declining"]
Convention = Literal["full_month", "mid_month", "half_year"]


@dataclass
class AssetInput:
    asset_id: str
    asset_name: str
    category: str
    in_service_date: date
    cost: float
    salvage_value: float
    useful_life_months: int
    method: Method = "sl"
    convention: Convention = "full_month"
    decline_rate: float = 2.0
    disposal_date: Optional[date] = None


# -------------------------
# Helpers
# -------------------------
def _parse_date_str(s: str) -> date:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        raise ValueError(f"Invalid date format '{s}', expected YYYY-MM-DD")


def _normalize_method(method: str) -> str:
    m = (method or "").strip().lower()
    if m in ("sl", "straight_line"):
        return "sl"
    if m in ("ddb", "double_declining"):
        return "ddb"
    if m == "db_switch_sl":
        return "db_switch_sl"
    raise ValueError(f"Unsupported method: {method}")


def _month_start(d: date) -> date:
    return date(d.year, d.month, 1)


def _month_end(d: date) -> date:
    last_day = calendar.monthrange(d.year, d.month)[1]
    return date(d.year, d.month, last_day)


def _add_months(d: date, n: int) -> date:
    # Keeps month-safe behavior
    y = d.year + (d.month - 1 + n) // 12
    m = (d.month - 1 + n) % 12 + 1
    return date(y, m, 1)


def _month_key(d: date) -> str:
    return f"{d.year:04d}-{str(d.month).zfill(2)}"


def _safe_round(x: float) -> float:
    return round(float(x), 2)


def _month_fraction(in_service_date: date, period_month_start: date, convention: Convention) -> float:
    # First-period convention factor only
    if convention == "full_month":
        return 1.0
    if convention == "mid_month":
        return 0.5
    if convention == "half_year":
        # For monthly schedule, approximate first 6 months as half weighting
        month_index = (period_month_start.year - in_service_date.year) * 12 + (
            period_month_start.month - in_service_date.month
        )
        return 0.5 if 0 <= month_index < 6 else 1.0
    return 1.0


# -------------------------
# Core Engine
# -------------------------
def compute_depreciation_schedule(
    asset_id: str,
    asset_name: str,
    category: str,
    in_service_date: str,
    cost: float,
    salvage_value: float,
    useful_life_months: int,
    method: Method = "sl",
    convention: Convention = "full_month",
    decline_rate: float = 2.0,
    disposal_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Backward-compatible depreciation engine with enhanced output.

    Supports:
      - sl / straight_line
      - ddb / double_declining
      - db_switch_sl
      - conventions: full_month, mid_month, half_year
      - optional disposal_date
    """
    # ---- validation ----
    if useful_life_months <= 0:
        raise ValueError("useful_life_months must be > 0")
    if cost < 0:
        raise ValueError("cost must be >= 0")
    if salvage_value < 0:
        raise ValueError("salvage_value must be >= 0")
    if salvage_value > cost:
        raise ValueError("salvage_value cannot exceed cost")
    if decline_rate <= 0:
        raise ValueError("decline_rate must be > 0")

    norm_method = _normalize_method(method)

    sd = _parse_date_str(in_service_date)
    dd = _parse_date_str(disposal_date) if disposal_date else None

    depreciable_basis = round(cost - salvage_value, 2)

    if depreciable_basis <= 0:
        return {
            "asset_id": asset_id,
            "asset_name": asset_name,
            "category": category,
            "in_service_date": sd.isoformat(),
            "rows": [],
            "summary": {
                "cost": _safe_round(cost),
                "salvage_value": _safe_round(salvage_value),
                "depreciable_basis": _safe_round(depreciable_basis),
                "total_depreciation": 0.0,
                "ending_nbv": _safe_round(cost),
                "ending_book_value": _safe_round(cost),
                "method": norm_method,
                "convention": convention,
                "periods": 0,
            },
        }

    rows: List[Dict[str, Any]] = []
    nbv = float(cost)
    accum = 0.0
    month0 = _month_start(sd)

    # Straight-line baseline
    sl_monthly_full = depreciable_basis / useful_life_months

    # DDB-style monthly rate
    annual_rate = decline_rate / (useful_life_months / 12.0)   # e.g. 2 / 5 years = 40%
    monthly_rate = annual_rate / 12.0

    for i in range(useful_life_months):
        period_start = _add_months(month0, i)
        period_end = _month_end(period_start)

        # Stop if disposed before this month begins
        if dd and period_start > _month_start(dd):
            break

        opening_nbv = nbv
        opening_accum = accum

        # convention fraction
        frac = 1.0
        if i == 0:
            frac = _month_fraction(sd, period_start, convention)

        # If disposed in this same month and using mid-month, cap to 0.5
        if dd and period_start == _month_start(dd) and convention == "mid_month":
            frac = min(frac, 0.5)

        max_dep_allowed = max(0.0, opening_nbv - salvage_value)
        if max_dep_allowed <= 0:
            break

        dep = 0.0
        method_used = norm_method

        if norm_method == "sl":
            dep = sl_monthly_full * frac
            method_used = "straight_line"

        elif norm_method == "ddb":
            dep = opening_nbv * monthly_rate * frac
            method_used = "double_declining"

        elif norm_method == "db_switch_sl":
            db_dep = opening_nbv * monthly_rate * frac

            remaining_months = max(1, useful_life_months - i)
            sl_remaining = max(0.0, opening_nbv - salvage_value) / remaining_months
            sl_dep = sl_remaining * frac

            if sl_dep > db_dep:
                dep = sl_dep
                method_used = "straight_line_switched"
            else:
                dep = db_dep
                method_used = "declining_balance"

        # Cap at salvage floor
        dep = min(dep, max_dep_allowed)
        dep = round(max(dep, 0.0), 2)

        accum = round(accum + dep, 2)
        nbv = round(nbv - dep, 2)

        # If final row / end of life / disposal month, clean drift to exact salvage when close
        is_last_planned_row = (i == useful_life_months - 1)
        is_disposal_row = dd is not None and period_start == _month_start(dd)
        if (is_last_planned_row or is_disposal_row) and abs(nbv - salvage_value) <= 0.05:
            drift = round(nbv - salvage_value, 2)
            dep = round(dep + drift, 2)
            accum = round(opening_accum + dep, 2)
            nbv = round(opening_nbv - dep, 2)

        rows.append({
            # old shape (compat)
            "period": i + 1,
            "month": _month_key(period_start),
            "depreciation_expense": dep,
            "accumulated_depreciation_opening": round(opening_accum, 2),
            "accumulated_depreciation_ending": accum,
            "net_book_value_opening": round(opening_nbv, 2),
            "net_book_value_ending": nbv,

            # new/audit-friendly fields
            "row_num": i + 1,
            "period_end_date": period_end.isoformat(),
            "method_used": method_used,
            "convention_factor": round(frac, 4),
            "opening_book_value": round(opening_nbv, 2),
            "accumulated_depreciation": accum,
            "closing_book_value": nbv,

            # export-friendly identifiers
            "asset_id": asset_id,
            "asset_name": asset_name,
            "category": category,
        })

        if nbv <= salvage_value:
            break

    total_dep = round(sum(r["depreciation_expense"] for r in rows), 2)

    return {
        "asset_id": asset_id,
        "asset_name": asset_name,
        "category": category,
        "in_service_date": sd.isoformat(),
        "rows": rows,
        "summary": {
            "cost": round(cost, 2),
            "salvage_value": round(salvage_value, 2),
            "depreciable_basis": round(depreciable_basis, 2),
            "total_depreciation": total_dep,
            "ending_nbv": round(nbv, 2),          # old key
            "ending_book_value": round(nbv, 2),   # new key
            "method": norm_method,
            "convention": convention,
            "decline_rate": round(decline_rate, 4),
            "periods": len(rows),
        },
    }


# -------------------------
# Journal generation
# -------------------------
def depreciation_journals(schedule: Dict[str, Any]) -> List[Dict[str, Any]]:
    asset_id = schedule["asset_id"]
    asset_name = schedule.get("asset_name", asset_id)
    rows = schedule.get("rows", [])
    out: List[Dict[str, Any]] = []

    for r in rows:
        memo = f"Depreciation - {asset_name} - Period {r['period']}"
        amt = float(r["depreciation_expense"])

        out.append({
            "asset_id": asset_id,
            "month": r["month"],
            "account": "Depreciation Expense",
            "debit": round(amt, 2),
            "credit": 0.0,
            "memo": memo,
        })
        out.append({
            "asset_id": asset_id,
            "month": r["month"],
            "account": "Accumulated Depreciation",
            "debit": 0.0,
            "credit": round(amt, 2),
            "memo": memo,
        })
    return out


# -------------------------
# CSV exports
# -------------------------
def export_depreciation_csv(payload: Dict[str, Any]) -> str:
    sched = compute_depreciation_schedule(**payload)
    buf = io.StringIO()

    # keep old columns + include new ones at end
    fieldnames = [
        "period",
        "month",
        "depreciation_expense",
        "accumulated_depreciation_opening",
        "accumulated_depreciation_ending",
        "net_book_value_opening",
        "net_book_value_ending",
        "period_end_date",
        "method_used",
        "convention_factor",
        "asset_id",
        "asset_name",
        "category",
    ]

    w = csv.DictWriter(buf, fieldnames=fieldnames)
    w.writeheader()
    for row in sched["rows"]:
        w.writerow({k: row.get(k) for k in fieldnames})

    return buf.getvalue()


def export_depreciation_journals_csv(payload: Dict[str, Any]) -> str:
    sched = compute_depreciation_schedule(**payload)
    journ = depreciation_journals(sched)

    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["asset_id", "month", "account", "debit", "credit", "memo"])
    w.writeheader()
    for row in journ:
        w.writerow(row)

    return buf.getvalue()
