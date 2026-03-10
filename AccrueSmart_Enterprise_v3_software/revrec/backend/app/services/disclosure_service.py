"""
disclosure_service.py — Real DB query logic for ASC 606 disclosure pack.

Three sections:
  1. Revenue disaggregation by product (current FY vs prior FY)
  2. Deferred revenue rollforward (beginning / additions / recognized / ending)
  3. Remaining Performance Obligations (future buckets as of a given date)

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


def _recognition_rows(session: Session) -> list[ScheduleRow]:
    """All non-adjustment recognition rows."""
    return session.exec(
        select(ScheduleRow)
        .where(ScheduleRow.is_adjustment == False)  # noqa: E712
        .where(ScheduleRow.event_type == "recognition")
    ).all()


# ─────────────────────────────────────────────────────────────────────────────
# Section 1 — Revenue Disaggregation
# ─────────────────────────────────────────────────────────────────────────────

def get_revenue_disaggregation(
    session: Session, fiscal_year: int
) -> List[Dict[str, Any]]:
    """
    Aggregate recognized revenue by product_code for the given FY
    and the prior FY, for side-by-side comparison.

    Returns a list of dicts sorted by product_code:
      {product_code, product_name, current, prior, variance_pct}
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
        variance = ((curr - pri) / pri * 100) if pri else 0.0
        result.append(
            {
                "product_code": code,
                "product_name": products.get(code, code),
                "current": round(curr, 2),
                "prior": round(pri, 2),
                "variance_pct": round(variance, 1),
            }
        )
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Section 2 — Deferred Revenue Rollforward
# ─────────────────────────────────────────────────────────────────────────────

def get_contract_balances_rollforward(
    session: Session, fiscal_year: int
) -> Dict[str, Any]:
    """
    Deferred revenue rollforward for the fiscal year.

    Methodology (simplified, cash-basis surrogate):
      Beginning balance  = total future recognition for contracts that started
                           BEFORE the FY, measured as all their schedule_rows
                           in periods >= FY start (i.e. unrecognized at FY open).
      Additions          = total scheduled recognition for contracts that started
                           DURING the FY (all their scheduled rows).
      Recognized         = sum of schedule_rows whose period falls within the FY.
      Ending balance     = Beginning + Additions − Recognized.

    Note: This is an ASC-606-aligned approximation. A full billing system would
    track cash received separately; here we use allocated schedule rows as a proxy.
    """
    fy_start, fy_end = _fy_range(fiscal_year)
    fy_start_date = date(fiscal_year, 1, 1)
    fy_end_date = date(fiscal_year, 12, 31)

    # Contracts that started BEFORE this FY
    prior_ids: set[str] = {
        c.contract_id
        for c in session.exec(
            select(ContractRecord).where(ContractRecord.start_date < fy_start_date)
        ).all()
    }

    # Contracts that started DURING this FY
    new_ids: set[str] = {
        c.contract_id
        for c in session.exec(
            select(ContractRecord)
            .where(ContractRecord.start_date >= fy_start_date)
            .where(ContractRecord.start_date <= fy_end_date)
        ).all()
    }

    def _sum(contract_ids: set[str], period_start: str | None = None, period_end: str | None = None) -> float:
        if not contract_ids:
            return 0.0
        stmt = (
            select(ScheduleRow)
            .where(ScheduleRow.contract_id.in_(list(contract_ids)))
            .where(ScheduleRow.is_adjustment == False)  # noqa: E712
            .where(ScheduleRow.event_type == "recognition")
        )
        if period_start:
            stmt = stmt.where(ScheduleRow.period >= period_start)
        if period_end:
            stmt = stmt.where(ScheduleRow.period <= period_end)
        return sum(r.amount for r in session.exec(stmt).all())

    # Beginning balance: prior-contract rows scheduled for the FY onward
    beginning = round(_sum(prior_ids, period_start=fy_start), 2)

    # Additions: all rows for new contracts (their full allocated schedule)
    additions = round(_sum(new_ids), 2)

    # Recognized in FY: all contracts, rows within the FY period range
    all_ids = prior_ids | new_ids
    recognized = round(_sum(all_ids, period_start=fy_start, period_end=fy_end), 2)

    ending = round(beginning + additions - recognized, 2)

    return {
        "deferred_revenue": {
            "beginning": beginning,
            "additions": additions,
            "recognized": recognized,
            "ending": ending,
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
# Section 3 — Remaining Performance Obligations (RPO)
# ─────────────────────────────────────────────────────────────────────────────

def get_rpo(session: Session, as_of_date: date) -> Dict[str, float]:
    """
    Remaining Performance Obligations as of as_of_date.

    Future = schedule_rows whose period > as_of_date's YYYY-MM.
    Buckets:
      - Next 12 months  (months_out 1–12)
      - 13–24 months    (months_out 13–24)
      - Beyond 24 months
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
