# backend/app/llm/gateway.py
from __future__ import annotations

from typing import Dict, Any
import os
import json


class LLMGateway:
    """
    Shared LLM gateway for all modules.

    Supports:
    - mock mode (default, no API key needed)
    - openai mode (real LLM)

    Environment variables:
      LLM_PROVIDER=mock | openai
      LLM_MODEL=gpt-4o-mini (or another model)
      OPENAI_API_KEY=...
    """

    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "mock").strip().lower()
        self.model = os.getenv("LLM_MODEL", "gpt-4o-mini").strip()

    # ----------------------------
    # Public methods used by services
    # ----------------------------
    def audit_memo(self, payload: Dict[str, Any]) -> str:
        """
        Used by auditor / audit summaries.
        """
        system = (
            "You are an accounting and compliance audit assistant. "
            "Summarize findings clearly, identify risks, and suggest next actions."
        )
        user = (
            "Generate a concise audit summary from this structured payload.\n\n"
            f"{json.dumps(payload, indent=2, default=str)}"
        )
        return self._complete(system=system, user=user, fallback=self._mock_audit(payload))

    def tax_memo(self, payload: Dict[str, Any]) -> str:
        """
        Optional dedicated tax memo path (ASC 740).
        """
        system = (
            "You are a technical accounting tax assistant. "
            "Write a concise ASC 740 memo with deferred tax interpretation."
        )
        user = (
            "Generate an ASC 740 memo from this structured payload.\n\n"
            f"{json.dumps(payload, indent=2, default=str)}"
        )
        return self._complete(system=system, user=user, fallback=self._mock_tax(payload))

    def forecast_commentary(self, payload: Dict[str, Any]) -> str:
        """
        Optional dedicated forecast commentary path.
        """
        system = (
            "You are a finance forecasting assistant. "
            "Summarize forecast trends, uncertainty, and practical cautions."
        )
        user = (
            "Generate a short revenue forecast commentary from this structured payload.\n\n"
            f"{json.dumps(payload, indent=2, default=str)}"
        )
        return self._complete(system=system, user=user, fallback=self._mock_forecast(payload))

    def deal_desk_memo(self, payload: Dict[str, Any], review: Dict[str, Any]) -> str:
        """
        Deal Desk AI memo (commercial + accounting + legal + rev rec aware).
        """
        system = (
            "You are an expert SaaS Deal Desk reviewer with strong knowledge of "
            "B2B pricing, approvals, legal terms, collections risk, and revenue recognition."
        )
        user = (
            "Write a concise, practical memo with these sections:\n"
            "1) Deal Summary\n"
            "2) Key Risks\n"
            "3) Recommended Changes\n"
            "4) Approval Recommendation\n"
            "5) Sales Talking Points\n\n"
            "Be specific and action-oriented. Mention rev rec implications when relevant.\n\n"
            f"Structured review:\n{json.dumps(review, indent=2, default=str)}\n\n"
            f"Deal payload:\n{json.dumps(payload, indent=2, default=str)}"
        )
        return self._complete(system=system, user=user, fallback=self._mock_deal_desk(payload, review))

    def chat(self, prompt: str) -> str:
        """
        Generic chat helper for ad hoc use by services.
        Keeps compatibility if some services call llm.chat(prompt).
        """
        system = "You are a helpful enterprise finance and accounting AI assistant."
        return self._complete(system=system, user=prompt, fallback=prompt + "\n\n(Mock mode active.)")

    # ----------------------------
    # Core completion dispatcher
    # ----------------------------
    def _complete(self, system: str, user: str, fallback: str) -> str:
        if self.provider == "mock":
            return fallback

        if self.provider == "openai":
            return self._openai_complete(system=system, user=user, fallback=fallback)

        # Unknown provider -> safe fallback
        return fallback + f"\n\n(Note: Unknown LLM_PROVIDER='{self.provider}', using mock.)"

    def _openai_complete(self, system: str, user: str, fallback: str) -> str:
        """
        Real OpenAI path.
        Requires:
          pip install openai
          OPENAI_API_KEY set
        """
        try:
            from openai import OpenAI
        except Exception:
            return fallback + "\n\n(OpenAI SDK not installed; using mock fallback.)"

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return fallback + "\n\n(OPENAI_API_KEY not set; using mock fallback.)"

        try:
            client = OpenAI(api_key=api_key)

            resp = client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )

            text = getattr(resp, "output_text", None)
            if text and str(text).strip():
                return str(text).strip()

            return fallback + "\n\n(OpenAI returned empty output; using fallback.)"

        except Exception as e:
            return fallback + f"\n\n(OpenAI call failed: {e})"

    # ----------------------------
    # Mock fallbacks (dev-safe)
    # ----------------------------
    def _mock_audit(self, payload: Dict[str, Any]) -> str:
        title = payload.get("title", "AI Auditor Summary")
        scores = payload.get("scores", {})
        notes = payload.get("notes", [])
        avg = payload.get("avg_score")

        out = [title, ""]
        if avg is not None:
            out.append(f"Overall score: {avg}")
            out.append("")

        if scores:
            out.append("Module scores:")
            for k, v in scores.items():
                out.append(f"- {k}: {v}")
            out.append("")

        if notes:
            out.append("Key observations:")
            for n in notes:
                out.append(f"- {n}")
            out.append("")

        out.append("LLM commentary is not configured, so this is a rules-based summary.")
        return "\n".join(out)

    def _mock_tax(self, payload: Dict[str, Any]) -> str:
        company = payload.get("company", "Company")
        results = payload.get("results", {})
        gross = results.get("gross", {})

        statutory_rate = results.get("statutory_rate", 0)
        try:
            statutory_rate_fmt = f"{float(statutory_rate):.2%}"
        except Exception:
            statutory_rate_fmt = str(statutory_rate)

        return (
            f"ASC 740 Memo — {company}\n\n"
            f"Statutory tax rate: {statutory_rate_fmt}\n"
            f"Gross DTL: ${gross.get('DTL', 0):,.2f} | Gross DTA: ${gross.get('DTA', 0):,.2f}\n"
            f"Valuation allowance: ${results.get('valuation_allowance', 0):,.2f}\n"
            f"Net deferred tax position: ${results.get('net_deferred_tax', 0):,.2f}\n"
            f"Reversal timing (by year): {results.get('reversal_buckets', {})}\n\n"
            "LLM commentary is not configured, so this is a rules-based summary."
        )

    def _mock_forecast(self, payload: Dict[str, Any]) -> str:
        method = payload.get("method", "unknown")
        horizon = payload.get("horizon", "n/a")
        return (
            f"Forecast commentary (mock)\n\n"
            f"Method: {method}\n"
            f"Horizon: {horizon} periods\n\n"
            "LLM commentary is not configured, so this is a rules-based summary."
        )

    def _mock_deal_desk(self, payload: Dict[str, Any], review: Dict[str, Any]) -> str:
        customer = payload.get("customer_name", "Customer")
        exceptions = review.get("exceptions", [])
        recs = review.get("recommendations", [])
        approval_path = review.get("approval_path", [])
        totals = review.get("totals", {})
        score = review.get("overall_health_score", 0)

        ex_lines = "\n".join(
            [f"- [{e.get('severity','').upper()}] {e.get('message','')}" for e in exceptions]
        ) or "- None"

        rec_lines = "\n".join([f"- {r}" for r in recs]) or "- None"
        ap_lines = " -> ".join(approval_path) if approval_path else "Sales Manager"

        return (
            f"Deal Desk AI Memo\n\n"
            f"Deal Summary\n"
            f"- Customer: {customer}\n"
            f"- Gross: {totals.get('gross_total', 0)}\n"
            f"- Net: {totals.get('net_total', 0)}\n"
            f"- Blended Discount: {totals.get('blended_discount_pct', 0)}%\n"
            f"- Overall Health Score: {score}\n\n"
            f"Key Risks\n"
            f"{ex_lines}\n\n"
            f"Recommended Changes\n"
            f"{rec_lines}\n\n"
            f"Approval Recommendation\n"
            f"- Route: {ap_lines}\n\n"
            f"Sales Talking Points\n"
            f"- Position any pricing changes around term commitment and billing structure.\n"
            f"- Clarify acceptance/termination language to avoid downstream delays.\n\n"
            f"LLM commentary is not configured, so this is a rules-based summary."
        )
