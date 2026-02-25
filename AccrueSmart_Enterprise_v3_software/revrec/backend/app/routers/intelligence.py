# backend/app/routers/intelligence.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services.scenario_mode import run_scenario
from ..services.audit_ready import build_audit_ready_package
from ..services.policy_engine import parse_policy_text, evaluate_policy_rules

try:
    from ..auth import require
except Exception:
    def require(perms=None):
        def _decorator(fn):
            return fn
        return _decorator


router = APIRouter(prefix="/intelligence", tags=["intelligence"])


# ----------------------------
# Models
# ----------------------------
class ScenarioChangeIn(BaseModel):
    contract_term_months: Optional[int] = None
    billing_frequency: Optional[str] = None
    payment_terms: Optional[str] = None
    currency: Optional[str] = None
    nonstandard_terms: Optional[str] = None

    lease_discount_rate_annual: Optional[float] = None
    fixed_asset_useful_life_months: Optional[int] = None
    fixed_asset_cost: Optional[float] = None
    fixed_asset_salvage_value: Optional[float] = None

    # line-level edits
    line_changes: List[Dict[str, Any]] = Field(default_factory=list)


class ScenarioRequestIn(BaseModel):
    base_payload: Dict[str, Any]
    changes: ScenarioChangeIn


class AuditReadyRequestIn(BaseModel):
    period: str
    company: str
    modules: Dict[str, Any] = Field(default_factory=dict)
    source_documents: List[Dict[str, Any]] = Field(default_factory=list)


class PolicyParseRequestIn(BaseModel):
    policy_lines: List[str] = Field(default_factory=list)


class PolicyEvalRequestIn(BaseModel):
    rules: List[Dict[str, Any]] = Field(default_factory=list)
    deal_payload: Dict[str, Any]


# ----------------------------
# Routes
# ----------------------------
@router.get("/health")
@require(perms=["reports.memo"])
def health():
    return {"ok": True, "module": "intelligence"}


@router.post("/scenario-mode")
@require(perms=["reports.memo"])
def scenario_mode(payload: ScenarioRequestIn):
    try:
        data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
        out = run_scenario(
            base_payload=data["base_payload"],
            changes=data["changes"],
        )
        return out
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Scenario mode failed: {e}")


@router.post("/audit-ready-package")
@require(perms=["reports.memo"])
def audit_ready(payload: AuditReadyRequestIn):
    try:
        data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
        return build_audit_ready_package(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Audit-ready package generation failed: {e}")


@router.post("/policy/parse")
@require(perms=["reports.memo"])
def policy_parse(payload: PolicyParseRequestIn):
    try:
        data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
        rules = parse_policy_text(data.get("policy_lines") or [])
        return {
            "status": "ok",
            "count": len(rules),
            "rules": rules,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Policy parse failed: {e}")


@router.post("/policy/evaluate")
@require(perms=["reports.memo"])
def policy_evaluate(payload: PolicyEvalRequestIn):
    try:
        data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
        return {
            "status": "ok",
            **evaluate_policy_rules(
                rules=data.get("rules") or [],
                deal_payload=data.get("deal_payload") or {},
            )
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Policy evaluation failed: {e}")
