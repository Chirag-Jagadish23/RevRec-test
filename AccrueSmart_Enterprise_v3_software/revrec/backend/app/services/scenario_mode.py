# backend/app/services/scenario_mode.py
from __future__ import annotations

from typing import Any, Dict, List


def _f(v: Any, d: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return d


def _i(v: Any, d: int = 0) -> int:
    try:
        return int(float(v))
    except Exception:
        return d


def _billing_factor(freq: str) -> int:
    freq = (freq or "").lower()
    if freq == "annual":
        return 1
    if freq == "quarterly":
        return 4
    return 12  # monthly default


def _build_deal_totals(payload: Dict[str, Any]) -> Dict[str, float]:
    gross = 0.0
    disc = 0.0
    net = 0.0
    subscription_net = 0.0
    services_net = 0.0

    for l in payload.get("lines", []) or []:
        qty = _f(l.get("quantity"), 0)
        price = _f(l.get("unit_price"), 0)
        discount_pct = _f(l.get("discount_pct"), 0)
        typ = str(l.get("type", "subscription")).lower()

        line_gross = qty * price
        line_disc = line_gross * (discount_pct / 100.0)
        line_net = line_gross - line_disc

        gross += line_gross
        disc += line_disc
        net += line_net

        if typ == "services":
            services_net += line_net
        else:
            subscription_net += line_net

    blended = (disc / gross * 100.0) if gross > 0 else 0.0
    return {
        "gross_total": round(gross, 2),
        "discount_value": round(disc, 2),
        "net_total": round(net, 2),
        "blended_discount_pct": round(blended, 2),
        "subscription_net": round(subscription_net, 2),
        "services_net": round(services_net, 2),
    }


def _approx_commissions_asset(net_total: float, term_months: int) -> Dict[str, float]:
    # simple enterprise-friendly approximation (can later tie to real commissions engine)
    # assume 8% commission on subscription-like value, amortized over term
    asset = net_total * 0.08
    monthly_amort = asset / max(term_months, 1)
    return {
        "commission_asset_initial": round(asset, 2),
        "commission_asset_monthly_amort": round(monthly_amort, 2),
    }


def _approx_cash_flow(net_total: float, billing_frequency: str, term_months: int) -> Dict[str, float]:
    bill_events = _billing_factor(billing_frequency)
    # approximate first-year cash collected
    if billing_frequency == "annual":
        first_year_cash = net_total * min(12, term_months) / max(term_months, 1)
        # annual often collects upfront yearly tranche
        first_year_cash *= 1.05
    elif billing_frequency == "quarterly":
        first_year_cash = net_total * min(12, term_months) / max(term_months, 1) * 1.02
    else:
        first_year_cash = net_total * min(12, term_months) / max(term_months, 1)

    return {
        "billing_events_per_year": bill_events,
        "first_year_cash_in": round(first_year_cash, 2),
        "cash_conversion_signal": "faster" if billing_frequency in ("annual", "quarterly") else "standard",
    }


def _approx_revrec_and_deferred(net_total: float, services_net: float, term_months: int, billing_frequency: str) -> Dict[str, Any]:
    # assume services recognized upfront-ish, subscription ratable
    upfront_revenue = services_net
    ratable_base = max(0.0, net_total - services_net)
    monthly_ratable = ratable_base / max(term_months, 1)

    # deferred revenue rough approximation based on billing style
    if billing_frequency == "annual":
        deferred_start = min(ratable_base, ratable_base * 12 / max(term_months, 1))
    elif billing_frequency == "quarterly":
        deferred_start = min(ratable_base, ratable_base * 3 / max(term_months, 1))
    else:
        deferred_start = monthly_ratable

    # first 6 months schedule preview
    timing = []
    remaining = ratable_base
    for m in range(1, min(7, term_months + 1)):
        rec = monthly_ratable
        remaining = max(0.0, remaining - rec)
        timing.append({
            "month": m,
            "recognized_revenue": round(rec + (upfront_revenue if m == 1 else 0.0), 2),
            "remaining_deferred_proxy": round(remaining, 2),
        })

    return {
        "monthly_ratable_revenue": round(monthly_ratable, 2),
        "upfront_services_revenue": round(upfront_revenue, 2),
        "opening_deferred_revenue_proxy": round(deferred_start, 2),
        "revenue_timing_preview": timing,
    }


def _approx_ebitda_impact(base: Dict[str, Any], scenario: Dict[str, Any]) -> Dict[str, float]:
    # Simple proxy: EBITDA affected by net revenue delta, commissions timing, and lease cost delta
    net_delta = _f(scenario["totals"]["net_total"]) - _f(base["totals"]["net_total"])
    comm_amort_delta = _f(scenario["commissions"]["commission_asset_monthly_amort"]) - _f(base["commissions"]["commission_asset_monthly_amort"])
    lease_monthly_delta = _f(scenario["lease"]["estimated_monthly_lease_cost"]) - _f(base["lease"]["estimated_monthly_lease_cost"])

    monthly_ebitda_delta = net_delta / max(_i(scenario["inputs"]["contract_term_months"], 12), 1) - comm_amort_delta - lease_monthly_delta
    return {
        "monthly_ebitda_delta_proxy": round(monthly_ebitda_delta, 2),
        "annualized_ebitda_delta_proxy": round(monthly_ebitda_delta * 12, 2),
    }


def _build_approval_path(payload: Dict[str, Any]) -> List[str]:
    steps = ["Sales Manager"]
    nonstd = (payload.get("nonstandard_terms") or "").lower()
    term = _i(payload.get("contract_term_months"), 0)
    payment_terms = str(payload.get("payment_terms") or "").lower()

    # blended discount
    totals = _build_deal_totals(payload)
    if _f(totals["blended_discount_pct"]) > 20:
        steps.append("Finance")

    if "termination for convenience" in nonstd:
        steps.append("Legal")

    if term > 24:
        steps.append("RevRec")

    if "net" in payment_terms:
        # parse days
        import re
        m = re.search(r"net\s*?(\d+)", payment_terms)
        days = int(m.group(1)) if m else 0
        if days > 45:
            steps.append("CFO")

    # dedupe order
    out: List[str] = []
    for s in steps:
        if s not in out:
            out.append(s)
    out.append("Final Approval")
    return out


def _scenario_snapshot(payload: Dict[str, Any]) -> Dict[str, Any]:
    totals = _build_deal_totals(payload)
    term_months = _i(payload.get("contract_term_months"), 12)
    billing_frequency = str(payload.get("billing_frequency") or "monthly").lower()

    revrec = _approx_revrec_and_deferred(
        net_total=totals["net_total"],
        services_net=totals["services_net"],
        term_months=term_months,
        billing_frequency=billing_frequency,
    )

    commissions = _approx_commissions_asset(
        net_total=totals["subscription_net"],
        term_months=term_months,
    )

    cash = _approx_cash_flow(
        net_total=totals["net_total"],
        billing_frequency=billing_frequency,
        term_months=term_months,
    )

    # lease + depreciation inputs (optional scenario knobs)
    lease_rate = _f(payload.get("lease_discount_rate_annual", 0.06))
    useful_life_months = _i(payload.get("fixed_asset_useful_life_months", 36))
    fixed_asset_cost = _f(payload.get("fixed_asset_cost", 0.0))
    fixed_asset_salvage = _f(payload.get("fixed_asset_salvage_value", 0.0))

    depreciable_basis = max(0.0, fixed_asset_cost - fixed_asset_salvage)
    dep_monthly = depreciable_basis / max(useful_life_months, 1)

    lease = {
        "lease_discount_rate_annual": round(lease_rate, 4),
        "estimated_monthly_lease_cost": round(10000 * lease_rate / 12.0, 2),  # proxy
    }

    fixed_assets = {
        "useful_life_months": useful_life_months,
        "monthly_depreciation_proxy": round(dep_monthly, 2),
    }

    approvals = _build_approval_path(payload)

    snap = {
        "inputs": {
            "contract_term_months": term_months,
            "billing_frequency": billing_frequency,
            "lease_discount_rate_annual": lease_rate,
            "fixed_asset_useful_life_months": useful_life_months,
        },
        "totals": totals,
        "revrec": revrec,
        "commissions": commissions,
        "cash_flow": cash,
        "lease": lease,
        "fixed_assets": fixed_assets,
        "approval_path": approvals,
    }
    return snap


def run_scenario(base_payload: Dict[str, Any], changes: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply scenario changes to a deal-like payload and return baseline vs scenario + impact deltas.
    """
    base = dict(base_payload or {})
    scenario_payload = dict(base_payload or {})

    # Top-level changes
    for k in [
        "contract_term_months",
        "billing_frequency",
        "payment_terms",
        "currency",
        "nonstandard_terms",
        "lease_discount_rate_annual",
        "fixed_asset_useful_life_months",
        "fixed_asset_cost",
        "fixed_asset_salvage_value",
    ]:
        if k in changes:
            scenario_payload[k] = changes[k]

    # Line-level updates (e.g. discount change)
    line_changes = changes.get("line_changes") or []
    orig_lines = list(scenario_payload.get("lines") or [])
    new_lines = []
    for idx, line in enumerate(orig_lines):
        updated = dict(line)
        for lc in line_changes:
            target_idx = lc.get("index")
            sku = lc.get("sku")
            if (target_idx is not None and int(target_idx) == idx) or (sku and sku == line.get("sku")):
                for field in ["discount_pct", "term_months", "unit_price", "quantity", "type", "description"]:
                    if field in lc:
                        updated[field] = lc[field]
        new_lines.append(updated)
    scenario_payload["lines"] = new_lines

    base_snap = _scenario_snapshot(base)
    scenario_snap = _scenario_snapshot(scenario_payload)

    delta = {
        "net_total_delta": round(scenario_snap["totals"]["net_total"] - base_snap["totals"]["net_total"], 2),
        "discount_value_delta": round(scenario_snap["totals"]["discount_value"] - base_snap["totals"]["discount_value"], 2),
        "opening_deferred_revenue_delta": round(
            scenario_snap["revrec"]["opening_deferred_revenue_proxy"] - base_snap["revrec"]["opening_deferred_revenue_proxy"], 2
        ),
        "commission_asset_delta": round(
            scenario_snap["commissions"]["commission_asset_initial"] - base_snap["commissions"]["commission_asset_initial"], 2
        ),
        "commission_amort_monthly_delta": round(
            scenario_snap["commissions"]["commission_asset_monthly_amort"] - base_snap["commissions"]["commission_asset_monthly_amort"], 2
        ),
        "first_year_cash_delta": round(
            scenario_snap["cash_flow"]["first_year_cash_in"] - base_snap["cash_flow"]["first_year_cash_in"], 2
        ),
        "lease_monthly_cost_delta": round(
            scenario_snap["lease"]["estimated_monthly_lease_cost"] - base_snap["lease"]["estimated_monthly_lease_cost"], 2
        ),
        "depreciation_monthly_delta": round(
            scenario_snap["fixed_assets"]["monthly_depreciation_proxy"] - base_snap["fixed_assets"]["monthly_depreciation_proxy"], 2
        ),
        "approval_path_changed": scenario_snap["approval_path"] != base_snap["approval_path"],
    }

    ebitda = _approx_ebitda_impact(base_snap, scenario_snap)

    return {
        "status": "ok",
        "baseline": base_snap,
        "scenario": scenario_snap,
        "delta": delta,
        "ebitda": ebitda,
        "explanation": [
            "Revenue timing and deferred revenue are proxy estimates until connected to live revrec schedules.",
            "Commission asset impact is estimated using an 8% commission proxy on subscription net value.",
            "Lease and depreciation impacts are scenario proxies unless linked to live lease/fixed-asset schedules.",
        ],
    }
