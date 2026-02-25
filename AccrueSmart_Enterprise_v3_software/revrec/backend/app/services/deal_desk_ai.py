# backend/app/services/deal_desk_ai.py
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

try:
    from ..llm.gateway import LLMGateway
except Exception:
    LLMGateway = None


def _safe_num(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _normalize_lines(lines: Any) -> List[Dict[str, Any]]:
    if not isinstance(lines, list):
        return []

    out: List[Dict[str, Any]] = []
    for i, line in enumerate(lines):
        if not isinstance(line, dict):
            continue
        out.append(
            {
                "sku": str(line.get("sku") or f"LINE-{i+1}"),
                "description": str(line.get("description") or ""),
                "quantity": _safe_num(line.get("quantity"), 1.0),
                "unit_price": _safe_num(line.get("unit_price"), 0.0),
                "discount_pct": _safe_num(line.get("discount_pct"), 0.0),
                "term_months": int(_safe_num(line.get("term_months"), 12)),
                "type": str(line.get("type") or "subscription"),  # subscription, services, usage, support
            }
        )
    return out


def _compute_totals(lines: List[Dict[str, Any]]) -> Dict[str, float]:
    gross = 0.0
    net = 0.0
    total_discount_value = 0.0

    for l in lines:
        qty = _safe_num(l.get("quantity"), 1.0)
        unit_price = _safe_num(l.get("unit_price"), 0.0)
        discount_pct = _safe_num(l.get("discount_pct"), 0.0)

        line_gross = qty * unit_price
        line_discount = line_gross * (discount_pct / 100.0)
        line_net = line_gross - line_discount

        gross += line_gross
        net += line_net
        total_discount_value += line_discount

    blended_discount_pct = (total_discount_value / gross * 100.0) if gross > 0 else 0.0

    return {
        "gross_total": round(gross, 2),
        "net_total": round(net, 2),
        "discount_value": round(total_discount_value, 2),
        "blended_discount_pct": round(blended_discount_pct, 2),
    }


def _rule_based_review(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fast deterministic checks + scoring. LLM will enhance the narrative.
    """
    customer_name = str(payload.get("customer_name") or "Unknown Customer")
    contract_term_months = int(_safe_num(payload.get("contract_term_months"), 12))
    billing_frequency = str(payload.get("billing_frequency") or "annual")
    payment_terms = str(payload.get("payment_terms") or "Net 30")
    approval_policy = payload.get("approval_policy") or {}
    lines = _normalize_lines(payload.get("lines"))

    totals = _compute_totals(lines)

    # policy thresholds (customizable)
    max_standard_discount_pct = _safe_num(approval_policy.get("max_standard_discount_pct"), 20.0)
    max_auto_approve_term_months = int(_safe_num(approval_policy.get("max_auto_approve_term_months"), 12))
    require_legal_for_nonstandard_terms = bool(approval_policy.get("require_legal_for_nonstandard_terms", True))
    require_finance_for_services_discount = bool(approval_policy.get("require_finance_for_services_discount", True))

    exceptions: List[Dict[str, Any]] = []
    recommendations: List[str] = []
    observations: List[str] = []

    # risk dimensions (0 = no risk, 100 = max risk)
    revrec_risk = 10
    pricing_risk = 10
    collections_risk = 10
    approval_risk = 10
    legal_risk = 10

    # discount policy
    if totals["blended_discount_pct"] > max_standard_discount_pct:
        exceptions.append(
            {
                "code": "DISCOUNT_OVER_POLICY",
                "severity": "high",
                "message": (
                    f"Blended discount {totals['blended_discount_pct']}% exceeds "
                    f"policy threshold {max_standard_discount_pct}%."
                ),
            }
        )
        pricing_risk += 30
        approval_risk += 20
        recommendations.append("Consider reducing discount or requiring annual prepay to offset concession.")
        recommendations.append("Split discount by line and keep services discount lower than subscription discount.")

    # long-term contract complexity
    if contract_term_months > max_auto_approve_term_months:
        exceptions.append(
            {
                "code": "LONG_TERM_NONSTANDARD",
                "severity": "medium",
                "message": (
                    f"Contract term ({contract_term_months} months) exceeds "
                    f"auto-approve term ({max_auto_approve_term_months} months)."
                ),
            }
        )
        revrec_risk += 15
        approval_risk += 20
        recommendations.append("Add renewal and termination language clarity for multi-year term.")

    # billing frequency cash risk
    if billing_frequency.lower() in {"monthly", "quarterly"} and contract_term_months >= 24:
        exceptions.append(
            {
                "code": "LONG_TERM_LOW_CASH_COLLECTION",
                "severity": "medium",
                "message": "Long-term deal billed monthly/quarterly may increase collections and churn risk.",
            }
        )
        collections_risk += 20
        recommendations.append("Offer annual prepay option with smaller discount to improve cash flow.")

    # payment terms
    if "60" in payment_terms or "90" in payment_terms:
        exceptions.append(
            {
                "code": "EXTENDED_PAYMENT_TERMS",
                "severity": "medium",
                "message": f"Extended payment terms detected ({payment_terms}).",
            }
        )
        collections_risk += 20
        approval_risk += 10
        recommendations.append("Consider staged billing or partial upfront payment for extended terms.")

    # line-level checks
    has_services = False
    has_usage = False
    has_subscription = False
    line_term_mismatch = False

    for l in lines:
        ltype = (l.get("type") or "").lower()
        d = _safe_num(l.get("discount_pct"), 0.0)
        term = int(_safe_num(l.get("term_months"), contract_term_months))

        if ltype == "services":
            has_services = True
            if d > 10 and require_finance_for_services_discount:
                exceptions.append(
                    {
                        "code": "SERVICES_DISCOUNT_HIGH",
                        "severity": "medium",
                        "message": f"Services line '{l.get('sku')}' has discount {d}% (above typical threshold).",
                    }
                )
                pricing_risk += 10
                approval_risk += 10

        if ltype == "usage":
            has_usage = True
            revrec_risk += 8
            observations.append("Usage-based pricing detected, which may require variable consideration assessment.")

        if ltype == "subscription":
            has_subscription = True

        if term != contract_term_months and ltype in {"subscription", "support"}:
            line_term_mismatch = True

    if line_term_mismatch:
        exceptions.append(
            {
                "code": "LINE_TERM_MISMATCH",
                "severity": "low",
                "message": "One or more recurring lines have term months different from the overall contract term.",
            }
        )
        revrec_risk += 10
        recommendations.append("Confirm line-level term alignment to avoid billing and rev rec mismatches.")

    # legal terms flags from free text
    nonstandard_terms_text = str(payload.get("nonstandard_terms") or "")
    txt = nonstandard_terms_text.lower()

    if txt:
        if any(w in txt for w in ["termination for convenience", "cancel any time", "opt-out"]):
            exceptions.append(
                {
                    "code": "TERMINATION_FLEXIBILITY",
                    "severity": "high",
                    "message": "Termination/opt-out language may impact enforceable rights and revenue recognition.",
                }
            )
            legal_risk += 25
            revrec_risk += 20
            recommendations.append("Tighten termination language and clarify non-cancelable period.")

        if any(w in txt for w in ["acceptance", "subject to acceptance", "milestone acceptance"]):
            exceptions.append(
                {
                    "code": "ACCEPTANCE_CLAUSE",
                    "severity": "high",
                    "message": "Acceptance language detected; this may delay revenue recognition for some obligations.",
                }
            )
            legal_risk += 20
            revrec_risk += 20
            recommendations.append("Clarify objective acceptance criteria and timing for acceptance.")

        if require_legal_for_nonstandard_terms:
            approval_risk += 15
            recommendations.append("Route to Legal review because non-standard terms were provided.")

    # recommendations based on composition
    if has_services and has_subscription:
        recommendations.append("Separate implementation/services and subscription pricing clearly for PO allocation support.")
    if has_usage:
        recommendations.append("Define usage floor, overage mechanics, and reporting period to reduce variable consideration ambiguity.")
    if has_subscription and billing_frequency.lower() == "monthly" and totals["blended_discount_pct"] > 15:
        recommendations.append("Offer annual billing with a lower discount to improve cash and reduce churn exposure.")

    # dedupe recommendations while preserving order
    dedup_recs: List[str] = []
    seen = set()
    for r in recommendations:
        if r not in seen:
            dedup_recs.append(r)
            seen.add(r)

    # Normalize scores 0-100
    def clamp(x: float) -> int:
        if x < 0:
            return 0
        if x > 100:
            return 100
        return int(round(x))

    risk_scores = {
        "revrec": clamp(revrec_risk),
        "pricing": clamp(pricing_risk),
        "collections": clamp(collections_risk),
        "approval": clamp(approval_risk),
        "legal": clamp(legal_risk),
    }

    # Convert risk to health
    health_scores = {k: clamp(100 - v) for k, v in risk_scores.items()}
    overall_health = clamp(sum(health_scores.values()) / len(health_scores)) if health_scores else 0

    approval_path = ["Sales Manager"]
    if approval_risk >= 30 or pricing_risk >= 30:
        approval_path.append("Finance")
    if legal_risk >= 30 or nonstandard_terms_text.strip():
        approval_path.append("Legal")
    if overall_health < 70:
        approval_path.append("CFO")

    return {
        "customer_name": customer_name,
        "totals": totals,
        "risk_scores": risk_scores,
        "health_scores": health_scores,
        "overall_health_score": overall_health,
        "exceptions": exceptions,
        "observations": observations,
        "recommendations": dedup_recs[:10],
        "approval_path": approval_path,
        "normalized_lines": lines,
    }


def _build_llm_prompt(review: Dict[str, Any], payload: Dict[str, Any]) -> str:
    return f"""
You are an expert Deal Desk + Accounting + RevRec reviewer for B2B SaaS.

Produce a concise but high-quality deal review memo with these sections:
1) Deal Summary
2) Key Risks (commercial, accounting/rev rec, legal, collections)
3) Recommended Changes (practical alternatives)
4) Approval Recommendation
5) Sales Talking Points (what sales can say back to customer)

