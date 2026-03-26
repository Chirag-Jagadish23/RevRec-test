# backend/app/services/close_orchestrator.py
from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from datetime import datetime

from sqlalchemy import text
from sqlmodel import Session


# ----------------------------
# Low-level DB helpers
# ----------------------------
def _extract_scalar(row: Any, default: Any = 0) -> Any:
    """
    Safely extract the first scalar value from SQLAlchemy/SQLModel row results.
    Handles:
    - SQLAlchemy Row
    - tuple/list
    - scalar primitives
    """
    if row is None:
        return default

    # Already a scalar
    if isinstance(row, (int, float, str, bool)):
        return row

    # SQLAlchemy Row / tuple-like
    try:
        return row[0]
    except Exception:
        pass

    # Iterable fallback
    try:
        vals = list(row)
        if vals:
            return vals[0]
    except Exception:
        pass

    return default


def _table_exists(session: Session, table_name: str) -> bool:
    q = text("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename=:t")
    row = session.exec(q, params={"t": table_name}).first()
    return bool(_extract_scalar(row, None))


def _safe_scalar(
    session: Session,
    sql: str,
    params: Optional[Dict[str, Any]] = None,
    default: Any = 0,
) -> Any:
    try:
        row = session.exec(text(sql), params=params or {}).first()
        return _extract_scalar(row, default)
    except Exception:
        return default


def _safe_rows(session: Session, sql: str, params: Optional[Dict[str, Any]] = None) -> List[Any]:
    try:
        rows = session.exec(text(sql), params=params or {}).all()
        return list(rows or [])
    except Exception:
        return []


def _count_rows(session: Session, table_name: str) -> int:
    if not _table_exists(session, table_name):
        return 0
    val = _safe_scalar(session, f"SELECT COUNT(*) FROM {table_name}", default=0)
    try:
        return int(val or 0)
    except Exception:
        return 0


def _count_query(session: Session, sql: str, params: Optional[Dict[str, Any]] = None) -> int:
    val = _safe_scalar(session, sql, params=params, default=0)
    try:
        return int(val or 0)
    except Exception:
        return 0


# ----------------------------
# Deadline computation
# ----------------------------
def _compute_deadline(period_key: str, day_bucket: str) -> Optional[date]:
    """
    Compute the D+N deadline date for a task.
    period_key = "YYYY-MM"; day_bucket = "D+1" | "D+2" | "D+3"
    Returns the calendar date by which the task should be done.
    """
    try:
        year, month = int(period_key[:4]), int(period_key[5:7])
        last_day = calendar.monthrange(year, month)[1]
        period_end = date(year, month, last_day)
        n = int(day_bucket.split("+")[1])
        return period_end + timedelta(days=n)
    except Exception:
        return None


# ----------------------------
# Manual override loader
# ----------------------------
def _load_task_overrides(session: Session, period_key: str, entity_id: str) -> Dict[str, Dict[str, Any]]:
    """Load manual task status overrides from close_task_overrides table."""
    if not _table_exists(session, "close_task_overrides"):
        return {}

    rows = _safe_rows(
        session,
        "SELECT task_id, status, notes, updated_at FROM close_task_overrides "
        "WHERE period_key = :pk AND entity_id = :eid",
        {"pk": period_key, "eid": entity_id},
    )

    result: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        try:
            m = dict(r._mapping)
            result[m["task_id"]] = m
            continue
        except Exception:
            pass
        if isinstance(r, (tuple, list)) and len(r) >= 2:
            result[r[0]] = {"task_id": r[0], "status": r[1], "notes": r[2] if len(r) > 2 else None, "updated_at": r[3] if len(r) > 3 else None}
    return result


