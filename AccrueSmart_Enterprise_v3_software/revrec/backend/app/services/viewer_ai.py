# backend/app/services/viewer_ai.py
from __future__ import annotations

from typing import Dict, Any, List
import re
import json

try:
    from ..llm.gateway import LLMGateway
except Exception:
    LLMGateway = None


def _to_num(s: str, default: float = 0.0) -> float:
    try:
        return float(s.replace(",", "").replace("$", "").strip())
    except Exception:
        return default


def _heuristic_extract(text: str) -> Dict[str, Any]:
    t = text or ""
    low = t.lower()

    # Basic regex pulls
    customer_name = None
    m = re.search(r"(customer|client)\s*[:\-]\s*([A-Za-z0-9&., \-]+)", t, re.I)
    if m:
        customer_name = m.group(2).strip()

    quote_name = None
    m = re.search(r"(quote|order form|proposal)\s*(id|#)?\s*[:\-]\s*([A-Za-z0-9\-_]+)", t, re.I)
    if m:
        quote_name = m.group(3).strip()

    # Term
    contract_term_months = None
    m = re.search(r"(\d{1,3})\s*(month|months)\b", low)
    if m:
        contract_term_months = int(m.group(1))
    else:
        m = re.search(r"(\d{1,2})\s*(year|years)\b", low)
        if m:
            contract_term_months = int(m.group(1)) * 12

    # Billing frequency
    billing_frequency = "unknown"
    if "annual" in low or "annually" in low or "yearly" in low:
        billing_frequency = "annual"
    elif "quarterly" in low:
        billing_frequency = "quarterly"
    elif "monthly" in low:
        billing_frequency = "monthly"
    elif "upfront" in low or "in advance" in low:
        billing_frequency = "upfront"

    # Payment terms
    payment_terms = "Unknown"
    for p in ["net 15", "net 30", "net 45", "net 60", "net 90"]:
        if p in low:
            payment_terms = p.upper()
            break

    # Money amounts (best effort)
    amounts = re.findall(r"\$?\s?(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)", t)
    parsed_amounts = [_to_num(x) for x in amounts if _to_num(x) > 0]
    gross_total = max(parsed_amounts) if parsed_amounts else 0.0

    # Key clauses / risks
    risk_flags: List[Dict[str, Any]] = []

    def add_flag(code: str, severity: str, message: str):
        risk_flags.append({"code": code, "severity": severity, "message": message})

    if "termination for convenience" in low:
        add_flag("termination_for_convenience", "high", "Termination for convenience detected.")
    if "acceptance" in low or "acceptance criteria" in low:
        add_flag("acceptance_clause", "medium", "Acceptance language detected (may affect timing / rev rec).")
    if "refund" in low:
        add_flag("refund_rights", "medium", "Refund language detected.")
    if "service level credit" in low or "sla credit" in low:
        add_flag("sla_credits", "medium", "SLA/service credits detected.")
    if "most favored nation" in low or "mfn" in low:
        add_flag("mfn", "high", "MFN term detected.")
    if "unlimited liability" in low:
        add_flag("liability_cap", "high", "Unlimited liability language detected.")
    if "indemn" in low:
        add_flag("indemnity", "medium", "Indemnity language detected.")
    if "auto-renew" in low or "auto renew" in low:
        add_flag("auto_renew", "low", "Auto-renewal language detected.")
    if "net 60" in low or "net 90" in low:
        add_flag("payment_terms", "medium", f"Extended payment terms detected ({payment_terms}).")

    # Try crude line extraction
    lines = []
    # Example patterns: "Platform Subscription - $120,000", "Implementation Services: 20000"
    for ln in t.splitlines():
        if not ln.strip():
            continue
        if re.search(r"\$?\s?\d", ln) and any(k in ln.lower() for k in ["subscription", "service", "license", "support", "implementation"]):
            amt_match = re.search(r"\$?\s?(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)", ln)
            amt = _to_num(amt_match.group(1)) if amt_match else 0.0
            line_type = "services" if "implementation" in ln.lower() or "service" in ln.lower() else "subscription"
            lines.append({
                "sku": "",
                "description": ln.strip()[:160],
                "quantity": 1,
                "unit_price": amt,
                "discount_pct": 0,
                "term_months": contract_term_months or 12,
                "type": line_type,
            })

    # Nonstandard snippets
    nonstandard_hits = []
    for phrase in [
        "termination for convenience",
        "acceptance criteria",
        "acceptance",
        "net 60",
        "net 90",
        "auto-renew",
        "auto renew",
        "refund",
        "indemn",
        "unlimited liability",
    ]:
        if phrase in low:
            nonstandard_hits.append(phrase)

    nonstandard_terms = ", ".join(nonstandard_hits) if nonstandard_hits else ""

    # Deal Desk autofill payload (what /negotiation can use)
    deal_desk_autofill = {
        "customer_name": customer_name or "Extracted Customer",
        "quote_name": quote_name or "EXTRACTED-QUOTE",
        "contract_term_months": contract_term_months or 12,
        "billing_frequency": billing_frequency,
        "payment_terms": payment_terms,
        "nonstandard_terms": nonstandard_terms,
        "lines": lines[:10],  # cap to avoid noise
    }

    return {
        "source": "heuristic",
        "summary": {
            "customer_name": deal_desk_autofill["customer_name"],
            "quote_name": deal_desk_autofill["quote_name"],
            "contract_term_months": deal_desk_autofill["contract_term_months"],
            "billing_frequency": deal_desk_autofill["billing_frequency"],
            "payment_terms": deal_desk_autofill["payment_terms"],
            "estimated_gross_total": gross_total,
            "line_count_detected": len(lines),
        },
        "risk_flags": risk_flags,
        "deal_desk_autofill": deal_desk_autofill,
        "raw_extraction": {
            "amounts_found": parsed_amounts[:20],
            "nonstandard_hits": nonstandard_hits,
        },
    }


