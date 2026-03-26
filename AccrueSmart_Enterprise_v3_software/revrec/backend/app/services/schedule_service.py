from sqlmodel import Session, select
from sqlalchemy import delete
from ..models.models import ScheduleRow, Product, RevRecCode


def clear_schedule(
    contract_id: str,
    session: Session,
    preserve_adjustments: bool = False,
    preserve_before_period: str = None,
) -> int:
    """Delete schedule rows for a given contract.

    Args:
        preserve_adjustments: When True, rows with is_adjustment=True are kept.
        preserve_before_period: YYYY-MM string. When set, rows with period < this
            value are also kept (prospective treatment — don't restate history).
    Returns:
        Count of rows preserved (adjustments + historical rows kept).
    """
    # Count rows we'll keep so callers can surface warnings
    keep_q = select(ScheduleRow).where(ScheduleRow.contract_id == contract_id)
    if preserve_adjustments:
        keep_q = keep_q.where(ScheduleRow.is_adjustment == True)
    preserved_count = len(session.exec(keep_q).all()) if preserve_adjustments else 0

    # Build the DELETE — remove non-adjustment rows, optionally only from effective_period onward
    stmt = delete(ScheduleRow).where(
        ScheduleRow.contract_id == contract_id,
        ScheduleRow.is_adjustment == False,
    )
    if preserve_before_period:
        # Only delete rows in periods >= effective_period; keep older rows intact
        stmt = stmt.where(ScheduleRow.period >= preserve_before_period)

    session.exec(stmt)
    session.commit()
    return preserved_count


def save_schedule_rows(
    contract_id: str,
    schedule: list,
    session: Session,
    prospective_from: str = None,
) -> dict:
    """Replace the allocated schedule for a contract.

    Args:
        prospective_from: YYYY-MM string. When set, only rows for periods >=
            this value are inserted (prospective treatment). Historical rows
            already in the DB are left untouched.

    Returns:
        dict with 'preserved_adjustments' count.
    """
    preserved_count = clear_schedule(
        contract_id,
        session,
        preserve_adjustments=True,
        preserve_before_period=prospective_from,
    )

    rows_to_save = schedule
    if prospective_from:
        rows_to_save = [r for r in schedule if r["period"] >= prospective_from]

    for row in rows_to_save:
        session.add(
            ScheduleRow(
                contract_id=contract_id,
                product_code=row.get("product_code"),
                period=row["period"],
                amount=row["amount"],
                source=row.get("source", "allocated"),
            )
        )

    session.commit()
    return {"preserved_adjustments": preserved_count}


def post_catchup_row(
    contract_id: str,
    schedule: list,
    effective_date: str,
    session: Session,
) -> float:
    """Compute and post a cumulative catch-up adjustment row.

    Compares what the new schedule would have recognised in periods before
    effective_period against what was actually recognised (existing non-adjustment
    rows for those periods).  Posts the delta as a single is_adjustment row in
    the effective period.

    Returns the catch-up amount (0.0 if no delta).
    """
    effective_period = effective_date[:7]  # "YYYY-MM"

    # Sum of new schedule rows for periods before effective_period
    new_before = sum(
        r["amount"] for r in schedule if r["period"] < effective_period
    )

    # Sum of existing non-adjustment rows for periods before effective_period
    old_rows = session.exec(
        select(ScheduleRow).where(
            ScheduleRow.contract_id == contract_id,
            ScheduleRow.period < effective_period,
            ScheduleRow.is_adjustment == False,
        )
    ).all()
    old_before = sum(r.amount for r in old_rows)

    catchup = round(new_before - old_before, 2)

    if abs(catchup) > 0.00:
        session.add(
            ScheduleRow(
                contract_id=contract_id,
                period=effective_period,
                amount=catchup,
                source="cumulative_catch_up",
                event_type="cumulative_catch_up",
                is_adjustment=True,
                notes=(
                    f"Cumulative catch-up for contract modification effective {effective_date}. "
                    f"New terms would have recognised ${new_before:,.2f} vs actual ${old_before:,.2f} "
                    f"in prior periods."
                ),
                effective_date=effective_date,
            )
        )
        session.commit()

    return catchup


def load_schedule(contract_id: str, session: Session):
    """
    Return schedule rows enriched with product + revrec metadata
    so frontend grid can show Product Name / SSP / Rule.
    """
    rows = session.exec(
        select(ScheduleRow).where(ScheduleRow.contract_id == contract_id)
    ).all()

    enriched = []
    for i, r in enumerate(rows, start=1):
        product = session.get(Product, r.product_code) if r.product_code else None
        revrec = session.get(RevRecCode, product.revrec_code) if product and product.revrec_code else None

        enriched.append({
            "line_no": i,
            "period": r.period,
            "amount": r.amount,
            "product_code": r.product_code,
            "product_name": product.name if product else None,
            "ssp": product.ssp if product else None,
            "revrec_code": product.revrec_code if product else None,
            "rule_type": revrec.rule_type if revrec else None,
            "source": r.source,
        })

    # nice sort: product_code, then period
    enriched.sort(key=lambda x: ((x.get("product_code") or ""), x["period"]))
    for idx, row in enumerate(enriched, start=1):
        row["line_no"] = idx

    return enriched
