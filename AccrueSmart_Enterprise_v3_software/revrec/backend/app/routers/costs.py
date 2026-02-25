# backend/app/routers/costs.py
from __future__ import annotations
from datetime import date
from typing import List, Optional, Literal, Dict, Any, Annotated
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, confloat
from ..auth import require
from ..services.costs import amortize_cost

router = APIRouter(prefix="/costs", tags=["costs"])

Method = Literal["straight_line", "percent_complete", "custom_curve"]

class CostsIn(BaseModel):
    total: float = Field(..., example=2400.0, ge=0)
    months: int = Field(..., gt=0, example=24)
    start: str = Field(..., example="2025-01-01")
    method: Method = Field("straight_line")
    percent_complete: Optional[Annotated[List[float], Field(min_length=1)]] = None
    curve: Optional[Annotated[List[float], Field(min_length=1)]] = None

@router.post("/amortize")
#@require(perms=["costs.run"])  # add this perm in schema below
def amortize(body: CostsIn) -> Dict[str, Any]:
    try:
        res = amortize_cost(
            total=float(body.total),
            months=int(body.months),
            start=date.fromisoformat(body.start),
            method=body.method,
            percent_complete=body.percent_complete,
            curve=body.curve,
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
