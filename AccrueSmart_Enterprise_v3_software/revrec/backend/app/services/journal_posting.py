
from app.models.journal import JournalBatch, JournalLine
from app.models.accounting_period import AccountingPeriod
from sqlmodel import Session, select
from datetime import datetime

def post_journal(session: Session, period: str, lines: list, source="revrec"):
    p=session.exec(select(AccountingPeriod).where(AccountingPeriod.period==period)).first()
    if not p or p.status!="open":
        raise Exception("Period closed or missing")

    batch=JournalBatch(period=period,created_at=datetime.utcnow(),source=source)
    session.add(batch)
    session.commit()
    session.refresh(batch)

    for l in lines:
        jl=JournalLine(batch_id=batch.id,**l)
        session.add(jl)

    return batch
