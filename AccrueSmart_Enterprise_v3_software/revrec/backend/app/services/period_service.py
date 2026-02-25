
from app.models.accounting_period import AccountingPeriod
from sqlmodel import Session, select
from datetime import date

def close_period(session: Session, period: str):
    p=session.exec(select(AccountingPeriod).where(AccountingPeriod.period==period)).first()
    if not p:
        raise Exception("Period not found")
    if p.status=="locked":
        raise Exception("Period locked")
    p.status="closed"
    p.closed_at=date.today()
    session.add(p)
    return p

def reopen_period(session: Session, period: str):
    p=session.exec(select(AccountingPeriod).where(AccountingPeriod.period==period)).first()
    if not p:
        raise Exception("Period not found")
    p.status="open"
    p.closed_at=None
    session.add(p)
    return p