Be specific and action-oriented. Mention rev rec implications when relevant (acceptance clauses, usage-based pricing, non-cancelable term, services bundling, discounting).
Use plain English, no fluff.

Structured review data:
{json.dumps(review, indent=2)}

Original payload:
{json.dumps(payload, indent=2)}
""".strip()


def review_deal(payload: Dict[str, Any]) -> Dict[str, Any]:
    review = _rule_based_review(payload)

    llm_memo: Optional[str] = None
    if LLMGateway is not None:
        try:
            llm = LLMGateway()
            prompt = _build_llm_prompt(review, payload)

            # Try common method names safely
            if hasattr(llm, "chat"):
                llm_memo = llm.chat(prompt)
            elif hasattr(llm, "complete"):
                llm_memo = llm.complete(prompt)
            elif hasattr(llm, "deal_desk_memo"):
                llm_memo = llm.deal_desk_memo(payload, review)
        except Exception:
            llm_memo = None

    if not llm_memo:
        exceptions_text = "\n".join(
            [f"- [{e.get('severity','').upper()}] {e.get('message','')}" for e in review["exceptions"]]
        ) or "- None"

        recommendations_text = "\n".join([f"- {r}" for r in review["recommendations"]]) or "- None"
        approval_text = " -> ".join(review["approval_path"])

        llm_memo = (
            f"Deal Desk AI Review\n\n"
            f"Customer: {review['customer_name']}\n"
            f"Overall Health Score: {review['overall_health_score']}\n\n"
            f"Totals:\n"
            f"- Gross: {review['totals']['gross_total']}\n"
            f"- Net: {review['totals']['net_total']}\n"
            f"- Blended Discount: {review['totals']['blended_discount_pct']}%\n\n"
            f"Key Exceptions:\n{exceptions_text}\n\n"
            f"Recommendations:\n{recommendations_text}\n\n"
            f"Approval Path:\n- {approval_text}\n\n"
            f"LLM commentary is not configured, so this is a rules-based summary."
        )

    return {
        "status": "ok",
        "overall_health_score": review["overall_health_score"],
        "risk_scores": review["risk_scores"],
        "health_scores": review["health_scores"],
        "exceptions": review["exceptions"],
        "observations": review["observations"],
        "recommendations": review["recommendations"],
        "approval_path": review["approval_path"],
        "totals": review["totals"],
        "lines": review["normalized_lines"],
        "memo": llm_memo,
    }
