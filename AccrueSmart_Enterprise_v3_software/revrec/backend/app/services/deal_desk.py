# backend/app/services/deal_desk.py
from __future__ import annotations

from typing import Dict, Any, List

try:
    from ..llm.gateway import LLMGateway
except Exception:
    LLMGateway = None


def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _to_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _safe_str(v: Any) -> str:
    return "" if v is None else str(v)


def _compute_totals(lines: List[Dict[str, Any]]) -> Dict[str, float]:
    gross_total = 0.0
    net_total = 0.0
    discount_value = 0.0

    normalized_lines = []
    for line in lines:
        qty = _to_float(line.get("quantity"), 0)
        unit_price = _to_float(line.get("unit_price"), 0)
        discount_pct = _to_float(line.get("discount_pct"), 0)

        line_gross = qty * unit_price
        line_disc = line_gross * (discount_pct / 100.0)
        line_net = line_gross - line_disc

        gross_total += line_gross
        discount_value += line_disc
        net_total += line_net

        normalized_lines.append({
            **line,
            "quantity": qty,
            "unit_price": unit_price,
            "discount_pct": discount_pct,
            "_line_gross": round(line_gross, 2),
            "_line_discount": round(line_disc, 2),
            "_line_net": round(line_net, 2),
        })

    blended_discount_pct = (discount_value / gross_total * 100.0) if gross_total > 0 else 0.0

    return {
        "gross_total": round(gross_total, 2),
        "net_total": round(net_total, 2),
        "discount_value": round(discount_value, 2),
        "blended_discount_pct": round(blended_discount_pct, 2),
        "normalized_lines": normalized_lines,
    }


def _severity_from_score(score: float) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _build_llm_memo(payload: Dict[str, Any], review: Dict[str, Any]) -> str:
    """
    Use LLMGateway if available. Fall back to deterministic memo.
    """
    fallback = _mock_deal_desk_memo(payload, review)

    if LLMGateway is None:
        return fallback + "\n\n(LLM gateway not available; using rules-based memo.)"

    try:
        llm = LLMGateway()

        # Prefer a dedicated method if you've added it to gateway.py
        if hasattr(llm, "deal_desk_memo") and callable(getattr(llm, "deal_desk_memo")):
            return llm.deal_desk_memo(payload, review)

        # Safe fallback if gateway exists but no deal_desk_memo yet
        return fallback + "\n\n(LLM deal_desk_memo not configured in gateway; using rules-based memo.)"
    except Exception as e:
        return fallback + f"\n\n(LLM memo generation failed: {e})"


def _mock_deal_desk_memo(payload: Dict[str, Any], review: Dict[str, Any]) -> str:
    customer = _safe_str(payload.get("customer_name", "Unknown Customer"))
    quote_name = _safe_str(payload.get("quote_name", "Unnamed Quote"))
    term = _to_int(payload.get("contract_term_months"), 0)
    billing = _safe_str(payload.get("billing_frequency", "unknown"))
    payment_terms = _safe_str(payload.get("payment_terms", "unknown"))

    totals = review.get("totals", {})
    exceptions = review.get("exceptions", [])
    recs = review.get("recommendations", [])
    approval_path = review.get("approval_path", [])

    lines_out = []
    lines_out.append("Deal Desk AI Memo")
    lines_out.append("")
    lines_out.append("Deal Summary")
    lines_out.append(f"- Customer: {customer}")
    lines_out.append(f"- Quote: {quote_name}")
    lines_out.append(f"- Term: {term} months")
    lines_out.append(f"- Billing: {billing}")
    lines_out.append(f"- Payment Terms: {payment_terms}")
    lines_out.append(f"- Gross Total: ${totals.get('gross_total', 0):,.2f}")
    lines_out.append(f"- Net Total: ${totals.get('net_total', 0):,.2f}")
    lines_out.append(f"- Blended Discount: {totals.get('blended_discount_pct', 0):,.2f}%")
    lines_out.append("")

    lines_out.append("Key Risks")
    if exceptions:
        for ex in exceptions[:6]:
            lines_out.append(f"- [{ex.get('severity','low').upper()}] {ex.get('message','')}")
    else:
        lines_out.append("- No material policy exceptions detected.")
    lines_out.append("")

    lines_out.append("Recommended Changes")
    if recs:
        for r in recs[:6]:
            lines_out.append(f"- {r}")
    else:
        lines_out.append("- No changes required under current policy.")
    lines_out.append("")

    lines_out.append("Approval Recommendation")
    lines_out.append(f"- Status: {review.get('status', 'unknown')}")
    if approval_path:
        lines_out.append(f"- Route: {' -> '.join(approval_path)}")
    lines_out.append("")

    lines_out.append("Sales Talking Points")
    lines_out.append("- Align contract term and payment terms to reduce approval friction.")
    lines_out.append("- If discount is above policy, prepare ROI and competitive justification.")
    lines_out.append("- Remove or narrow non-standard clauses to accelerate legal review.")
    lines_out.append("")

    lines_out.append("LLM commentary is not configured, so this is a rules-based memo.")
    return "\n".join(lines_out)


