"""
disclosure_service.py — Real DB query logic for ASC 606 disclosure pack.

Sections supported:
  1. Executive Revenue Summary      (4-year trend + YoY)
  3. Revenue Disaggregation          (product, current FY vs prior FY)
  4. Deferred Revenue Rollforward    (beginning / additions / recognized / ending)
  4b. Monthly Recognized             (month-by-month for deferred chart)
  6. RPO                             (future buckets by as-of date)
  6b. RPO by Product                 (detail schedule)
  7. Revenue Waterfall               (bookings / deferred / recognized)
  8. Contract Duration Mix           (annual / multi-year / short-term)
  13. Customer Concentration          (top 1 / 5 / 10)

Fiscal year = calendar year (Jan–Dec).
All amounts in USD, rounded to 2 decimal places.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

from sqlmodel import Session, select

from ..models.models import ContractRecord, Product, ScheduleRow


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fy_range(fiscal_year: int) -> tuple[str, str]:
    """Return (start_period, end_period) as YYYY-MM strings for a calendar FY."""
    return f"{fiscal_year}-01", f"{fiscal_year}-12"


def _recognition_sum(session: Session, period_start: str, period_end: str,
                     contract_ids: list[str] | None = None) -> float:
    stmt = (
        select(ScheduleRow)
        .where(ScheduleRow.period >= period_start)
        .where(ScheduleRow.period <= period_end)
        .where(ScheduleRow.is_adjustment == False)  # noqa: E712
        .where(ScheduleRow.event_type == "recognition")
    )
    if contract_ids is not None:
        stmt = stmt.where(ScheduleRow.contract_id.in_(contract_ids))
    return sum(r.amount for r in session.exec(stmt).all())


# ─────────────────────────────────────────────────────────────────────────────
# Section 1 — Executive Revenue Summary
# ─────────────────────────────────────────────────────────────────────────────

def get_executive_summary(session: Session, fiscal_year: int) -> Dict[str, Any]:
    """
    Total revenue for the current FY, prior FY, and a 4-year trend.

    Returns:
      {current_year, prior_year, yoy_change_pct, trend_by_year: {year: amount}}
    """
    trend: Dict[int, float] = {}
    for yr in range(fiscal_year - 3, fiscal_year + 1):
        start, end = _fy_range(yr)
        trend[yr] = round(_recognition_sum(session, start, end), 2)

    current = trend[fiscal_year]
    prior = trend.get(fiscal_year - 1, 0.0)
    yoy_pct = round(((current - prior) / prior * 100) if prior else 0.0, 1)

    return {
        "current_year": current,
        "prior_year": prior,
        "yoy_change_pct": yoy_pct,
        "trend_by_year": trend,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Section 3 — Revenue Disaggregation
# ─────────────────────────────────────────────────────────────────────────────

def get_revenue_disaggregation(
    session: Session, fiscal_year: int
) -> List[Dict[str, Any]]:
    """
    Aggregate recognized revenue by product_code for the given FY and prior FY.

    Returns list sorted by product_code:
      [{product_code, product_name, current, prior, variance_pct}]
    """
    def _sum_by_product(year: int) -> Dict[str, float]:
        start, end = _fy_range(year)
        rows = session.exec(
            select(ScheduleRow)
            .where(ScheduleRow.period >= start)
            .where(ScheduleRow.period <= end)
            .where(ScheduleRow.is_adjustment == False)  # noqa: E712
            .where(ScheduleRow.event_type == "recognition")
        ).all()
        totals: Dict[str, float] = {}
        for r in rows:
            key = r.product_code or "Unassigned"
            totals[key] = totals.get(key, 0.0) + r.amount
        return totals

    current = _sum_by_product(fiscal_year)
    prior = _sum_by_product(fiscal_year - 1)
    products = {p.product_code: p.name for p in session.exec(select(Product)).all()}

    result: List[Dict[str, Any]] = []
    for code in sorted(set(current) | set(prior)):
        curr = current.get(code, 0.0)
        pri = prior.get(code, 0.0)
        variance = round(((curr - pri) / pri * 100) if pri else 0.0, 1)
        result.append({
            "product_code": code,
            "product_name": products.get(code, code),
            "current": round(curr, 2),
            "prior": round(pri, 2),
            "variance_pct": variance,
        })
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Section 4 — Deferred Revenue Rollforward
# ─────────────────────────────────────────────────────────────────────────────

def get_contract_balances_rollforward(
    session: Session, fiscal_year: int
) -> Dict[str, Any]:
    """
    Deferred revenue rollforward for the fiscal year.

    Methodology (schedule-row surrogate for billing data):
      Beginning = future rows from pre-FY contracts, starting at FY open.
      Additions  = all rows for contracts that started during the FY.
      Recognized = all rows recognized within the FY period range.
      Ending     = Beginning + Additions − Recognized.
    """
    fy_start, fy_end = _fy_range(fiscal_year)
    fy_start_date = date(fiscal_year, 1, 1)
    fy_end_date = date(fiscal_year, 12, 31)

    prior_ids: list[str] = [
        c.contract_id
        for c in session.exec(
            select(ContractRecord).where(ContractRecord.start_date < fy_start_date)
        ).all()
    ]
    new_ids: list[str] = [
        c.contract_id
        for c in session.exec(
            select(ContractRecord)
            .where(ContractRecord.start_date >= fy_start_date)
            .where(ContractRecord.start_date <= fy_end_date)
        ).all()
    ]

    def _sum(ids: list[str], p_start: str | None = None, p_end: str | None = None) -> float:
        if not ids:
            return 0.0
        stmt = (
            select(ScheduleRow)
            .where(ScheduleRow.contract_id.in_(ids))
            .where(ScheduleRow.is_adjustment == False)  # noqa: E712
            .where(ScheduleRow.event_type == "recognition")
        )
        if p_start:
            stmt = stmt.where(ScheduleRow.period >= p_start)
        if p_end:
            stmt = stmt.where(ScheduleRow.period <= p_end)
        return sum(r.amount for r in session.exec(stmt).all())

    beginning = round(_sum(prior_ids, p_start=fy_start), 2)
    additions = round(_sum(new_ids), 2)
    all_ids = list(set(prior_ids + new_ids))
    recognized = round(_sum(all_ids, p_start=fy_start, p_end=fy_end), 2)
    ending = round(beginning + additions - recognized, 2)

    return {
        "deferred_revenue": {
            "beginning": beginning,
            "additions": additions,
            "recognized": recognized,
            "ending": ending,
        }
    }


def get_monthly_recognized(session: Session, fiscal_year: int) -> Dict[str, float]:
    """Month-by-month recognized revenue within the FY (for deferred rollforward chart)."""
    fy_start, fy_end = _fy_range(fiscal_year)
    rows = session.exec(
        select(ScheduleRow)
        .where(ScheduleRow.period >= fy_start)
        .where(ScheduleRow.period <= fy_end)
        .where(ScheduleRow.is_adjustment == False)  # noqa: E712
        .where(ScheduleRow.event_type == "recognition")
    ).all()
    monthly: Dict[str, float] = {}
    for r in rows:
        monthly[r.period] = monthly.get(r.period, 0.0) + r.amount
    return {
        f"{fiscal_year}-{m:02d}": round(monthly.get(f"{fiscal_year}-{m:02d}", 0.0), 2)
        for m in range(1, 13)
    }


# ─────────────────────────────────────────────────────────────────────────────
# Section 6 — Remaining Performance Obligations (RPO)
# ─────────────────────────────────────────────────────────────────────────────

def get_rpo(session: Session, as_of_date: date) -> Dict[str, float]:
    """
    RPO bucketed into: Next 12 months / 13–24 months / Beyond 24 months.
    """
    as_of_month = as_of_date.strftime("%Y-%m")
    future_rows = session.exec(
        select(ScheduleRow)
        .where(ScheduleRow.period > as_of_month)
        .where(ScheduleRow.is_adjustment == False)  # noqa: E712
        .where(ScheduleRow.event_type == "recognition")
    ).all()

    buckets: Dict[str, float] = {
        "Next 12 months": 0.0,
        "13\u201324 months": 0.0,
        "Beyond 24 months": 0.0,
    }
    for row in future_rows:
        try:
            year, month = map(int, row.period.split("-"))
            months_out = (year - as_of_date.year) * 12 + (month - as_of_date.month)
        except (ValueError, AttributeError):
            continue
        if months_out <= 12:
            buckets["Next 12 months"] += row.amount
        elif months_out <= 24:
            buckets["13\u201324 months"] += row.amount
        else:
            buckets["Beyond 24 months"] += row.amount

    return {k: round(v, 2) for k, v in buckets.items()}


def get_rpo_by_product(session: Session, as_of_date: date) -> List[Dict[str, Any]]:
    """RPO broken down by product code for the RPO detail schedule."""
    as_of_month = as_of_date.strftime("%Y-%m")
    future_rows = session.exec(
        select(ScheduleRow)
        .where(ScheduleRow.period > as_of_month)
        .where(ScheduleRow.is_adjustment == False)  # noqa: E712
        .where(ScheduleRow.event_type == "recognition")
    ).all()
    products = {p.product_code: p.name for p in session.exec(select(Product)).all()}

    by_product: Dict[str, Dict[str, float]] = {}
    for row in future_rows:
        code = row.product_code or "Unassigned"
        if code not in by_product:
            by_product[code] = {"next_12": 0.0, "13_24": 0.0, "beyond_24": 0.0}
        try:
            year, month = map(int, row.period.split("-"))
            months_out = (year - as_of_date.year) * 12 + (month - as_of_date.month)
        except (ValueError, AttributeError):
            continue
        if months_out <= 12:
            by_product[code]["next_12"] += row.amount
        elif months_out <= 24:
            by_product[code]["13_24"] += row.amount
        else:
            by_product[code]["beyond_24"] += row.amount

    return [
        {
            "product_code": code,
            "product_name": products.get(code, code),
            "next_12": round(v["next_12"], 2),
            "13_24": round(v["13_24"], 2),
            "beyond_24": round(v["beyond_24"], 2),
            "total": round(v["next_12"] + v["13_24"] + v["beyond_24"], 2),
        }
        for code, v in sorted(by_product.items())
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Section 7 — Revenue Waterfall
# ─────────────────────────────────────────────────────────────────────────────

def get_revenue_waterfall(session: Session, fiscal_year: int) -> Dict[str, float]:
    """
    Gross Bookings = transaction_price of contracts starting in FY.
    Recognized     = schedule rows within the FY.
    Deferred       = Bookings − Recognized.
    """
    fy_start_date = date(fiscal_year, 1, 1)
    fy_end_date = date(fiscal_year, 12, 31)
    fy_start, fy_end = _fy_range(fiscal_year)

    fy_contracts = session.exec(
        select(ContractRecord)
        .where(ContractRecord.start_date >= fy_start_date)
        .where(ContractRecord.start_date <= fy_end_date)
    ).all()
    gross_bookings = round(sum(c.transaction_price for c in fy_contracts), 2)
    recognized = round(_recognition_sum(session, fy_start, fy_end), 2)
    deferred = round(gross_bookings - recognized, 2)

    return {
        "gross_bookings": gross_bookings,
        "deferred": deferred,
        "recognized": recognized,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Section 8 — Contract Duration Mix
# ─────────────────────────────────────────────────────────────────────────────

def get_contract_duration_mix(session: Session) -> Dict[str, Any]:
    """
    Categorise contracts by duration:
      Short-term : < 9 months
      Annual     : 9–15 months
      Multi-year : > 15 months
    """
    contracts = session.exec(select(ContractRecord)).all()
    counts = {"Annual": 0, "Multi-year": 0, "Short-term": 0}
    for c in contracts:
        months = (
            (c.end_date.year - c.start_date.year) * 12
            + (c.end_date.month - c.start_date.month)
        )
        if months < 9:
            counts["Short-term"] += 1
        elif months <= 15:
            counts["Annual"] += 1
        else:
            counts["Multi-year"] += 1

    total = sum(counts.values()) or 1
    pct = {k: round(v / total * 100, 1) for k, v in counts.items()}
    return {"counts": counts, "percentages": pct, "total": sum(counts.values())}


# ─────────────────────────────────────────────────────────────────────────────
# Section 13 — Customer Concentration
# ─────────────────────────────────────────────────────────────────────────────

def get_customer_concentration(session: Session, fiscal_year: int) -> Dict[str, Any]:
    """Revenue share by customer tier for the FY."""
    fy_start, fy_end = _fy_range(fiscal_year)
    cust_map = {
        c.contract_id: c.customer
        for c in session.exec(select(ContractRecord)).all()
    }
    rows = session.exec(
        select(ScheduleRow)
        .where(ScheduleRow.period >= fy_start)
        .where(ScheduleRow.period <= fy_end)
        .where(ScheduleRow.is_adjustment == False)  # noqa: E712
        .where(ScheduleRow.event_type == "recognition")
    ).all()

    by_cust: Dict[str, float] = {}
    for r in rows:
        cust = cust_map.get(r.contract_id, "Unknown")
        by_cust[cust] = by_cust.get(cust, 0.0) + r.amount

    total = sum(by_cust.values())
    if total == 0:
        return {
            "top_1_pct": 0.0, "top_5_pct": 0.0, "top_10_pct": 0.0,
            "other_pct": 100.0, "total": 0.0, "customer_count": 0,
        }

    sorted_vals = sorted(by_cust.values(), reverse=True)
    top_1 = round(sum(sorted_vals[:1]) / total * 100, 1)
    top_5 = round(sum(sorted_vals[:5]) / total * 100, 1)
    top_10 = round(sum(sorted_vals[:10]) / total * 100, 1)
    return {
        "top_1_pct": top_1,
        "top_5_pct": top_5,
        "top_10_pct": top_10,
        "other_pct": round(100 - top_10, 1),
        "total": round(total, 2),
        "customer_count": len(by_cust),
    }