def extract_contract_view(text: str) -> Dict[str, Any]:
    if not text or not text.strip():
        raise ValueError("No text provided")

    # Always build heuristic result first (reliable fallback)
    heuristic = _heuristic_extract(text)

    if LLMGateway is None:
        return heuristic

    try:
        llm = LLMGateway()
    except Exception:
        return heuristic

    # If mock mode, keep heuristic (better than prompt-echo)
    if getattr(llm, "provider", "mock") == "mock":
        return heuristic

    # Real LLM mode: ask for JSON, then merge/fallback
    prompt = f"""
You are an enterprise contract intelligence extractor for SaaS deal desk and accounting workflows.

Extract JSON only (no markdown) with this exact top-level shape:
{{
  "source": "llm",
  "summary": {{
    "customer_name": string,
    "quote_name": string,
    "contract_term_months": number,
    "billing_frequency": string,
    "payment_terms": string,
    "estimated_gross_total": number,
    "line_count_detected": number
  }},
  "risk_flags": [
    {{"code": string, "severity": "low|medium|high", "message": string}}
  ],
  "deal_desk_autofill": {{
    "customer_name": string,
    "quote_name": string,
    "contract_term_months": number,
    "billing_frequency": string,
    "payment_terms": string,
    "nonstandard_terms": string,
    "lines": [
      {{
        "sku": string,
        "description": string,
        "quantity": number,
        "unit_price": number,
        "discount_pct": number,
        "term_months": number,
        "type": "subscription|services|support|other"
      }}
    ]
  }},
  "raw_extraction": {{
    "notes": [string]
  }}
}}

Contract text:
{text[:18000]}
""".strip()

    try:
        raw = llm.chat(prompt)
        # Try to locate JSON blob in case model adds prose
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            parsed = json.loads(raw[start:end + 1])
            # minimal sanity check
            if isinstance(parsed, dict) and "deal_desk_autofill" in parsed:
                # Merge in heuristic values where missing
                dd = parsed.get("deal_desk_autofill", {}) or {}
                hdd = heuristic.get("deal_desk_autofill", {}) or {}
                for k, v in hdd.items():
                    if dd.get(k) in [None, "", [], {}]:
                        dd[k] = v
                parsed["deal_desk_autofill"] = dd
                parsed["source"] = "llm"
                return parsed
    except Exception:
        pass

    return heuristic
