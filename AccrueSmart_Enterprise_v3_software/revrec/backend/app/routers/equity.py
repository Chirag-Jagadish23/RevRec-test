from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from ..auth import require
from ..services.equity import stock_comp_schedule

router = APIRouter(prefix="/equity", tags=["equity"])

class EquityGrantIn(BaseModel):
    grant_id: str
    employee_name: str
    grant_date: str
    total_fair_value: float = Field(..., ge=0)
    vest_months: int = Field(..., ge=1)
    cliff_months: int = Field(12, ge=0)
    method: str = "straight_line"

@router.post("/asc718/schedule")
@require(perms=["reports.memo"])
def asc718_schedule(inp: EquityGrantIn):
    try:
        return stock_comp_schedule(**inp.model_dump())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
