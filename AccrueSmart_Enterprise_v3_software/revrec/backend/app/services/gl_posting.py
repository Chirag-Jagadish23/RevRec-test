from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlmodel import Session, select

from ..models_enterprise import (
    PostingRule,
    COAMapping,
    PeriodLock,
    JournalBatch,
    JournalLine,
    PostingAuditLog,
)


def _hash_line(batch_id: str, line_no: int, account_code: str, debit: float, credit: float, source_ref: str) -> str:
    raw = f"{batch_id}|{line_no}|{account_code}|{debit:.2f}|{credit:.2f}|{source_ref}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _get_period_lock(session: Session, entity_code: str, period_key: str) -> Optional[PeriodLock]:
    return session.exec(
        select(PeriodLock).where(PeriodLock.entity_code == entity_code, PeriodLock.period_key == period_key)
    ).first()


def ensure_default_posting_rules(session: Session) -> Dict[str, Any]:
    existing = session.exec(select(PostingRule)).all()
    if existing:
        return {"status": "ok", "seeded": 0, "message": "Posting rules already exist"}

    rows = [
        PostingRule(source_type="revrec", rule_name="RevRec Revenue", debit_account_code="4000", credit_account_code="2050", amount_field="amount", memo_template="RevRec recognition"),
        PostingRule(source_type="lease", rule_name="Lease Expense", debit_account_code="6100", credit_account_code="2200", amount_field="amount", memo_template="Lease amortization"),
        PostingRule(source_type="depreciation", rule_name="Depreciation", debit_account_code="6200", credit_account_code="1501", amount_field="amount", memo_template="Fixed asset depreciation"),
        PostingRule(source_type="commission", rule_name="Commission Amortization", debit_account_code="6300", credit_account_code="1605", amount_field="amount", memo_template="Commission amortization"),
    ]
    for r in rows:
        session.add(r)
    session.commit()
    return {"status": "ok", "seeded": len(rows)}


def upsert_coa_mapping(
    session: Session,
    entity_code: str,
    logical_key: str,
    account_code: str,
    account_name: str = "",
    geography: str = "GLOBAL",
    product_family: str = "DEFAULT",
) -> Dict[str, Any]:
    row = session.exec(
        select(COAMapping).where(
            COAMapping.entity_code == entity_code,
            COAMapping.logical_key == logical_key,
            COAMapping.geography == geography,
            COAMapping.product_family == product_family,
        )
    ).first()

    if not row:
        row = COAMapping(
            entity_code=entity_code,
            logical_key=logical_key,
            account_code=account_code,
            account_name=account_name,
            geography=geography,
            product_family=product_family,
        )
    else:
        row.account_code = account_code
        row.account_name = account_name

    session.add(row)
    session.commit()
    session.refresh(row)

    return {
        "id": row.id,
        "entity_code": row.entity_code,
        "logical_key": row.logical_key,
        "account_code": row.account_code,
        "account_name": row.account_name,
    }


def set_period_lock(session: Session, entity_code: str, period_key: str, is_locked: bool, actor: str = "system") -> Dict[str, Any]:
    row = _get_period_lock(session, entity_code, period_key)
    if not row:
        row = PeriodLock(entity_code=entity_code, period_key=period_key, is_locked=is_locked)

    row.is_locked = is_locked
    if is_locked:
        row.locked_by = actor
        row.locked_at = datetime.utcnow()
    else:
        row.locked_by = ""
        row.locked_at = None

    session.add(row)
    session.commit()
    session.refresh(row)

    return {
        "status": "ok",
        "entity_code": entity_code,
        "period_key": period_key,
        "is_locked": row.is_locked,
        "locked_by": row.locked_by,
    }


def _build_lines_from_source(
    source_type: str,
    source_payload: Dict[str, Any],
    rule: PostingRule,
) -> List[Dict[str, Any]]:
    """
    source_payload supports:
    {
      "entity_code": "US_PARENT",
      "period_key": "2026-01",
      "source_ref": "REVREC-BATCH-001",
      "items": [{"line_ref":"1","amount":1000.0}, ...]
    }
    """
    items = source_payload.get("items") or []
    out = []

    for i, item in enumerate(items, start=1):
        amt = float(item.get(rule.amount_field, 0) or 0)
        if amt == 0:
            continue

        memo = item.get("memo") or rule.memo_template or f"{source_type} posting"

        out.append({
            "line_no": i * 2 - 1,
            "account_code": rule.debit_account_code,
            "debit": amt,
            "credit": 0.0,
            "memo": memo,
            "source_line_ref": str(item.get("line_ref") or i),
        })
        out.append({
            "line_no": i * 2,
            "account_code": rule.credit_account_code,
            "debit": 0.0,
            "credit": amt,
            "memo": memo,
            "source_line_ref": str(item.get("line_ref") or i),
        })

    return out