# ----------------------------
# Auto-status (real system state)
# ----------------------------
def _mock_system_state(session: Session, period_key: str, entity_id: str = "US_PARENT") -> Dict[str, Any]:
    """
    Kept function name for compatibility, but now returns REAL state derived from DB tables.
    """

    contracts_posted_count = _count_rows(session, "contracts")
    revrec_rows_count = _count_rows(session, "schedule_rows")
    commissions_count = _count_rows(session, "commissions")
    leases_count = _count_rows(session, "leases")
    fixed_assets_count = _count_rows(session, "fixed_assets")
    tax_rows_count = _count_rows(session, "tax_entries") if _table_exists(session, "tax_entries") else _count_rows(session, "tax")

    gl_batches_count = _count_rows(session, "gl_batches")
    gl_entries_count = _count_rows(session, "gl_entries")
    audit_log_count = _count_rows(session, "audit_log")

    gl_posted_by_source = {
        "revrec": False,
        "leases": False,
        "depreciation": False,
        "commissions": False,
        "tax": False,
    }

    if _table_exists(session, "gl_batches"):
        for src in gl_posted_by_source.keys():
            for source_col in ["source_type", "source", "module"]:
                for posted_col in ["status", "is_posted", "posted"]:
                    sql = None
                    if posted_col == "status":
                        sql = f"""
                            SELECT COUNT(*) FROM gl_batches
                            WHERE lower({source_col}) = :src
                              AND lower(status) IN ('posted','finalized','complete')
                        """
                    else:
                        sql = f"""
                            SELECT COUNT(*) FROM gl_batches
                            WHERE lower({source_col}) = :src
                              AND COALESCE({posted_col}, 0) = 1
                        """

                    cnt = _count_query(session, sql, {"src": src})
                    if cnt > 0:
                        gl_posted_by_source[src] = True
                        break

                if gl_posted_by_source[src]:
                    break

    if gl_batches_count == 0 and gl_entries_count > 0:
        gl_posted_by_source["revrec"] = revrec_rows_count > 0
        gl_posted_by_source["leases"] = leases_count > 0
        gl_posted_by_source["depreciation"] = fixed_assets_count > 0
        gl_posted_by_source["commissions"] = commissions_count > 0
        gl_posted_by_source["tax"] = tax_rows_count > 0

    tax_complete = bool(tax_rows_count > 0 and (gl_posted_by_source["tax"] or gl_batches_count > 0))

    period_locked = False
    if _table_exists(session, "period_locks"):
        for col_entity in ["entity_id", "entity", "legal_entity"]:
            for col_period in ["period_key", "period", "close_period"]:
                for col_lock in ["is_locked", "locked", "status"]:
                    if col_lock == "status":
                        sql = f"""
                            SELECT COUNT(*) FROM period_locks
                            WHERE {col_entity} = :entity_id
                              AND {col_period} = :period_key
                              AND lower(status) IN ('locked','closed')
                        """
                    else:
                        sql = f"""
                            SELECT COUNT(*) FROM period_locks
                            WHERE {col_entity} = :entity_id
                              AND {col_period} = :period_key
                              AND COALESCE({col_lock}, 0) = 1
                        """

                    cnt = _count_query(session, sql, {"entity_id": entity_id, "period_key": period_key})
                    if cnt > 0:
                        period_locked = True
                        break

                if period_locked:
                    break
            if period_locked:
                break

    return {
        "as_of": datetime.utcnow().isoformat(),
        "period_key": period_key,
        "entity_id": entity_id,
        "contracts_posted": contracts_posted_count > 0,
        "contracts_posted_count": contracts_posted_count,
        "revrec_schedules_exist": revrec_rows_count > 0,
        "revrec_schedules_count": revrec_rows_count,
        "commissions_run": commissions_count > 0,
        "commissions_count": commissions_count,
        "leases_run": leases_count > 0,
        "leases_count": leases_count,
        "depreciation_run": fixed_assets_count > 0,
        "fixed_assets_count": fixed_assets_count,
        "gl_batches_posted_by_source": gl_posted_by_source,
        "gl_batches_count": gl_batches_count,
        "gl_entries_count": gl_entries_count,
        "tax_complete": tax_complete,
        "tax_rows_count": tax_rows_count,
        "period_locked": period_locked,
        "audit_log_count": audit_log_count,
    }


