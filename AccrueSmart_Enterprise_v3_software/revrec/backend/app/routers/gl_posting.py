from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from ..db import get_session
from ..services.gl_posting import (
    ensure_default_posting_rules,
    upsert_coa_mapping,
    set_period_lock,
    preview_posting,
    post_batch,
    unpost_batch,
    repost_batch,
    get_journal_batch_detail,
)

try:
    from ..auth import require
except Exception:
    def require(perms=None):
        def _decorator(fn):
            return fn
        return _decorator


router = APIRouter(prefix="/gl-posting", tags=["gl-posting"])


class SeedRulesIn(BaseModel):
    pass


class COAMappingIn(BaseModel):
    entity_code: str = "US_PARENT"
    logical_key: str
    account_code: str
    account_name: str = ""
    geography: str = "GLOBAL"
    product_family: str = "DEFAULT"


class PeriodLockIn(BaseModel):
    entity_code: str = "US_PARENT"
    period_key: str = "2026-01"
    is_locked: bool = True
    actor: str = "controller@demo.com"


class PreviewPostingIn(BaseModel):
    source_type: str = Field(..., description="revrec | lease | depreciation | commission")
    actor: str = "system"
    source_payload: Dict[str, Any]


class BatchActionIn(BaseModel):
    batch_id: str
    actor: str = "system"


@router.get("/health")
@require(perms=["reports.memo"])
def gl_posting_health():
    return {"ok": True, "module": "gl-posting"}


@router.post("/rules/seed")
@require(perms=["reports.memo"])
def seed_rules(session: Session = Depends(get_session)):
    try:
        return ensure_default_posting_rules(session)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/coa/upsert")
@require(perms=["reports.memo"])
def coa_upsert(payload: COAMappingIn, session: Session = Depends(get_session)):
    try:
        return {
            "status": "ok",
            "mapping": upsert_coa_mapping(
                session=session,
                entity_code=payload.entity_code,
                logical_key=payload.logical_key,
                account_code=payload.account_code,
                account_name=payload.account_name,
                geography=payload.geography,
                product_family=payload.product_family,
            )
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/period-lock")
@require(perms=["reports.memo"])
def period_lock(payload: PeriodLockIn, session: Session = Depends(get_session)):
    try:
        return set_period_lock(
            session,
            entity_code=payload.entity_code,
            period_key=payload.period_key,
            is_locked=payload.is_locked,
            actor=payload.actor,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/preview")
@require(perms=["reports.memo"])
def preview(payload: PreviewPostingIn, session: Session = Depends(get_session)):
    try:
        return preview_posting(
            session=session,
            source_type=payload.source_type,
            source_payload=payload.source_payload,
            actor=payload.actor,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/post")
@require(perms=["reports.memo"])
def post(payload: BatchActionIn, session: Session = Depends(get_session)):
    try:
        return post_batch(session, batch_id=payload.batch_id, actor=payload.actor)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/unpost")
@require(perms=["reports.memo"])
def unpost(payload: BatchActionIn, session: Session = Depends(get_session)):
    try:
        return unpost_batch(session, batch_id=payload.batch_id, actor=payload.actor)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/repost")
@require(perms=["reports.memo"])
def repost(payload: BatchActionIn, session: Session = Depends(get_session)):
    try:
        return repost_batch(session, batch_id=payload.batch_id, actor=payload.actor)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/batch/{batch_id}")
@require(perms=["reports.memo"])
def get_batch(batch_id: str, session: Session = Depends(get_session)):
    try:
        return get_journal_batch_detail(session, batch_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
