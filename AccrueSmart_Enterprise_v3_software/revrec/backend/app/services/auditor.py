from __future__ import annotations
from typing import Dict, Any

try:
    from ..llm.gateway import LLMGateway
except Exception:
    LLMGateway = None


def summarize_audit(findings: Dict[str, Any]) -> Dict[str, Any]:
    """
    Aggregate schedules and generate narrative commentary via LLM (if available).
    """
    scores: Dict[str, float] = {}
    notes = []

    for k, v in findings.items():
        if not v:
            scores[k] = 0
            notes.append(f"{k}: missing data.")
            continue

        if isinstance(v, dict) and "errors" in v:
            scores[k] = 40
            notes.append(f"{k}: found {len(v['errors'])} error(s).")

        # ASC 842 lease payload
        elif isinstance(v, dict) and "total_interest" in v and "rows" in v:
            scores[k] = 90
            notes.append(f"{k}: lease schedule OK ({len(v.get('rows', []))} rows).")

        # ASC 740 tax payload
        elif isinstance(v, dict) and "gross" in v and "net_deferred_tax" in v:
            scores[k] = 85
            notes.append(f"{k}: deferred tax calculated.")

        # Forecast payload
        elif isinstance(v, dict) and "forecast" in v:
            scores[k] = 80
            notes.append(f"{k}: forecast generated ({len(v.get('forecast', {}))} periods).")
        # Fixed Assets depreciation payload  <-- NEW
        elif isinstance(v, dict) and "asset_id" in v and "rows" in v and "summary" in v:
            scores[k] = 88
            notes.append(f"{k}: fixed asset depreciation schedule OK ({len(v.get('rows', []))} rows).")


        # RevRec / schedules / contract payloads
        elif isinstance(v, list):
            scores[k] = 78
            notes.append(f"{k}: received {len(v)} row(s).")

        elif isinstance(v, dict) and ("rows" in v or "schedule" in v or "schedules" in v):
            row_count = 0
            if isinstance(v.get("rows"), list):
                row_count = len(v["rows"])
            scores[k] = 82
            notes.append(f"{k}: schedule data available ({row_count} rows).")

        else:
            scores[k] = 70
            notes.append(f"{k}: generic OK.")

    avg = round(sum(scores.values()) / len(scores), 1) if scores else 0

    payload = {
        "title": "AI Auditor Summary",
        "scores": scores,
        "notes": notes,
        "avg_score": avg,
    }

    memo = None
    if LLMGateway is not None:
        try:
            llm = LLMGateway()
            memo = llm.audit_memo(payload)
        except Exception:
            memo = None

    if not memo:
        module_lines = "\n".join([f"- {m}: {s}" for m, s in scores.items()])
        note_lines = "\n".join([f"- {n}" for n in notes])

        memo = (
            f"AI Auditor Summary\n\n"
            f"Overall score: {avg}\n\n"
            f"Module scores:\n{module_lines}\n\n"
            f"Key observations:\n{note_lines}\n\n"
            f"LLM commentary is not configured, so this is a rules-based summary."
        )

    return {
        "avg_score": avg,
        "scores": scores,
        "notes": notes,
        "summary_memo": memo,
    }
