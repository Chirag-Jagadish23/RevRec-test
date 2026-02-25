from sqlmodel import Session, select
from sqlalchemy import delete
from ..models.models import ScheduleRow, Product, RevRecCode


def clear_schedule(contract_id: str, session: Session):
    """Delete all schedule rows for a given contract."""
    session.exec(
        delete(ScheduleRow).where(ScheduleRow.contract_id == contract_id)
    )
    session.commit()


def save_schedule_rows(contract_id: str, schedule: list, session: Session):
    """Replace the schedule for a contract with new rows."""
    clear_schedule(contract_id, session)

    for row in schedule:
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
