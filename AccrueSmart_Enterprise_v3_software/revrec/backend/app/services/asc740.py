from __future__ import annotations
from typing import Dict, List, Optional
from dataclasses import dataclass

try:
    from ..llm.gateway import LLMGateway
except Exception:
    LLMGateway = None


@dataclass
class TempDiff:
    """
    Temporary difference for ASC 740.

    amount = book basis - tax basis
      > 0 : taxable temporary difference (creates DTL)
      < 0 : deductible temporary difference (creates DTA)
    """
    label: str                  # e.g. "Depreciation"
    period: str                 # e.g. "2026-12"
    amount: float               # book basis - tax basis
    reversal_year: int          # disclosure bucket
    va_pct: float = 0.0         # row-level valuation allowance, only applies to DTA rows


def _validate_rate(name: str, value: float):
    if value < 0 or value > 1:
        raise ValueError(f"{name} must be between 0 and 1")


def _blended_rate(federal_rate: float, state_rate: float, state_deductible_federal: bool = True) -> float:
    """
    Common blended tax rate:
      if state tax deductible for federal:
        blended = fed + state * (1 - fed)
      else:
        blended = fed + state
    """
    if state_deductible_federal:
        return federal_rate + state_rate * (1 - federal_rate)
    return federal_rate + state_rate


def compute_deferred_tax(
    differences: List[TempDiff],
    statutory_rate: Optional[float] = None,
    valuation_allowance_pct: float = 0.0,   # legacy global VA fallback
    federal_rate: Optional[float] = None,
    state_rate: float = 0.0,
    use_blended_rate: bool = False,
    state_deductible_federal: bool = True,
    beginning_net_deferred_tax: float = 0.0,   # for rollforward
    pretax_book_income: Optional[float] = None,  # for ETR bridge
) -> Dict:
    """
    ASC 740 deferred tax engine (v2)

    Supports:
      - row-level VA (va_pct on each temp diff row)
      - global VA fallback if row va_pct not provided
      - federal/state/blended rates
      - rollforward payload
      - simple ETR bridge payload
    """

    # --- rate selection ---
    if use_blended_rate:
        if federal_rate is None:
            raise ValueError("federal_rate is required when use_blended_rate=True")
        _validate_rate("federal_rate", federal_rate)
        _validate_rate("state_rate", state_rate)
        tax_rate = _blended_rate(federal_rate, state_rate, state_deductible_federal)
        _validate_rate("blended tax rate", tax_rate)
        rate_mode = "blended"
    else:
        if statutory_rate is None:
            raise ValueError("statutory_rate is required when use_blended_rate=False")
        _validate_rate("statutory_rate", statutory_rate)
        tax_rate = statutory_rate
        rate_mode = "statutory"

    _validate_rate("valuation_allowance_pct", valuation_allowance_pct)

    # --- row mapping ---
    mapping = []
    gross_dtl = 0.0
    gross_dta = 0.0
    row_level_va_total = 0.0
    reversal_buckets: Dict[int, float] = {}

    for d in differences:
        # tolerate missing/blank label
        label = (d.label or "").strip() or "Unlabeled Temp Difference"

        # validate row VA
        row_va_pct = d.va_pct if d.va_pct is not None else valuation_allowance_pct
        _validate_rate(f"va_pct for {label}", float(row_va_pct))

        amt = float(d.amount)
        deferred_tax_signed = round(amt * tax_rate, 2)

        if amt > 0:
            row_type = "DTL"
            gross_dtl += amt * tax_rate
            row_va = 0.0
            deferred_tax_display = round(abs(amt) * tax_rate, 2)
            net_effect = -deferred_tax_display  # net DTL impact (negative)
        elif amt < 0:
            row_type = "DTA"
            gross_dta_row = abs(amt) * tax_rate
            gross_dta += gross_dta_row
            row_va = round(gross_dta_row * row_va_pct, 2)
            row_level_va_total += row_va
            deferred_tax_display = round(gross_dta_row, 2)
            net_effect = round(gross_dta_row - row_va, 2)  # net DTA impact (positive)
        else:
            row_type = "NONE"
            row_va = 0.0
            deferred_tax_display = 0.0
            net_effect = 0.0

        reversal_buckets[d.reversal_year] = reversal_buckets.get(d.reversal_year, 0.0) + amt

        mapping.append({
            "label": label,
            "period": d.period,
            "temp_diff": round(amt, 2),
            "reversal_year": d.reversal_year,
            "type": row_type,
            "tax_rate_used": round(tax_rate, 6),
            "deferred_tax": deferred_tax_display,             # always positive display amount
            "deferred_tax_signed": deferred_tax_signed,       # sign-preserving
            "va_pct": round(float(row_va_pct), 6),
            "valuation_allowance": row_va,                    # row-level VA dollars
            "net_deferred_tax_effect": round(net_effect, 2),  # +DTA net, -DTL net
        })

    gross = {
        "DTL": round(gross_dtl, 2),
        "DTA": round(gross_dta, 2),
    }

    valuation_allowance = round(row_level_va_total, 2)
    net_deferred_tax = round(gross["DTA"] - valuation_allowance - gross["DTL"], 2)
    # Positive => net DTA, Negative => net DTL

    reversal_buckets = {yr: round(val, 2) for yr, val in sorted(reversal_buckets.items())}

    # --- rollforward ---
    current_period_activity = round(net_deferred_tax - float(beginning_net_deferred_tax), 2)
    rollforward = {
        "beginning_net_deferred_tax": round(float(beginning_net_deferred_tax), 2),
        "current_period_activity": current_period_activity,
        "ending_net_deferred_tax": net_deferred_tax,
    }

    # --- simple ETR bridge (optional) ---
    etr_bridge = None
    if pretax_book_income is not None:
        pbi = float(pretax_book_income)
        statutory_tax_expense = round(pbi * tax_rate, 2)
        va_impact = round(valuation_allowance, 2)

        # Simplified bridge (analytics/presentation only; not full tax provision engine)
        etr_bridge = {
            "pretax_book_income": round(pbi, 2),
            "rate_used": round(tax_rate, 6),
            "expected_tax_at_rate": statutory_tax_expense,
            "valuation_allowance_impact": va_impact,
            "deferred_tax_net_position": net_deferred_tax,
            "illustrative_total_tax_expense": round(statutory_tax_expense + va_impact, 2),
        }

    return {
        "rate_mode": rate_mode,
        "tax_rate_used": round(tax_rate, 6),
        "federal_rate": federal_rate,
        "state_rate": state_rate,
        "state_deductible_federal": state_deductible_federal,
        "gross": gross,
        "valuation_allowance": valuation_allowance,
        "net_deferred_tax": net_deferred_tax,
        "reversal_buckets": reversal_buckets,
        "mapping": mapping,
        "rollforward": rollforward,
        "etr_bridge": etr_bridge,
    }


