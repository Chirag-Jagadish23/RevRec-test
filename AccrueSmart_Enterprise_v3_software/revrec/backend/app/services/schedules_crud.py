from sqlmodel import Session, select
from ..models.schedules import ScheduleRow

def load_grid(session: Session, contract_id: str):
    rows = session.exec(
        select(ScheduleRow).where(ScheduleRow.contract_id == contract_id).order_by(ScheduleRow.line_no)
    ).all()

    # Convert model → dict for frontend
    return [r.dict() for r in rows]


def save_grid(session: Session, contract_id: str, rows: list):
    # Delete old
    session.query(ScheduleRow).filter(ScheduleRow.contract_id == contract_id).delete()

    # Insert new
    for r in rows:
        session.add(ScheduleRow(
            contract_id=contract_id,
            line_no=int(r["line_no"]),
            period=r["period"],
            amount=float(r["amount"]),
            product_code=r.get("product_code"),
            revrec_code=r.get("revrec_code"),
            source="manual",
        ))

    session.commit()
    return {"ok": True}
