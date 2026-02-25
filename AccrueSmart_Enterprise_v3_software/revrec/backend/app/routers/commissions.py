from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from ..auth import require
from ..services.commissions import commission_amort_schedule

router = APIRouter(prefix="/commissions", tags=["commissions"])

class CommissionIn(BaseModel):
    contract_id: str
    contract_name: str
    commission_amount: float = Field(..., ge=0)
    start_date: str
    amortization_months: int = Field(..., ge=1)

@router.post("/asc34040/schedule")
@require(perms=["reports.memo"])
def asc34040(inp: CommissionIn):
    try:
        return commission_amort_schedule(**inp.model_dump())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