def ai_tax_memo(company: str, results: Dict) -> str:
    """
    Use LLM if configured, otherwise fallback to deterministic memo text.
    """
    payload = {
        "company": company,
        "results": results,
        "module": "ASC740",
    }

    if LLMGateway is not None:
        try:
            llm = LLMGateway()
            # adjust method name if your gateway uses a different one
            memo = llm.audit_memo(payload)
            if memo:
                return memo
        except Exception:
            pass

    gross = results.get("gross", {})
    rf = results.get("rollforward", {})
    etr = results.get("etr_bridge")

    text = (
        f"ASC 740 Memo — {company}\n\n"
        f"Rate mode: {results.get('rate_mode')} | Tax rate used: {results.get('tax_rate_used', 0):.2%}\n"
        f"Gross DTL: ${gross.get('DTL', 0):,.2f} | Gross DTA: ${gross.get('DTA', 0):,.2f}\n"
        f"Valuation allowance: ${results.get('valuation_allowance', 0):,.2f}\n"
        f"Net deferred tax position: ${results.get('net_deferred_tax', 0):,.2f}\n"
        f"Reversal timing (by year): {results.get('reversal_buckets', {})}\n\n"
        f"Rollforward — Beginning: ${rf.get('beginning_net_deferred_tax', 0):,.2f}, "
        f"Activity: ${rf.get('current_period_activity', 0):,.2f}, "
        f"Ending: ${rf.get('ending_net_deferred_tax', 0):,.2f}\n\n"
    )

    if etr:
        text += (
            "ETR Bridge (illustrative):\n"
            f"- Pretax book income: ${etr.get('pretax_book_income', 0):,.2f}\n"
            f"- Expected tax at rate: ${etr.get('expected_tax_at_rate', 0):,.2f}\n"
            f"- Valuation allowance impact: ${etr.get('valuation_allowance_impact', 0):,.2f}\n"
            f"- Illustrative total tax expense: ${etr.get('illustrative_total_tax_expense', 0):,.2f}\n\n"
        )

    text += (
        "Judgment: The valuation allowance reflects management’s assessment of realizability of deferred tax assets "
        "based on available evidence, including forecasted taxable income and reversal patterns.\n\n"
        "Conclusion: Deferred taxes are measured and presented in accordance with ASC 740."
    )

    return text