# ----------------------------
# Close task templates + dependency graph
# ----------------------------
def _close_task_templates(entity_id: str) -> List[Dict[str, Any]]:
    common = [
        {"task_id": "contracts_post", "title": "Post contracts", "day_bucket": "D+1", "owner_role": "Revenue Ops"},
        {"task_id": "revrec_generate", "title": "Generate rev rec schedules", "day_bucket": "D+1", "owner_role": "Revenue Accounting"},
        {"task_id": "commissions_run", "title": "Run commission capitalization/amortization", "day_bucket": "D+1", "owner_role": "Sales Finance"},
        {"task_id": "leases_run", "title": "Run lease amortization", "day_bucket": "D+1", "owner_role": "Corporate Accounting"},
        {"task_id": "depr_run", "title": "Run fixed asset depreciation", "day_bucket": "D+1", "owner_role": "Corporate Accounting"},
        {"task_id": "gl_post_subledgers", "title": "Post subledger batches to GL", "day_bucket": "D+2", "owner_role": "GL Accounting"},
        {"task_id": "tax_finalize", "title": "Finalize tax provision inputs", "day_bucket": "D+2", "owner_role": "Tax"},
        {"task_id": "close_review", "title": "Controller close review", "day_bucket": "D+3", "owner_role": "Controller"},
        {"task_id": "cfo_signoff", "title": "CFO sign-off", "day_bucket": "D+3", "owner_role": "CFO"},
    ]

    if entity_id.upper() != "US_PARENT":
        common.append(
            {"task_id": "ic_confirm", "title": "Confirm intercompany balances", "day_bucket": "D+2", "owner_role": "Intercompany"}
        )

    return common


def _dependency_edges(entity_id: str) -> List[Dict[str, str]]:
    deps = [
        {"task_id": "revrec_generate", "depends_on": "contracts_post"},
        {"task_id": "commissions_run", "depends_on": "contracts_post"},
        {"task_id": "gl_post_subledgers", "depends_on": "revrec_generate"},
        {"task_id": "gl_post_subledgers", "depends_on": "leases_run"},
        {"task_id": "gl_post_subledgers", "depends_on": "depr_run"},
        {"task_id": "gl_post_subledgers", "depends_on": "commissions_run"},
        {"task_id": "tax_finalize", "depends_on": "gl_post_subledgers"},
        {"task_id": "close_review", "depends_on": "tax_finalize"},
        {"task_id": "cfo_signoff", "depends_on": "close_review"},
    ]
    if entity_id.upper() != "US_PARENT":
        deps.append({"task_id": "close_review", "depends_on": "ic_confirm"})
    return deps


def _auto_done(task_id: str, state: Dict[str, Any]) -> bool:
    """Returns True if system data indicates this task is complete."""
    source_flags = state.get("gl_batches_posted_by_source", {}) or {}
    mapping = {
        "contracts_post": bool(state.get("contracts_posted")),
        "revrec_generate": bool(state.get("revrec_schedules_exist")),
        "commissions_run": bool(state.get("commissions_run")),
        "leases_run": bool(state.get("leases_run")),
        "depr_run": bool(state.get("depreciation_run")),
        "gl_post_subledgers": all([
            bool(source_flags.get("revrec")),
            bool(source_flags.get("leases")),
            bool(source_flags.get("depreciation")),
            bool(source_flags.get("commissions")),
        ]) or (state.get("gl_batches_count", 0) > 0 and state.get("gl_entries_count", 0) > 0),
        "tax_finalize": bool(state.get("tax_complete")),
        "close_review": bool(state.get("tax_complete")) and bool(state.get("gl_entries_count", 0) > 0),
        "cfo_signoff": bool(state.get("period_locked")),
        "ic_confirm": True if state.get("entity_id", "").upper() == "US_PARENT" else False,
    }
    return mapping.get(task_id, False)


