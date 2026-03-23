from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..db import get_session
from ..models.models import Milestone, ContractRecord

router = APIRouter(prefix="/milestones", tags=["milestones"])


# ---------------- LIST milestones for a contract ----------------
@router.get("/{contract_id}")
def list_milestones(contract_id: str, session: Session = Depends(get_session)):
    rows = session.exec(
        select(Milestone).where(Milestone.contract_id == contract_id)
    ).all()
    return rows


# ---------------- CREATE milestone ----------------
@router.post("")
def create_milestone(payload: dict, session: Session = Depends(get_session)):
    contract_id = payload.get("contract_id")
    product_code = payload.get("product_code")
    milestone_date = payload.get("milestone_date")
    amount = payload.get("amount")
    description = payload.get("description")

    if not contract_id:
        raise HTTPException(400, "Missing contract_id")
    if not product_code:
        raise HTTPException(400, "Missing product_code")
    if not milestone_date:
        raise HTTPException(400, "Missing milestone_date")
    if amount is None:
        raise HTTPException(400, "Missing amount")

    contract = session.get(ContractRecord, contract_id)
    if not contract:
        raise HTTPException(404, f"Contract {contract_id} not found")

    milestone = Milestone(
        contract_id=contract_id,
        product_code=product_code,
        milestone_date=milestone_date,
        amount=float(amount),
        description=description or "",
        is_locked=False,
    )
    session.add(milestone)
    session.commit()
    session.refresh(milestone)
    return milestone


# ---------------- LOCK milestone ----------------
@router.patch("/{milestone_id}/lock")
def lock_milestone(milestone_id: int, session: Session = Depends(get_session)):
    milestone = session.get(Milestone, milestone_id)
    if not milestone:
        raise HTTPException(404, "Milestone not found")
    if milestone.is_locked:
        raise HTTPException(400, "Milestone is already locked")

    milestone.is_locked = True
    milestone.locked_at = datetime.utcnow().isoformat()
    session.add(milestone)
    session.commit()
    session.refresh(milestone)
    return milestone


# ---------------- UNLOCK milestone ----------------
@router.patch("/{milestone_id}/unlock")
def unlock_milestone(milestone_id: int, session: Session = Depends(get_session)):
    milestone = session.get(Milestone, milestone_id)
    if not milestone:
        raise HTTPException(404, "Milestone not found")

    milestone.is_locked = False
    milestone.locked_at = None
    session.add(milestone)
    session.commit()
    session.refresh(milestone)
    return milestone


# ---------------- DELETE milestone ----------------
@router.delete("/{milestone_id}")
def delete_milestone(milestone_id: int, session: Session = Depends(get_session)):
    milestone = session.get(Milestone, milestone_id)
    if not milestone:
        raise HTTPException(404, "Milestone not found")
    if milestone.is_locked:
        raise HTTPException(400, "Cannot delete a locked milestone — unlock it first")

    session.delete(milestone)
    session.commit()
    return {"status": "deleted", "id": milestone_id}
