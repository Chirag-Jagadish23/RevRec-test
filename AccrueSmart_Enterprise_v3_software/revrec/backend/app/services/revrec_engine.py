from datetime import date
from sqlmodel import Session, select
from ..models.models import Product, Milestone


def generate_month_list(start: date, end: date):
    months = []
    y, m = start.year, start.month
    while True:
        months.append(f"{y}-{m:02d}")
        if y == end.year and m == end.month:
            break
        m += 1
        if m == 13:
            m = 1
            y += 1
    return months


def build_schedule(contract, allocations, session: Session):
    periods = generate_month_list(contract.start_date, contract.end_date)
    schedule_rows = []

    for alloc in allocations:
        product = session.get(Product, alloc["product_code"])

        # --- MILESTONE rule: one row per locked milestone ---
        if alloc["rule_type"] == "milestone":
            locked = session.exec(
                select(Milestone).where(
                    Milestone.contract_id == contract.contract_id,
                    Milestone.product_code == alloc["product_code"],
                    Milestone.is_locked == True,
                )
            ).all()

            for m in locked:
                # Derive YYYY-MM period from the milestone date
                period = m.milestone_date[:7]
                schedule_rows.append({
                    "period": period,
                    "product_code": alloc["product_code"],
                    "product_name": product.name if product else None,
                    "ssp": product.ssp if product else None,
                    "revrec_code": alloc["revrec_code"],
                    "rule_type": "milestone",
                    "allocated_total": alloc["allocated_total"],
                    "monthly_amount": 0,
                    "amount": m.amount,
                    "source": "milestone",
                })
            continue  # skip the period loop for milestone lines

        # --- STRAIGHT_LINE and IMMEDIATE rules ---
        last_idx = len(periods) - 1
        for i, p in enumerate(periods):
            amount = (
                alloc["allocated_total"] if alloc["rule_type"] == "immediate" and i == 0
                else alloc.get("last_row_amount", alloc["monthly_amount"]) if alloc["rule_type"] == "straight_line" and i == last_idx
                else alloc["monthly_amount"] if alloc["rule_type"] == "straight_line"
                else 0
            )

            if amount == 0:
                continue  # skip zero rows

            schedule_rows.append({
                "period": p,
                "product_code": alloc["product_code"],
                "product_name": product.name if product else None,
                "ssp": product.ssp if product else None,
                "revrec_code": alloc["revrec_code"],
                "rule_type": alloc["rule_type"],
                "allocated_total": alloc["allocated_total"],
                "monthly_amount": alloc["monthly_amount"],
                "amount": amount,
                "source": alloc["rule_type"],
            })

    return schedule_rows