def _compute_blockers(tasks: List[Dict[str, Any]], deps: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    task_map = {t["task_id"]: t for t in tasks}
    blockers: List[Dict[str, Any]] = []

    for d in deps:
        t = task_map.get(d["task_id"])
        p = task_map.get(d["depends_on"])
        if not t or not p:
            continue

        if t["status"] != "done" and p["status"] != "done":
            blockers.append(
                {
                    "task_id": t["task_id"],
                    "task_title": t["title"],
                    "blocked_by_task_id": p["task_id"],
                    "blocked_by_title": p["title"],
                    "owner": t.get("owner"),
                    "severity": "high" if t["day_bucket"] in ("D+1", "D+2") else "medium",
                }
            )

    return blockers


def _ai_close_manager_summary(tasks: List[Dict[str, Any]], blockers: List[Dict[str, Any]], state: Dict[str, Any]) -> str:
    pending = [t for t in tasks if t["status"] != "done"]
    overdue = [t for t in tasks if t["status"] == "overdue"]
    top_blockers = blockers[:3]

    if not pending:
        return f"Close is on track. All tasks auto-completed from system state for {state.get('entity_id')} {state.get('period_key')}."

    lines = []
    lines.append(f"{len(pending)} tasks remain for {state.get('entity_id')} {state.get('period_key')}.")

    if overdue:
        lines.append(f"{len(overdue)} task(s) are OVERDUE: {', '.join(t['title'] for t in overdue)}.")

    if top_blockers:
        lines.append(f"{len(blockers)} blocker(s) detected. Top blockers:")
        for b in top_blockers:
            lines.append(f"- {b['task_title']} is blocked by {b['blocked_by_title']} (owner: {b.get('owner') or 'Unassigned'})")
    else:
        lines.append("No explicit blockers detected; remaining tasks are waiting on source data to populate.")
    return " ".join(lines)


def build_close_dashboard(session: Session, period_key: str, entity_id: str = "US_PARENT") -> Dict[str, Any]:
    state = _mock_system_state(session, period_key=period_key, entity_id=entity_id)
    templates = _close_task_templates(entity_id)
    deps = _dependency_edges(entity_id)
    today = date.today()

    # Step 1: auto done/not-done for each task
    done_map: Dict[str, bool] = {t["task_id"]: _auto_done(t["task_id"], state) for t in templates}

    # Step 2: build dep map: task_id → [depends_on task_ids]
    dep_map: Dict[str, List[str]] = {}
    for d in deps:
        dep_map.setdefault(d["task_id"], []).append(d["depends_on"])

    # Step 3: load manual overrides from DB
    overrides = _load_task_overrides(session, period_key, entity_id)

    # Step 4: compute final status for each task
    tasks: List[Dict[str, Any]] = []
    for t in templates:
        task_id = t["task_id"]
        is_done = done_map[task_id]

        if is_done:
            status = "done"
            reason = "Auto-completed from system state"
        else:
            # Check which dependencies are not yet done
            my_deps = dep_map.get(task_id, [])
            unmet_deps = [d for d in my_deps if not done_map.get(d, False)]

            if unmet_deps:
                status = "blocked"
                reason = f"Waiting on: {', '.join(unmet_deps)}"
            else:
                status = "in_progress"
                reason = "Dependencies met — waiting on source data"

            # Overdue: past D+N deadline and still not done
            deadline = _compute_deadline(period_key, t["day_bucket"])
            if deadline and today > deadline:
                status = "overdue"
                reason = f"Past deadline ({deadline.isoformat()}) — was {status}"

            # Apply manual override (never overrides auto "done"; can override overdue too)
            if task_id in overrides:
                ov = overrides[task_id]
                if ov.get("status") in ("in_progress", "blocked", "pending"):
                    status = ov["status"]
                    reason = ov.get("notes") or reason

        tasks.append({
            **t,
            "owner": t.get("owner_role"),
            "status": status,
            "status_reason": reason,
            "deadline": _compute_deadline(period_key, t["day_bucket"]).isoformat() if _compute_deadline(period_key, t["day_bucket"]) else None,
            "override": overrides.get(task_id),
        })

    blockers = _compute_blockers(tasks, deps)
    ai_summary = _ai_close_manager_summary(tasks, blockers, state)

    by_day = {
        "D+1": [t for t in tasks if t["day_bucket"] == "D+1"],
        "D+2": [t for t in tasks if t["day_bucket"] == "D+2"],
        "D+3": [t for t in tasks if t["day_bucket"] == "D+3"],
    }

    return {
        "status": "ok",
        "period_key": period_key,
        "entity_id": entity_id,
        "system_state": state,
        "dependencies": deps,
        "tasks": tasks,
        "by_day": by_day,
        "blockers": blockers,
        "ai_close_manager_summary": ai_summary,
    }


# ----------------------------
# Close Package Generator
# ----------------------------
def _rollforwards_from_state(state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "revenue_rollforward": {
            "contracts_posted_count": state.get("contracts_posted_count", 0),
            "revrec_schedules_count": state.get("revrec_schedules_count", 0),
            "gl_posted_revrec": bool((state.get("gl_batches_posted_by_source") or {}).get("revrec")),
        },
        "commissions_rollforward": {
            "commissions_runs": state.get("commissions_count", 0),
            "gl_posted_commissions": bool((state.get("gl_batches_posted_by_source") or {}).get("commissions")),
        },
        "leases_rollforward": {
            "lease_records": state.get("leases_count", 0),
            "gl_posted_leases": bool((state.get("gl_batches_posted_by_source") or {}).get("leases")),
        },
        "fixed_assets_rollforward": {
            "asset_records": state.get("fixed_assets_count", 0),
            "gl_posted_depreciation": bool((state.get("gl_batches_posted_by_source") or {}).get("depreciation")),
        },
        "tax_rollforward": {
            "tax_rows_count": state.get("tax_rows_count", 0),
            "tax_complete": bool(state.get("tax_complete")),
            "gl_posted_tax": bool((state.get("gl_batches_posted_by_source") or {}).get("tax")),
        },
    }


def _exception_summary(dashboard: Dict[str, Any]) -> Dict[str, Any]:
    blockers = dashboard.get("blockers", []) or []
    tasks = dashboard.get("tasks", []) or []
    pending = [t for t in tasks if t.get("status") != "done"]
    overdue = [t for t in tasks if t.get("status") == "overdue"]

    return {
        "blocker_count": len(blockers),
        "pending_task_count": len(pending),
        "overdue_task_count": len(overdue),
        "high_severity_blockers": [b for b in blockers if b.get("severity") == "high"],
        "overdue_tasks": [
            {"task_id": t.get("task_id"), "title": t.get("title"), "deadline": t.get("deadline")}
            for t in overdue
        ],
        "pending_tasks": [
            {
                "task_id": t.get("task_id"),
                "title": t.get("title"),
                "day_bucket": t.get("day_bucket"),
                "owner": t.get("owner"),
                "status": t.get("status"),
            }
            for t in pending
        ],
    }


def _source_refs(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {"source": "contracts", "present": state.get("contracts_posted"), "count": state.get("contracts_posted_count", 0)},
        {"source": "schedule_rows", "present": state.get("revrec_schedules_exist"), "count": state.get("revrec_schedules_count", 0)},
        {"source": "commissions", "present": state.get("commissions_run"), "count": state.get("commissions_count", 0)},
        {"source": "leases", "present": state.get("leases_run"), "count": state.get("leases_count", 0)},
        {"source": "fixed_assets", "present": state.get("depreciation_run"), "count": state.get("fixed_assets_count", 0)},
        {"source": "gl_batches", "present": state.get("gl_batches_count", 0) > 0, "count": state.get("gl_batches_count", 0)},
        {"source": "gl_entries", "present": state.get("gl_entries_count", 0) > 0, "count": state.get("gl_entries_count", 0)},
        {"source": "tax", "present": state.get("tax_rows_count", 0) > 0, "count": state.get("tax_rows_count", 0)},
        {"source": "audit_log", "present": state.get("audit_log_count", 0) > 0, "count": state.get("audit_log_count", 0)},
    ]


def _audit_trail_extracts(session: Session, limit: int = 50) -> List[Dict[str, Any]]:
    if not _table_exists(session, "audit_log"):
        return []

    rows = _safe_rows(
        session,
        "SELECT * FROM audit_log ORDER BY id DESC LIMIT :n",
        {"n": int(limit)},
    )

    extracts: List[Dict[str, Any]] = []
    for r in rows:
        try:
            mapping = dict(r._mapping)
            extracts.append(mapping)
            continue
        except Exception:
            pass

        if isinstance(r, (tuple, list)):
            extracts.append({"row": [str(x) for x in r]})
        else:
            extracts.append({"row": str(r)})

    return extracts


def _close_memo(dashboard: Dict[str, Any], exceptions: Dict[str, Any]) -> str:
    state = dashboard.get("system_state", {}) or {}
    lines = []
    lines.append("Period Close Package Memo")
    lines.append("")
    lines.append(f"Entity: {dashboard.get('entity_id')}")
    lines.append(f"Period: {dashboard.get('period_key')}")
    lines.append(f"As of: {state.get('as_of')}")
    lines.append("")
    lines.append("Close readiness summary:")
    lines.append(f"- Contracts posted: {'Yes' if state.get('contracts_posted') else 'No'}")
    lines.append(f"- RevRec schedules exist: {'Yes' if state.get('revrec_schedules_exist') else 'No'}")
    lines.append(f"- Commissions run: {'Yes' if state.get('commissions_run') else 'No'}")
    lines.append(f"- Leases run: {'Yes' if state.get('leases_run') else 'No'}")
    lines.append(f"- Depreciation run: {'Yes' if state.get('depreciation_run') else 'No'}")
    lines.append(f"- Tax complete: {'Yes' if state.get('tax_complete') else 'No'}")
    lines.append(f"- Period locked: {'Yes' if state.get('period_locked') else 'No'}")
    lines.append("")
    lines.append(f"Pending tasks: {exceptions.get('pending_task_count', 0)}")
    lines.append(f"Overdue tasks: {exceptions.get('overdue_task_count', 0)}")
    lines.append(f"Blockers: {exceptions.get('blocker_count', 0)}")
    if exceptions.get("overdue_tasks"):
        lines.append("Overdue:")
        for t in exceptions["overdue_tasks"][:5]:
            lines.append(f"- {t.get('title')} (deadline: {t.get('deadline')})")
    if exceptions.get("high_severity_blockers"):
        lines.append("High severity blockers:")
        for b in exceptions["high_severity_blockers"][:5]:
            lines.append(f"- {b.get('task_title')} blocked by {b.get('blocked_by_title')}")
    lines.append("")
    lines.append("AI Close Manager:")
    lines.append(dashboard.get("ai_close_manager_summary", "No summary generated."))
    return "\n".join(lines)


def generate_close_package(session: Session, period_key: str, entity_id: str = "US_PARENT") -> Dict[str, Any]:
    dashboard = build_close_dashboard(session, period_key=period_key, entity_id=entity_id)
    state = dashboard.get("system_state", {}) or {}

    rollforwards = _rollforwards_from_state(state)
    exceptions = _exception_summary(dashboard)
    memo = _close_memo(dashboard, exceptions)
    source_refs = _source_refs(state)
    audit_extracts = _audit_trail_extracts(session, limit=50)

    return {
        "status": "ok",
        "period_key": period_key,
        "entity_id": entity_id,
        "rollforwards": rollforwards,
        "exception_summary": exceptions,
        "memo": memo,
        "source_refs": source_refs,
        "audit_trail_extracts": audit_extracts,
    }
