# backend/app/services/accounting_graph.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
import json
import uuid

from sqlmodel import Session, select
from sqlalchemy import or_

from ..models.accounting_graph import GraphNode, GraphEdge, CausalEvent

try:
    from ..llm.gateway import LLMGateway
except Exception:
    LLMGateway = None


# ----------------------------
# JSON helpers
# ----------------------------
def _dumps(v: Any) -> str:
    try:
        return json.dumps(v if v is not None else {}, default=str)
    except Exception:
        return "{}"


def _loads(s: Optional[str]) -> Any:
    if not s:
        return {}
    try:
        return json.loads(s)
    except Exception:
        return {}


# ----------------------------
# IDs / keys
# ----------------------------
def make_node_id(node_type: str, ref_id: str) -> str:
    return f"{node_type}:{ref_id}"


def make_edge_id(from_node_id: str, to_node_id: str, edge_type: str) -> str:
    return f"{from_node_id}|{edge_type}|{to_node_id}"


# ----------------------------
# Upserts
# ----------------------------
def upsert_node(
    session: Session,
    *,
    node_type: str,
    ref_id: str,
    label: str = "",
    attrs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    node_id = make_node_id(node_type, ref_id)
    now = datetime.utcnow()

    node = session.exec(
        select(GraphNode).where(GraphNode.node_id == node_id)
    ).first()

    if node is None:
        node = GraphNode(
            node_id=node_id,
            node_type=node_type,
            ref_id=ref_id,
            label=label or ref_id,
            attrs_json=_dumps(attrs or {}),
            created_at=now,
            updated_at=now,
        )
        session.add(node)
    else:
        node.label = label or node.label or ref_id
        if attrs is not None:
            merged = _loads(node.attrs_json)
            if isinstance(merged, dict):
                merged.update(attrs)
            else:
                merged = attrs
            node.attrs_json = _dumps(merged)
        node.updated_at = now

    session.commit()
    session.refresh(node)
    return serialize_node(node)


def upsert_edge(
    session: Session,
    *,
    from_node_type: str,
    from_ref_id: str,
    to_node_type: str,
    to_ref_id: str,
    edge_type: str,
    attrs: Optional[Dict[str, Any]] = None,
    from_label: str = "",
    to_label: str = "",
) -> Dict[str, Any]:
    # Ensure both nodes exist
    from_node = upsert_node(
        session,
        node_type=from_node_type,
        ref_id=from_ref_id,
        label=from_label or from_ref_id,
        attrs={},
    )
    to_node = upsert_node(
        session,
        node_type=to_node_type,
        ref_id=to_ref_id,
        label=to_label or to_ref_id,
        attrs={},
    )

    from_node_id = from_node["node_id"]
    to_node_id = to_node["node_id"]
    edge_id = make_edge_id(from_node_id, to_node_id, edge_type)
    now = datetime.utcnow()

    edge = session.exec(
        select(GraphEdge).where(GraphEdge.edge_id == edge_id)
    ).first()

    if edge is None:
        edge = GraphEdge(
            edge_id=edge_id,
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            edge_type=edge_type,
            attrs_json=_dumps(attrs or {}),
            created_at=now,
            updated_at=now,
        )
        session.add(edge)
    else:
        if attrs is not None:
            merged = _loads(edge.attrs_json)
            if isinstance(merged, dict):
                merged.update(attrs)
            else:
                merged = attrs
            edge.attrs_json = _dumps(merged)
        edge.updated_at = now

    session.commit()
    session.refresh(edge)
    return serialize_edge(edge)


def record_causal_event(
    session: Session,
    *,
    root_node_type: str,
    root_ref_id: str,
    event_type: str,
    before: Optional[Dict[str, Any]] = None,
    after: Optional[Dict[str, Any]] = None,
    impact: Optional[Dict[str, Any]] = None,
    actor: str = "system",
    source: str = "app",
    event_id: Optional[str] = None,
) -> Dict[str, Any]:
    # Ensure root node exists
    root = upsert_node(
        session,
        node_type=root_node_type,
        ref_id=root_ref_id,
        label=root_ref_id,
        attrs={},
    )

    root_node_id = root["node_id"]
    eid = event_id or f"evt_{uuid.uuid4().hex[:12]}"
    now = datetime.utcnow()

    existing = session.exec(
        select(CausalEvent).where(CausalEvent.event_id == eid)
    ).first()

    if existing is None:
        row = CausalEvent(
            event_id=eid,
            root_node_id=root_node_id,
            event_type=event_type,
            before_json=_dumps(before or {}),
            after_json=_dumps(after or {}),
            impact_json=_dumps(impact or {}),
            actor=actor,
            source=source,
            created_at=now,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return serialize_event(row)

    # update existing event if same id reused
    existing.root_node_id = root_node_id
    existing.event_type = event_type
    existing.before_json = _dumps(before or {})
    existing.after_json = _dumps(after or {})
    existing.impact_json = _dumps(impact or {})
    existing.actor = actor
    existing.source = source
    session.commit()
    session.refresh(existing)
    return serialize_event(existing)


# ----------------------------
# Serializers
# ----------------------------
def serialize_node(n: GraphNode) -> Dict[str, Any]:
    return {
        "node_id": n.node_id,
        "node_type": n.node_type,
        "ref_id": n.ref_id,
        "label": n.label,
        "attrs": _loads(n.attrs_json),
        "created_at": n.created_at.isoformat() if n.created_at else None,
        "updated_at": n.updated_at.isoformat() if n.updated_at else None,
    }


def serialize_edge(e: GraphEdge) -> Dict[str, Any]:
    return {
        "edge_id": e.edge_id,
        "from_node_id": e.from_node_id,
        "to_node_id": e.to_node_id,
        "edge_type": e.edge_type,
        "attrs": _loads(e.attrs_json),
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
    }


def serialize_event(ev: CausalEvent) -> Dict[str, Any]:
    return {
        "event_id": ev.event_id,
        "root_node_id": ev.root_node_id,
        "event_type": ev.event_type,
        "before": _loads(ev.before_json),
        "after": _loads(ev.after_json),
        "impact": _loads(ev.impact_json),
        "actor": ev.actor,
        "source": ev.source,
        "created_at": ev.created_at.isoformat() if ev.created_at else None,
    }


# ----------------------------
# Trace / traversal
# ----------------------------
def _fetch_node(session: Session, node_type: str, ref_id: str) -> Optional[GraphNode]:
    node_id = make_node_id(node_type, ref_id)
    return session.exec(select(GraphNode).where(GraphNode.node_id == node_id)).first()


def _fetch_edges_for_nodes(session: Session, node_ids: List[str]) -> List[GraphEdge]:
    if not node_ids:
        return []
    return list(
        session.exec(
            select(GraphEdge).where(
                or_(GraphEdge.from_node_id.in_(node_ids), GraphEdge.to_node_id.in_(node_ids))
            )
        ).all()
    )


def trace_entity(
    session: Session,
    *,
    node_type: str,
    ref_id: str,
    max_hops: int = 2,
    max_nodes: int = 200,
) -> Dict[str, Any]:
    root = _fetch_node(session, node_type, ref_id)
    if not root:
        return {
            "root": None,
            "nodes": [],
            "edges": [],
            "events": [],
            "impact_summary": {},
        }

    root_id = root.node_id
    visited = {root_id}
    frontier = {root_id}
    all_edges: Dict[str, GraphEdge] = {}

    for _ in range(max_hops):
        if not frontier:
            break

        edges = _fetch_edges_for_nodes(session, list(frontier))
        next_frontier = set()

        for e in edges:
            all_edges[e.edge_id] = e
            if e.from_node_id not in visited and len(visited) < max_nodes:
                visited.add(e.from_node_id)
                next_frontier.add(e.from_node_id)
            if e.to_node_id not in visited and len(visited) < max_nodes:
                visited.add(e.to_node_id)
                next_frontier.add(e.to_node_id)

        frontier = next_frontier

    nodes = list(
        session.exec(select(GraphNode).where(GraphNode.node_id.in_(list(visited)))).all()
    )

    # Events attached to any traced node as root
    events = list(
        session.exec(
            select(CausalEvent).where(CausalEvent.root_node_id.in_(list(visited)))
        ).all()
    )

    serialized_nodes = [serialize_node(n) for n in nodes]
    serialized_edges = [serialize_edge(e) for e in all_edges.values()]
    serialized_events = [serialize_event(e) for e in sorted(events, key=lambda x: x.created_at or datetime.min)]

    impact_summary = summarize_impacts(serialized_events)

    return {
        "root": serialize_node(root),
        "nodes": serialized_nodes,
        "edges": serialized_edges,
        "events": serialized_events,
        "impact_summary": impact_summary,
    }


def summarize_impacts(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Roll up common numeric deltas from causal event impact payloads.
    Example impact payload:
      {
        "revrec_delta": -12000,
        "commission_asset_delta": -1500,
        "forecast_12m_delta": -22000,
        "risk_score_delta": 15
      }
    """
    totals: Dict[str, float] = {}
    counts: Dict[str, int] = {}
    recent_event_types: Dict[str, int] = {}

    for ev in events:
        impact = ev.get("impact") or {}
        if not isinstance(impact, dict):
            continue

        recent_event_types[ev.get("event_type", "unknown")] = recent_event_types.get(ev.get("event_type", "unknown"), 0) + 1

        for k, v in impact.items():
            if isinstance(v, (int, float)):
                totals[k] = round(totals.get(k, 0.0) + float(v), 2)
                counts[k] = counts.get(k, 0) + 1

    return {
        "totals": totals,
        "counts": counts,
        "event_type_counts": recent_event_types,
    }


# ----------------------------
# AI explanation
# ----------------------------
def explain_impact(
    session: Session,
    *,
    root_type: str,
    root_id: str,
    question: str,
    max_hops: int = 2,
) -> Dict[str, Any]:
    trace = trace_entity(session, node_type=root_type, ref_id=root_id, max_hops=max_hops)

    if not trace.get("root"):
        return {
            "ok": False,
            "memo": f"No graph record found for {root_type}:{root_id}.",
            "trace": trace,
        }

    payload = {
        "title": "Accounting Intelligence Graph Impact Analysis",
        "question": question,
        "root": trace["root"],
        "impact_summary": trace["impact_summary"],
        # keep LLM payload compact but useful
        "recent_events": trace["events"][-10:],
        "linked_nodes": [
            {
                "node_type": n.get("node_type"),
                "ref_id": n.get("ref_id"),
                "label": n.get("label"),
            }
            for n in trace["nodes"]
        ],
        "linked_edges": [
            {
                "from": e.get("from_node_id"),
                "to": e.get("to_node_id"),
                "type": e.get("edge_type"),
            }
            for e in trace["edges"]
        ],
    }

    memo = None
    if LLMGateway is not None:
        try:
            llm = LLMGateway()

            # If you later add a dedicated method, this will pick it up.
            if hasattr(llm, "graph_explain_memo"):
                memo = llm.graph_explain_memo(payload)  # type: ignore[attr-defined]
            else:
                # Reuse audit memo path for now
                memo = llm.audit_memo(payload)
        except Exception:
            memo = None

    if not memo:
        memo = _rules_based_graph_memo(payload)

    return {
        "ok": True,
        "memo": memo,
        "trace": trace,
    }


def _rules_based_graph_memo(payload: Dict[str, Any]) -> str:
    q = payload.get("question", "")
    root = payload.get("root", {}) or {}
    impact = (payload.get("impact_summary", {}) or {}).get("totals", {}) or {}
    events = payload.get("recent_events", []) or []

    lines = []
    lines.append("Accounting Intelligence Graph Impact Analysis")
    lines.append("")
    lines.append(f"Question: {q}")
    lines.append(f"Root: {root.get('node_type')}:{root.get('ref_id')} ({root.get('label')})")
    lines.append("")

    if impact:
        lines.append("Aggregated impact deltas:")
        for k, v in impact.items():
            lines.append(f"- {k}: {v}")
        lines.append("")

    if events:
        lines.append("Recent causal events:")
        for ev in events[-5:]:
            lines.append(
                f"- {ev.get('event_type')} by {ev.get('actor', 'system')} "
                f"({ev.get('created_at', 'unknown time')})"
            )
        lines.append("")

    lines.append("This is a rules-based graph explanation fallback. LLM commentary is not configured.")
    return "\n".join(lines)


# ----------------------------
# Enterprise graph helpers (NEW)
# ----------------------------
def link_accounting_chain(
    session: Session,
    chain: List[Dict[str, Any]],
    edge_type: str = "related_to",
) -> Dict[str, Any]:
    """
    chain example:
    [
      {"node_type":"deal","ref_id":"DEAL-1001","label":"Deal 1001"},
      {"node_type":"contract","ref_id":"CTR-1001","label":"Contract 1001"},
      {"node_type":"revrec_schedule","ref_id":"RRS-1001","label":"RevRec Jan"},
      {"node_type":"invoice","ref_id":"INV-1001","label":"Invoice 1001"},
      ...
    ]
    """
    if not chain or len(chain) < 2:
        raise ValueError("Chain must include at least 2 nodes")

    created_nodes = []
    created_edges = []

    for n in chain:
        node = upsert_node(
            session=session,
            node_type=n["node_type"],
            ref_id=n["ref_id"],
            label=n.get("label") or "",
            attrs=n.get("attrs") or {},
        )
        created_nodes.append(node)

    for i in range(len(chain) - 1):
        a = chain[i]
        b = chain[i + 1]
        e = upsert_edge(
            session=session,
            from_node_type=a["node_type"],
            from_ref_id=a["ref_id"],
            to_node_type=b["node_type"],
            to_ref_id=b["ref_id"],
            edge_type=edge_type,
            attrs={"sequence": i + 1},
            from_label=a.get("label") or "",
            to_label=b.get("label") or "",
        )
        created_edges.append(e)

    return {
        "status": "ok",
        "nodes_linked": len(created_nodes),
        "edges_linked": len(created_edges),
    }


def trace_change_impact(
    session: Session,
    root_type: str,
    root_id: str,
    change_summary: Dict[str, Any],
    max_hops: int = 3,
) -> Dict[str, Any]:
    """
    Create a causal event + trace around it.
    """
    record_causal_event(
        session=session,
        root_node_type=root_type,
        root_ref_id=root_id,
        event_type="change_impact",
        before=change_summary.get("before") or {},
        after=change_summary.get("after") or {},
        impact=change_summary.get("impact") or {},
        actor=change_summary.get("actor") or "system",
        source=change_summary.get("source") or "app",
        event_id=change_summary.get("event_id"),
    )

    graph_trace = trace_entity(session=session, node_type=root_type, ref_id=root_id, max_hops=max_hops)

    return {
        "status": "ok",
        "root": {"type": root_type, "id": root_id},
        "change_summary": change_summary,
        "trace": graph_trace,
        "narrative": [
            f"Recorded change impact for {root_type}:{root_id}.",
            "Use /graph/explain-impact for a memo-style explanation of downstream effects.",
        ],
    }


def why_metric_changed(
    session: Session,
    metric_name: str,
    period_key: str,
    candidate_roots: List[Dict[str, str]],
) -> Dict[str, Any]:
    """
    v1 heuristic 'why' engine:
    Accept roots (contracts/deals/etc), trace each, and return a ranked explanation stub.
    """
    explanations = []

    for root in candidate_roots:
        rtype = root.get("node_type")
        rid = root.get("ref_id")
        if not rtype or not rid:
            continue

        try:
            t = trace_entity(session=session, node_type=rtype, ref_id=rid, max_hops=3)
            # simple heuristic score = count of touched nodes/edges
            score = 0
            if isinstance(t, dict):
                score += len(t.get("nodes", []) or [])
                score += len(t.get("edges", []) or [])
            explanations.append({
                "root_type": rtype,
                "root_id": rid,
                "impact_score": score,
                "reason": f"{rtype}:{rid} is connected to downstream accounting objects in {period_key}",
                "trace": t,
            })
        except Exception:
            continue

    explanations = sorted(explanations, key=lambda x: x["impact_score"], reverse=True)

    top = explanations[:5]
    summary_lines = [f"Top drivers of {metric_name} for {period_key}:"] + [
        f"- {x['root_type']}:{x['root_id']} (score={x['impact_score']})"
        for x in top
    ]

    return {
        "status": "ok",
        "metric_name": metric_name,
        "period_key": period_key,
        "drivers": top,
        "memo": "\n".join(summary_lines),
    }
