from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from ..auth import require
from ..services.intercompany import eliminate_intercompany

router = APIRouter(prefix="/intercompany", tags=["intercompany"])

class ICRow(BaseModel):
    from_entity: str
    to_entity: str
    account: str
    amount: float

class IntercompanyIn(BaseModel):
    balances: List[ICRow]

@router.post("/eliminate")
@require(perms=["reports.memo"])
def eliminate(inp: IntercompanyIn):
    try:
        return eliminate_intercompany([r.model_dump() for r in inp.balances])
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