def preview_posting(
    session: Session,
    source_type: str,
    source_payload: Dict[str, Any],
    actor: str = "system",
) -> Dict[str, Any]:
    entity_code = source_payload.get("entity_code") or "US_PARENT"
    period_key = source_payload.get("period_key") or "2026-01"
    source_ref = source_payload.get("source_ref") or f"{source_type}-preview"

    lock = _get_period_lock(session, entity_code, period_key)
    if lock and lock.is_locked:
        raise ValueError(f"Period {period_key} is locked for entity {entity_code}")

    rule = session.exec(
        select(PostingRule).where(PostingRule.source_type == source_type, PostingRule.active == True)
    ).first()
    if not rule:
        raise ValueError(f"No active posting rule for source_type '{source_type}'")

    batch_id = f"JE-{source_type.upper()}-{entity_code}-{period_key}-{int(datetime.utcnow().timestamp())}"

    raw_lines = _build_lines_from_source(source_type, source_payload, rule)
    if not raw_lines:
        raise ValueError("No posting lines generated (check source payload items/amounts)")

    total_debits = round(sum(float(x["debit"]) for x in raw_lines), 2)
    total_credits = round(sum(float(x["credit"]) for x in raw_lines), 2)
    if total_debits != total_credits:
        raise ValueError(f"Unbalanced journal preview: debits={total_debits}, credits={total_credits}")

    batch = JournalBatch(
        batch_id=batch_id,
        entity_code=entity_code,
        period_key=period_key,
        source_type=source_type,
        source_ref=source_ref,
        status="preview",
        total_debits=total_debits,
        total_credits=total_credits,
        memo=source_payload.get("memo") or f"{source_type} journal preview",
    )
    session.add(batch)
    session.commit()
    session.refresh(batch)

    created_lines = []
    for x in raw_lines:
        line = JournalLine(
            batch_id=batch.batch_id,
            line_no=int(x["line_no"]),
            account_code=x["account_code"],
            account_name="",
            debit=round(float(x["debit"]), 2),
            credit=round(float(x["credit"]), 2),
            memo=x["memo"],
            source_type=source_type,
            source_ref=source_ref,
            source_line_ref=x["source_line_ref"],
            immutable_hash=_hash_line(batch.batch_id, int(x["line_no"]), x["account_code"], float(x["debit"]), float(x["credit"]), source_ref),
        )
        session.add(line)
        created_lines.append(line)

    session.add(PostingAuditLog(batch_id=batch.batch_id, action="preview", actor=actor, message="Journal preview created"))
    session.commit()

    return get_journal_batch_detail(session, batch.batch_id)


def post_batch(session: Session, batch_id: str, actor: str = "system") -> Dict[str, Any]:
    batch = session.exec(select(JournalBatch).where(JournalBatch.batch_id == batch_id)).first()
    if not batch:
        raise ValueError("Batch not found")

    lock = _get_period_lock(session, batch.entity_code, batch.period_key)
    if lock and lock.is_locked:
        raise ValueError(f"Period {batch.period_key} is locked for entity {batch.entity_code}")

    if batch.status == "posted":
        return {"status": "ok", "batch_id": batch_id, "message": "Already posted"}

    batch.status = "posted"
    batch.posted_by = actor
    batch.posted_at = datetime.utcnow()
    session.add(batch)
    session.add(PostingAuditLog(batch_id=batch.batch_id, action="post", actor=actor, message="Batch posted"))
    session.commit()

    return get_journal_batch_detail(session, batch.batch_id)


def unpost_batch(session: Session, batch_id: str, actor: str = "system") -> Dict[str, Any]:
    batch = session.exec(select(JournalBatch).where(JournalBatch.batch_id == batch_id)).first()
    if not batch:
        raise ValueError("Batch not found")

    if batch.status != "posted":
        raise ValueError("Only posted batches can be unposted")

    batch.status = "unposted"
    batch.unposted_by = actor
    batch.unposted_at = datetime.utcnow()
    session.add(batch)
    session.add(PostingAuditLog(batch_id=batch.batch_id, action="unpost", actor=actor, message="Batch unposted"))
    session.commit()

    return get_journal_batch_detail(session, batch.batch_id)


def repost_batch(session: Session, batch_id: str, actor: str = "system") -> Dict[str, Any]:
    batch = session.exec(select(JournalBatch).where(JournalBatch.batch_id == batch_id)).first()
    if not batch:
        raise ValueError("Batch not found")

    if batch.status != "unposted":
        raise ValueError("Only unposted batches can be reposted")

    batch.status = "posted"
    batch.posted_by = actor
    batch.posted_at = datetime.utcnow()
    session.add(batch)
    session.add(PostingAuditLog(batch_id=batch.batch_id, action="repost", actor=actor, message="Batch reposted"))
    session.commit()

    return get_journal_batch_detail(session, batch.batch_id)


def get_journal_batch_detail(session: Session, batch_id: str) -> Dict[str, Any]:
    batch = session.exec(select(JournalBatch).where(JournalBatch.batch_id == batch_id)).first()
    if not batch:
        raise ValueError("Batch not found")

    lines = session.exec(select(JournalLine).where(JournalLine.batch_id == batch_id)).all()
    audits = session.exec(select(PostingAuditLog).where(PostingAuditLog.batch_id == batch_id)).all()

    return {
        "status": "ok",
        "batch": {
            "batch_id": batch.batch_id,
            "entity_code": batch.entity_code,
            "period_key": batch.period_key,
            "source_type": batch.source_type,
            "source_ref": batch.source_ref,
            "batch_status": batch.status,
            "total_debits": batch.total_debits,
            "total_credits": batch.total_credits,
            "memo": batch.memo,
            "posted_by": batch.posted_by,
            "posted_at": batch.posted_at.isoformat() if batch.posted_at else None,
        },
        "lines": [
            {
                "line_no": l.line_no,
                "account_code": l.account_code,
                "debit": l.debit,
                "credit": l.credit,
                "memo": l.memo,
                "source_ref": l.source_ref,
                "source_line_ref": l.source_line_ref,
                "immutable_hash": l.immutable_hash,
            }
            for l in sorted(lines, key=lambda x: x.line_no)
        ],
        "audit_trail": [
            {
                "action": a.action,
                "actor": a.actor,
                "message": a.message,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in audits
        ],
    }