def review_deal(payload: Dict[str, Any]) -> Dict[str, Any]:
    # ----------------------------
    # Inputs
    # ----------------------------
    customer_name = _safe_str(payload.get("customer_name"))
    quote_name = _safe_str(payload.get("quote_name"))
    contract_term_months = _to_int(payload.get("contract_term_months"), 0)
    billing_frequency = _safe_str(payload.get("billing_frequency", "monthly")).lower()
    payment_terms = _safe_str(payload.get("payment_terms", "Net 30"))
    currency = _safe_str(payload.get("currency", "USD"))
    nonstandard_terms = _safe_str(payload.get("nonstandard_terms", ""))
    notes = _safe_str(payload.get("notes", ""))

    approval_policy = payload.get("approval_policy", {}) or {}
    max_standard_discount_pct = _to_float(approval_policy.get("max_standard_discount_pct"), 20)
    max_auto_approve_term_months = _to_int(approval_policy.get("max_auto_approve_term_months"), 12)
    require_legal_for_nonstandard_terms = bool(
        approval_policy.get("require_legal_for_nonstandard_terms", True)
    )
    require_finance_for_services_discount = bool(
        approval_policy.get("require_finance_for_services_discount", True)
    )

    raw_lines = payload.get("lines", []) or []
    if not isinstance(raw_lines, list):
        raw_lines = []

    totals_info = _compute_totals(raw_lines)
    lines = totals_info.pop("normalized_lines")

    # ----------------------------
    # Rule Engine / Exceptions
    # ----------------------------
    exceptions: List[Dict[str, str]] = []
    observations: List[str] = []
    recommendations: List[str] = []
    approval_path: List[str] = []

    risk_scores = {
        "pricing": 10,
        "term": 10,
        "legal": 10,
        "billing": 10,
        "collections": 10,
        "revrec": 10,
    }

    health_scores = {
        "pricing": 90,
        "term": 90,
        "legal": 90,
        "billing": 90,
        "collections": 90,
        "revrec": 90,
    }

    # Discount checks
    blended_discount = totals_info["blended_discount_pct"]
    max_line_discount = max([_to_float(l.get("discount_pct"), 0) for l in lines], default=0)

    if blended_discount > max_standard_discount_pct:
        risk_scores["pricing"] += 35
        exceptions.append({
            "code": "DISCOUNT_POLICY_EXCEEDED",
            "severity": "high",
            "message": (
                f"Blended discount {blended_discount:.2f}% exceeds policy threshold "
                f"{max_standard_discount_pct:.2f}%."
            ),
        })
        recommendations.append("Reduce blended discount or attach approval justification (competitive/strategic).")
    elif blended_discount > max_standard_discount_pct * 0.75:
        risk_scores["pricing"] += 18
        observations.append("Blended discount is approaching approval threshold.")
        recommendations.append("Document pricing rationale to avoid approval delays.")

    if max_line_discount > (max_standard_discount_pct + 10):
        risk_scores["pricing"] += 20
        exceptions.append({
            "code": "LINE_DISCOUNT_OUTLIER",
            "severity": "medium",
            "message": f"At least one line has discount {max_line_discount:.2f}%, a pricing outlier.",
        })
        recommendations.append("Normalize line-level discounting and avoid hidden discount concentration.")

    # Term checks
    if contract_term_months <= 0:
        risk_scores["term"] += 50
        exceptions.append({
            "code": "INVALID_TERM",
            "severity": "high",
            "message": "Contract term months is missing or invalid.",
        })
        recommendations.append("Provide a valid contract term in months.")
    else:
        if contract_term_months > max_auto_approve_term_months:
            risk_scores["term"] += 25
            exceptions.append({
                "code": "LONG_TERM_APPROVAL",
                "severity": "medium",
                "message": (
                    f"Contract term ({contract_term_months} months) exceeds auto-approve limit "
                    f"({max_auto_approve_term_months} months)."
                ),
            })
            recommendations.append("Route long-term deal to Finance for term risk review.")

        if contract_term_months >= 36:
            risk_scores["revrec"] += 15
            observations.append("Long-term contract may require added rev rec scrutiny (modification/renewal risk).")
            recommendations.append("Confirm SSPs, PO allocation, and renewal assumptions for long-term deal.")

    # Billing / collections checks
    if billing_frequency not in {"monthly", "quarterly", "annual"}:
        risk_scores["billing"] += 25
        exceptions.append({
            "code": "NONSTANDARD_BILLING_FREQUENCY",
            "severity": "medium",
            "message": f"Billing frequency '{billing_frequency}' is non-standard.",
        })

    pt = payment_terms.lower().replace(" ", "")
    if "net60" in pt:
        risk_scores["collections"] += 20
        exceptions.append({
            "code": "EXTENDED_PAYMENT_TERMS",
            "severity": "medium",
            "message": "Payment terms are Net 60, which may increase collections risk.",
        })
        recommendations.append("Consider Net 30 or staged billing to reduce DSO risk.")
    elif "net90" in pt or "net120" in pt:
        risk_scores["collections"] += 35
        exceptions.append({
            "code": "VERY_EXTENDED_PAYMENT_TERMS",
            "severity": "high",
            "message": f"Payment terms '{payment_terms}' create elevated collections risk.",
        })
        recommendations.append("Require finance approval for extended payment terms.")

    # Non-standard legal terms
    nonstandard_lower = nonstandard_terms.lower()
    has_nonstandard = len(nonstandard_lower.strip()) > 0

    legal_keywords = [
        "termination for convenience",
        "milestone acceptance",
        "acceptance criteria",
        "refund",
        "penalty",
        "indemnity cap",
        "uncapped liability",
        "sla credits",
        "most favored",
        "evergreen",
    ]
    matched_legal_flags = [kw for kw in legal_keywords if kw in nonstandard_lower]

    if has_nonstandard and require_legal_for_nonstandard_terms:
        risk_scores["legal"] += 25
        exceptions.append({
            "code": "NONSTANDARD_TERMS_PRESENT",
            "severity": "medium",
            "message": "Non-standard terms provided; legal review required by policy.",
        })
        recommendations.append("Route to Legal and redline non-standard clauses to approved fallback language.")

    if matched_legal_flags:
        risk_scores["legal"] += min(40, 10 * len(matched_legal_flags))
        observations.append(f"Detected legal risk keywords: {', '.join(matched_legal_flags)}")
        recommendations.append("Review termination, acceptance, and liability clauses before approval.")

    # Services line discount policy check
    service_lines = [l for l in lines if _safe_str(l.get("type")).lower() == "services"]
    if require_finance_for_services_discount:
        service_discounted = [l for l in service_lines if _to_float(l.get("discount_pct")) > 0]
        if service_discounted:
            risk_scores["pricing"] += 10
            exceptions.append({
                "code": "SERVICES_DISCOUNT_FINANCE_REVIEW",
                "severity": "medium",
                "message": "Discounted services line detected; finance review required by policy.",
            })
            recommendations.append("Validate services margin and staffing assumptions with Finance.")

    # RevRec heuristics by line mix
    line_types = {_safe_str(l.get("type")).lower() for l in lines}
    if "services" in line_types and "subscription" in line_types:
        risk_scores["revrec"] += 10
        observations.append("Mixed subscription + services deal may require PO separation and timing review.")
        recommendations.append("Confirm distinct performance obligations and standalone selling prices.")

    if "usage" in line_types:
        risk_scores["revrec"] += 8
        observations.append("Usage-based pricing present; variable consideration policy should be reviewed.")
        recommendations.append("Document usage billing and variable consideration treatment under ASC 606.")

    # Data quality checks
    if not customer_name:
        risk_scores["pricing"] += 10
        exceptions.append({
            "code": "MISSING_CUSTOMER",
            "severity": "low",
            "message": "Customer name is blank.",
        })

    if not quote_name:
        risk_scores["pricing"] += 10
        exceptions.append({
            "code": "MISSING_QUOTE_NAME",
            "severity": "low",
            "message": "Quote name is blank.",
        })

    if len(lines) == 0:
        risk_scores["pricing"] = 100
        risk_scores["revrec"] = 100
        exceptions.append({
            "code": "NO_LINES",
            "severity": "high",
            "message": "No deal lines provided.",
        })
        recommendations.append("Add at least one deal line.")
    else:
        observations.append(f"Deal contains {len(lines)} line(s).")

    # Clamp risk scores and derive health scores
    for k in list(risk_scores.keys()):
        risk_scores[k] = max(0, min(100, round(risk_scores[k], 2)))
        health_scores[k] = max(0, min(100, round(100 - risk_scores[k], 2)))

    overall_health_score = round(sum(health_scores.values()) / len(health_scores), 1) if health_scores else 0.0

    # Approval path
    approval_path = ["Sales Manager"]
    high_ex_count = sum(1 for e in exceptions if e.get("severity") == "high")
    med_ex_count = sum(1 for e in exceptions if e.get("severity") == "medium")

    if any(e["code"] == "NONSTANDARD_TERMS_PRESENT" for e in exceptions) or matched_legal_flags:
        approval_path.append("Legal")

    if any(e["code"] in {"DISCOUNT_POLICY_EXCEEDED", "SERVICES_DISCOUNT_FINANCE_REVIEW", "LONG_TERM_APPROVAL"} for e in exceptions):
        approval_path.append("Finance")

    if high_ex_count >= 2 or overall_health_score < 55:
        approval_path.append("CFO")
    elif med_ex_count >= 3 or overall_health_score < 70:
        if "Finance" not in approval_path:
            approval_path.append("Finance")

    # Final status
    if high_ex_count >= 2 or overall_health_score < 50:
        status = "escalate"
    elif high_ex_count >= 1 or med_ex_count >= 2 or overall_health_score < 75:
        status = "needs_review"
    else:
        status = "approve"

    # De-dupe / clean
    def _dedupe_keep_order(items: List[str]) -> List[str]:
        seen = set()
        out = []
        for item in items:
            key = item.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out

    observations = _dedupe_keep_order(observations)
    recommendations = _dedupe_keep_order(recommendations)

    review = {
        "status": status,
        "overall_health_score": overall_health_score,
        "risk_scores": risk_scores,
        "health_scores": health_scores,
        "exceptions": exceptions,
        "observations": observations,
        "recommendations": recommendations,
        "approval_path": approval_path,
        "totals": {
            "gross_total": totals_info["gross_total"],
            "net_total": totals_info["net_total"],
            "discount_value": totals_info["discount_value"],
            "blended_discount_pct": totals_info["blended_discount_pct"],
        },
        "lines": lines,
    }

    memo = _build_llm_memo(payload, review)
    review["memo"] = memo
    return review
