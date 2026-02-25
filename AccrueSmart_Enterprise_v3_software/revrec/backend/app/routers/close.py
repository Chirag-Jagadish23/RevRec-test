# backend/app/routers/close.py
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session

from ..db import get_session
from ..services.close_orchestrator import build_close_dashboard, generate_close_package

try:
    from ..auth import require
except Exception:
    # Dev-safe fallback
    def require(perms=None):
        def _decorator(fn):
            return fn
        return _decorator


router = APIRouter(prefix="/close", tags=["close"])


class ClosePackageGenerateIn(BaseModel):
    period_key: str = Field(..., min_length=1, description="Example: 2026-01")
    entity_id: Optional[str] = "US_PARENT"


@router.get("/dashboard")
@require(perms=["reports.memo"])
def close_dashboard(
    period_key: str = Query(..., description="Example: 2026-01"),
    entity_id: str = Query("US_PARENT"),
    session: Session = Depends(get_session),
):
    try:
        return build_close_dashboard(session=session, period_key=period_key, entity_id=entity_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/package/generate")
@require(perms=["reports.memo"])
def close_package_generate(payload: ClosePackageGenerateIn, session: Session = Depends(get_session)):
    try:
        data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
        return generate_close_package(
            session=session,
            period_key=data["period_key"],
            entity_id=data.get("entity_id") or "US_PARENT",
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
