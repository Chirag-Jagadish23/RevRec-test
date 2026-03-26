# backend/app/routers/close.py
from __future__ import annotations

from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..db import get_session
from ..models.models import CloseTaskOverride
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


class TaskOverrideIn(BaseModel):
    task_id: str
    period_key: str
    entity_id: Optional[str] = "US_PARENT"
    status: str = Field(..., pattern="^(in_progress|blocked|pending)$")
    notes: Optional[str] = None


@router.patch("/tasks/override")
def override_task_status(payload: TaskOverrideIn, session: Session = Depends(get_session)):
    """Manually set a close task to in_progress, blocked, or pending. 'done' is always auto-detected."""
    data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()

    # Upsert: find existing override for this task+period+entity
    existing = session.exec(
        select(CloseTaskOverride).where(
            CloseTaskOverride.task_id == data["task_id"],
            CloseTaskOverride.period_key == data["period_key"],
            CloseTaskOverride.entity_id == data["entity_id"],
        )
    ).first()

    if existing:
        existing.status = data["status"]
        existing.notes = data.get("notes")
        existing.updated_at = datetime.utcnow().isoformat()
    else:
        session.add(CloseTaskOverride(
            task_id=data["task_id"],
            period_key=data["period_key"],
            entity_id=data["entity_id"],
            status=data["status"],
            notes=data.get("notes"),
            updated_at=datetime.utcnow().isoformat(),
        ))

    session.commit()
    return {"status": "ok", "task_id": data["task_id"], "new_status": data["status"]}
