# backend/app/routers/deal_desk.py
from __future__ import annotations

from typing import Optional, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..auth import require
from ..services.deal_desk import review_deal  # <- make sure this matches your service file name

router = APIRouter(prefix="/deal-desk", tags=["deal-desk"])


class DealLineIn(BaseModel):
    sku: str = "SKU-1"
    description: str = ""
    quantity: float = Field(1, ge=0)
    unit_price: float = Field(0, ge=0)
    discount_pct: float = Field(0, ge=0, le=100)
    term_months: int = Field(12, ge=1, le=120)
    type: str = "subscription"  # subscription | services | usage | support


class ApprovalPolicyIn(BaseModel):
    max_standard_discount_pct: float = Field(20, ge=0, le=100)
    max_auto_approve_term_months: int = Field(12, ge=1, le=120)
    require_legal_for_nonstandard_terms: bool = True
    require_finance_for_services_discount: bool = True


class DealDeskReviewIn(BaseModel):
    customer_name: str = "Demo Customer"
    quote_name: Optional[str] = "Q-1001"
    contract_term_months: int = Field(12, ge=1, le=120)
    billing_frequency: str = "annual"  # monthly | quarterly | annual
    payment_terms: str = "Net 30"
    currency: str = "USD"

    nonstandard_terms: Optional[str] = ""
    notes: Optional[str] = ""

    lines: List[DealLineIn]
    approval_policy: Optional[ApprovalPolicyIn] = ApprovalPolicyIn()


@router.get("/health")
@require(perms=["reports.memo"])
def deal_desk_health():
    return {"status": "ok", "router": "deal-desk"}


@router.post("/review")
@require(perms=["reports.memo"])
def review(payload: DealDeskReviewIn):
    try:
        data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
        return review_deal(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
