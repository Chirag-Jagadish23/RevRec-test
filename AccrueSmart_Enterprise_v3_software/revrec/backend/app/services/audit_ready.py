# backend/app/services/audit_ready.py
from __future__ import annotations

from typing import Any, Dict, List
from datetime import datetime

try:
    from ..llm.gateway import LLMGateway
except Exception:
    LLMGateway = None


def _mk_ref(doc_type: str, doc_id: str, title: str) -> Dict[str, Any]:
    return {
        "doc_type": doc_type,
        "doc_id": doc_id,
        "title": title,
    }


def build_audit_ready_package(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build an audit-ready close package shell from available module payloads.
    Accepts payload structure like:
    {
      "period": "2026-01",
      "company": "DemoCo",
      "modules": {
         "revrec": {...},
         "leases": {...},
         "tax": {...},
         "fixed_assets": {...},
         "commissions": {...},
         "deal_desk": {...},
         "audit_log": {...}
      }
    }
    """
    period = payload.get("period", "unknown-period")
    company = payload.get("company", "Unknown Company")
    modules = payload.get("modules", {}) or {}

    refs: List[Dict[str, Any]] = []
    exceptions: List[Dict[str, Any]] = []
    rollforwards: List[Dict[str, Any]] = []
    supporting_schedules: List[Dict[str, Any]] = []
    memos: List[Dict[str, Any]] = []

    # RevRec
    revrec = modules.get("revrec")
    if revrec:
        supporting_schedules.append({"name": "Revenue Recognition Schedule", "module": "revrec"})
        rollforwards.append({"name": "Deferred Revenue Rollforward", "module": "revrec"})
        refs.append(_mk_ref("schedule", "revrec", "RevRec Schedule Export"))
        memos.append({"title": "ASC 606 Revenue Memo", "module": "revrec"})
    else:
        exceptions.append({"module": "revrec", "severity": "medium", "message": "RevRec payload missing from close package input."})

    # Leases
    leases = modules.get("leases")
    if leases:
        supporting_schedules.append({"name": "Lease Amortization Schedule", "module": "leases"})
        rollforwards.append({"name": "ROU Asset / Lease Liability Rollforward", "module": "leases"})
        refs.append(_mk_ref("schedule", "leases", "Lease Schedule Export"))
        memos.append({"title": "ASC 842 Lease Memo", "module": "leases"})
    else:
        exceptions.append({"module": "leases", "severity": "low", "message": "Lease payload not provided."})

    # Fixed Assets
    fa = modules.get("fixed_assets")
    if fa:
        supporting_schedules.append({"name": "Fixed Asset Depreciation Schedule", "module": "fixed_assets"})
        rollforwards.append({"name": "Fixed Asset / Accumulated Depreciation Rollforward", "module": "fixed_assets"})
        refs.append(_mk_ref("schedule", "fixed_assets", "Fixed Asset Depreciation Export"))
        memos.append({"title": "Fixed Assets & Depreciation Memo", "module": "fixed_assets"})
    else:
        exceptions.append({"module": "fixed_assets", "severity": "low", "message": "Fixed assets payload not provided."})

    # Tax
    tax = modules.get("tax")
    if tax:
        supporting_schedules.append({"name": "Deferred Tax Mapping", "module": "tax"})
        rollforwards.append({"name": "Deferred Tax Rollforward", "module": "tax"})
        refs.append(_mk_ref("calc", "tax", "ASC 740 Deferred Tax Calculation"))
        memos.append({"title": "ASC 740 Tax Memo", "module": "tax"})
    else:
        exceptions.append({"module": "tax", "severity": "medium", "message": "Tax payload missing from close package input."})

    # Commissions
    comm = modules.get("commissions")
    if comm:
        supporting_schedules.append({"name": "Commission Asset Amortization", "module": "commissions"})
        rollforwards.append({"name": "Deferred Commission Asset Rollforward", "module": "commissions"})
        refs.append(_mk_ref("schedule", "commissions", "Commissions Schedule Export"))

    # Audit log
    audit_log = modules.get("audit_log")
    if audit_log:
        refs.append(_mk_ref("extract", "audit_log", "Audit Trail Extract"))
    else:
        exceptions.append({"module": "audit_log", "severity": "low", "message": "Audit log extract not provided."})

    # Source document references (contracts, invoices, etc.)
    src_docs = payload.get("source_documents", []) or []
    source_doc_refs = []
    for d in src_docs:
        source_doc_refs.append({
            "source_type": d.get("source_type", "document"),
            "source_id": d.get("source_id"),
            "name": d.get("name"),
            "link": d.get("link"),
        })

    # Narrative package summary
    summary_memo = None
    if LLMGateway is not None:
        try:
            llm = LLMGateway()
            summary_memo = llm.audit_memo({
                "title": "Period Close Audit-Ready Package",
                "company": company,
                "period": period,
                "scores": {
                    "supporting_schedules": 100 if supporting_schedules else 0,
                    "rollforwards": 100 if rollforwards else 0,
                    "exceptions": max(0, 100 - 10 * len(exceptions)),
                },
                "notes": [
                    f"Generated close package for {company} ({period})",
                    f"{len(supporting_schedules)} supporting schedules",
                    f"{len(rollforwards)} rollforwards",
                    f"{len(exceptions)} exceptions/warnings",
                    f"{len(source_doc_refs)} source document references",
                ],
                "avg_score": 90 if len(exceptions) <= 2 else 75,
            })
        except Exception:
            summary_memo = None

    if not summary_memo:
        summary_memo = (
            f"Audit-Ready Package generated for {company} ({period}).\n"
            f"- Supporting schedules: {len(supporting_schedules)}\n"
            f"- Rollforwards: {len(rollforwards)}\n"
            f"- Exception reports: {len(exceptions)}\n"
            f"- Source document references: {len(source_doc_refs)}\n"
            "This package is rules-based and can be upgraded to include LLM-authored technical memos."
        )

    return {
        "status": "ok",
        "company": company,
        "period": period,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "period_close_package": {
            "checklist": [
                "Trial balance tie-out",
                "Subledger reconciliations",
                "RevRec review",
                "Lease review",
                "Fixed assets depreciation review",
                "Tax review",
                "Management review",
            ],
            "supporting_schedules": supporting_schedules,
            "rollforwards": rollforwards,
            "exception_reports": exceptions,
            "audit_trail_extracts": [r for r in refs if r["doc_type"] == "extract"],
            "source_document_references": source_doc_refs,
            "memos": memos,
            "all_references": refs,
        },
        "summary_memo": summary_memo,
    }
