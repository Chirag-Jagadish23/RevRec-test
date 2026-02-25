# backend/app/routers/forecast.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Literal, Optional

from ..auth import require
from ..services.forecast import forecast_revenue

router = APIRouter(prefix="/forecast", tags=["forecast"])


class ForecastIn(BaseModel):
    history: Dict[str, float]  # {"2024-01": 10000, ...}
    horizon: int = Field(12, ge=1, le=60)
    method: Literal["exp_smooth", "seasonal_ma"] = "exp_smooth"
    alpha: Optional[float] = Field(0.35, ge=0.01, le=0.99)
    season: Optional[int] = Field(12, ge=2, le=24)


@router.post("/revenue")
@require(perms=["revrec.export"])  # or "forecast.run" if you add it later
def forecast(inp: ForecastIn):
    try:
        kwargs = {}
        if inp.method == "exp_smooth":
            kwargs["alpha"] = inp.alpha
        else:
            kwargs["season"] = inp.season

        return forecast_revenue(
            history=inp.history,
            horizon=inp.horizon,
            method=inp.method,
            **kwargs,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
