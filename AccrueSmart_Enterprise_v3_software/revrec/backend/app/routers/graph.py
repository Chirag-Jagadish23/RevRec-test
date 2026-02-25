# backend/app/routers/graph.py
from __future__ import annotations

from typing import Any, Dict, Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from ..db import get_session
from ..services.accounting_graph import (
    upsert_node,
    upsert_edge,
    record_causal_event,
    trace_entity,
    explain_impact,
    link_accounting_chain,
    trace_change_impact,
    why_metric_changed,
)

try:
    from ..auth import require
except Exception:
    # Dev-safe fallback if auth isn't wired yet
    def require(perms=None):
        def _decorator(fn):
            return fn
        return _decorator


router = APIRouter(prefix="/graph", tags=["graph"])


# ----------------------------
# Pydantic request models
# ----------------------------
class UpsertNodeIn(BaseModel):
    node_type: str = Field(..., min_length=1)
    ref_id: str = Field(..., min_length=1)
    label: Optional[str] = ""
    attrs: Dict[str, Any] = Field(default_factory=dict)


class UpsertEdgeIn(BaseModel):
    from_node_type: str
    from_ref_id: str
    to_node_type: str
    to_ref_id: str
    edge_type: str
    attrs: Dict[str, Any] = Field(default_factory=dict)
    from_label: Optional[str] = ""
    to_label: Optional[str] = ""


class CausalEventIn(BaseModel):
    root_node_type: str
    root_ref_id: str
    event_type: str
    before: Dict[str, Any] = Field(default_factory=dict)
    after: Dict[str, Any] = Field(default_factory=dict)
    impact: Dict[str, Any] = Field(default_factory=dict)
    actor: Optional[str] = "system"
    source: Optional[str] = "app"
    event_id: Optional[str] = None


class ExplainImpactIn(BaseModel):
    root_type: str
    root_id: str
    question: str
    max_hops: Optional[int] = 2


# NEW: enterprise graph request models
class ChainNodeIn(BaseModel):
    node_type: str
    ref_id: str
    label: Optional[str] = ""
    attrs: Optional[Dict[str, Any]] = Field(default_factory=dict)


class LinkChainIn(BaseModel):
    chain: List[ChainNodeIn]
    edge_type: Optional[str] = "related_to"


class TraceChangeImpactIn(BaseModel):
    root_type: str
    root_id: str
    change_summary: Dict[str, Any]
    max_hops: Optional[int] = 3


class WhyMetricIn(BaseModel):
    metric_name: str
    period_key: str
    candidate_roots: List[Dict[str, str]]


# ----------------------------
# Routes
# ----------------------------
@router.get("/health")
@require(perms=["reports.memo"])
def graph_health():
    return {"ok": True, "module": "graph"}


@router.post("/upsert-node")
@require(perms=["reports.memo"])
def graph_upsert_node(payload: UpsertNodeIn, session: Session = Depends(get_session)):
    try:
        data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
        out = upsert_node(
            session=session,
            node_type=data["node_type"],
            ref_id=data["ref_id"],
            label=data.get("label") or "",
            attrs=data.get("attrs") or {},
        )
        return {"status": "ok", "node": out}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/upsert-edge")
@require(perms=["reports.memo"])
def graph_upsert_edge(payload: UpsertEdgeIn, session: Session = Depends(get_session)):
    try:
        data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
        out = upsert_edge(
            session=session,
            from_node_type=data["from_node_type"],
            from_ref_id=data["from_ref_id"],
            to_node_type=data["to_node_type"],
            to_ref_id=data["to_ref_id"],
            edge_type=data["edge_type"],
            attrs=data.get("attrs") or {},
            from_label=data.get("from_label") or "",
            to_label=data.get("to_label") or "",
        )
        return {"status": "ok", "edge": out}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/causal-event")
@require(perms=["reports.memo"])
def graph_causal_event(payload: CausalEventIn, session: Session = Depends(get_session)):
    try:
        data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
        out = record_causal_event(
            session=session,
            root_node_type=data["root_node_type"],
            root_ref_id=data["root_ref_id"],
            event_type=data["event_type"],
            before=data.get("before") or {},
            after=data.get("after") or {},
            impact=data.get("impact") or {},
            actor=data.get("actor") or "system",
            source=data.get("source") or "app",
            event_id=data.get("event_id"),
        )
        return {"status": "ok", "event": out}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/trace/{node_type}/{ref_id}")
@require(perms=["reports.memo"])
def graph_trace(
    node_type: str,
    ref_id: str,
    max_hops: int = 2,
    session: Session = Depends(get_session),
):
    try:
        result = trace_entity(
            session=session,
            node_type=node_type,
            ref_id=ref_id,
            max_hops=max_hops,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/explain-impact")
@require(perms=["reports.memo"])
def graph_explain(payload: ExplainImpactIn, session: Session = Depends(get_session)):
    try:
        data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
        result = explain_impact(
            session=session,
            root_type=data["root_type"],
            root_id=data["root_id"],
            question=data["question"],
            max_hops=int(data.get("max_hops") or 2),
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ----------------------------
# NEW: enterprise graph routes
# ----------------------------
@router.post("/link-chain")
@require(perms=["reports.memo"])
def graph_link_chain(payload: LinkChainIn, session: Session = Depends(get_session)):
    try:
        data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
        # Convert Pydantic models to plain dicts safely
        chain = [
            n.model_dump() if hasattr(n, "model_dump") else n.dict()
            for n in data["chain"]
        ] if data.get("chain") else []

        return link_accounting_chain(
            session=session,
            chain=chain,
            edge_type=data.get("edge_type") or "related_to",
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/trace-change-impact")
@require(perms=["reports.memo"])
def graph_trace_change(payload: TraceChangeImpactIn, session: Session = Depends(get_session)):
    try:
        data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
        return trace_change_impact(
            session=session,
            root_type=data["root_type"],
            root_id=data["root_id"],
            change_summary=data["change_summary"],
            max_hops=int(data.get("max_hops") or 3),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/why-metric")
@require(perms=["reports.memo"])
def graph_why_metric(payload: WhyMetricIn, session: Session = Depends(get_session)):
    try:
        data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
        return why_metric_changed(
            session=session,
            metric_name=data["metric_name"],
            period_key=data["period_key"],
            candidate_roots=data["candidate_roots"],
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
