# backend/app/services/policy_engine.py
from __future__ import annotations

from typing import Any, Dict, List
import re


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(float(v))
    except Exception:
        return default


def parse_policy_text(policy_lines: List[str]) -> List[Dict[str, Any]]:
    """
    Converts plain-English policy statements into structured rules.
    This is intentionally deterministic/rules-based for reliability.
    You can later add LLM-based parsing fallback.
    """
    out: List[Dict[str, Any]] = []

    for raw in policy_lines:
        line = (raw or "").strip()
        if not line:
            continue

        l = line.lower()

        # Example: "Any services discount >10% requires finance approval"
        m = re.search(r"services\s+discount\s*>\s*(\d+(?:\.\d+)?)\s*%?.*finance", l)
        if m:
            out.append({
                "rule_id": f"RULE-{len(out)+1}",
                "name": "Services Discount Finance Approval",
                "scope": "deal_desk",
                "condition": {
                    "metric": "services_discount_pct",
                    "operator": ">",
                    "value": float(m.group(1)),
                },
                "action": {
                    "type": "add_approval",
                    "value": "Finance",
                },
                "source_text": line,
            })
            continue

        # Example: "Net terms >45 need CFO approval"
        m = re.search(r"net\s*terms?\s*>\s*(\d+).*cfo", l)
        if m:
            out.append({
                "rule_id": f"RULE-{len(out)+1}",
                "name": "Net Terms CFO Approval",
                "scope": "deal_desk",
                "condition": {
                    "metric": "payment_terms_days",
                    "operator": ">",
                    "value": int(m.group(1)),
                },
                "action": {
                    "type": "add_approval",
                    "value": "CFO",
                },
                "source_text": line,
            })
            continue

        # Example: "Termination for convenience triggers legal review"
        if "termination for convenience" in l and ("legal" in l or "review" in l):
            out.append({
                "rule_id": f"RULE-{len(out)+1}",
                "name": "Termination for Convenience Legal Review",
                "scope": "deal_desk",
                "condition": {
                    "metric": "nonstandard_terms_contains",
                    "operator": "contains",
                    "value": "termination for convenience",
                },
                "action": {
                    "type": "add_approval",
                    "value": "Legal",
                },
                "source_text": line,
            })
            continue

        # Example: "Contracts >24 months need revrec review"
        m = re.search(r"contracts?\s*>\s*(\d+)\s*months?.*revrec", l)
        if m:
            out.append({
                "rule_id": f"RULE-{len(out)+1}",
                "name": "Long Contract RevRec Review",
                "scope": "deal_desk",
                "condition": {
                    "metric": "contract_term_months",
                    "operator": ">",
                    "value": int(m.group(1)),
                },
                "action": {
                    "type": "add_approval",
                    "value": "RevRec",
                },
                "source_text": line,
            })
            continue

        # fallback unknown policy
        out.append({
            "rule_id": f"RULE-{len(out)+1}",
            "name": "Unparsed Policy",
            "scope": "deal_desk",
            "condition": {"metric": "manual_review", "operator": "=", "value": True},
            "action": {"type": "add_approval", "value": "Finance"},
            "source_text": line,
            "parse_status": "manual_review_needed",
        })

    return out


def _extract_payment_terms_days(s: str) -> int:
    s = (s or "").lower()
    # Handles "Net 30", "net60", etc
    m = re.search(r"net\s*?(\d+)", s)
    if m:
        return int(m.group(1))
    # fallback if number present
    m = re.search(r"(\d+)", s)
    if m:
        return int(m.group(1))
    return 0


def evaluate_policy_rules(rules: List[Dict[str, Any]], deal_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluate rules against deal payload and return triggered results.
    """
    lines = deal_payload.get("lines", []) or []
    nonstandard_terms = (deal_payload.get("nonstandard_terms") or "").lower()
    contract_term_months = _safe_int(deal_payload.get("contract_term_months"), 0)
    payment_terms = deal_payload.get("payment_terms", "")
    payment_terms_days = _extract_payment_terms_days(payment_terms)

    # compute services discount % (max or blended services discount)
    services_lines = [l for l in lines if str(l.get("type", "")).lower() == "services"]
    services_discount_pct = 0.0
    if services_lines:
        # use max services discount as trigger metric
        services_discount_pct = max(_safe_float(l.get("discount_pct", 0)) for l in services_lines)

    ctx = {
        "services_discount_pct": services_discount_pct,
        "payment_terms_days": payment_terms_days,
        "contract_term_months": contract_term_months,
        "nonstandard_terms_contains": nonstandard_terms,
        "manual_review": True,
    }

    triggered: List[Dict[str, Any]] = []
    approvals: List[str] = []

    for rule in rules:
        cond = rule.get("condition", {}) or {}
        action = rule.get("action", {}) or {}

        metric = cond.get("metric")
        op = cond.get("operator")
        target = cond.get("value")
        current = ctx.get(metric)

        hit = False

        try:
            if op == ">":
                hit = _safe_float(current) > _safe_float(target)
            elif op == ">=":
                hit = _safe_float(current) >= _safe_float(target)
            elif op == "<":
                hit = _safe_float(current) < _safe_float(target)
            elif op == "<=":
                hit = _safe_float(current) <= _safe_float(target)
            elif op == "=":
                hit = current == target
            elif op == "contains":
                hit = str(target).lower() in str(current).lower()
        except Exception:
            hit = False

        if hit:
            tr = {
                "rule_id": rule.get("rule_id"),
                "name": rule.get("name"),
                "action": action,
                "source_text": rule.get("source_text"),
            }
            triggered.append(tr)

            if action.get("type") == "add_approval":
                approvals.append(str(action.get("value")))

    # de-duplicate approvals, preserve order
    dedup_approvals: List[str] = []
    for a in approvals:
        if a not in dedup_approvals:
            dedup_approvals.append(a)

    return {
        "context": ctx,
        "triggered_rules": triggered,
        "required_approvals": dedup_approvals,
    }
