from __future__ import annotations

from datetime import datetime, date
from typing import Optional

from sqlmodel import SQLModel, Field


# ----------------------------
# CLOSE ORCHESTRATOR MODELS
# ----------------------------
class CloseTemplate(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    entity_code: str = Field(index=True)
    task_code: str = Field(index=True)
    task_name: str
    day_offset: int = 0  # D+0, D+1, D+2...
    owner_role: str = "accounting"
    depends_on_csv: str = ""  # comma-separated task_code values
    module_key: str = ""      # e.g. contracts, revrec, tax, leases
    auto_check_type: str = "" # e.g. contracts_posted, revrec_generated
    required: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CloseRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    entity_code: str = Field(index=True)
    period_key: str = Field(index=True)   # e.g. 2026-01
    status: str = "open"                  # open / blocked / ready_to_close / closed
    close_day: int = 0                    # D+0, D+1, etc.
    started_by: str = "system"
    started_at: datetime = Field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None
    ai_summary: str = ""


class CloseTask(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    close_run_id: int = Field(index=True)
    entity_code: str = Field(index=True)
    period_key: str = Field(index=True)

    task_code: str = Field(index=True)
    task_name: str
    day_offset: int = 0
    owner_role: str = "accounting"
    owner_user: str = ""
    depends_on_csv: str = ""
    module_key: str = ""
    auto_check_type: str = ""

    status: str = "not_started"  # not_started / blocked / in_progress / complete / failed
    auto_status: str = "unknown"  # unknown / ready / complete / blocked / failed
    blocker_reason: str = ""
    notes: str = ""

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ----------------------------
# GL POSTING / SUBLEDGER MODELS
# ----------------------------
class PostingRule(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source_type: str = Field(index=True)  # revrec, lease, depreciation, commission
    rule_name: str
    debit_account_code: str
    credit_account_code: str
    amount_field: str = "amount"
    memo_template: str = ""
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class COAMapping(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    entity_code: str = Field(index=True)
    geography: str = Field(default="GLOBAL", index=True)
    product_family: str = Field(default="DEFAULT", index=True)

    logical_key: str = Field(index=True)  # e.g. REV_SUBSCRIPTION, DEFERRED_REVENUE, LEASE_EXPENSE
    account_code: str
    account_name: str = ""


class PeriodLock(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    entity_code: str = Field(index=True)
    period_key: str = Field(index=True)
    is_locked: bool = False
    locked_by: str = ""
    locked_at: Optional[datetime] = None


class JournalBatch(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    batch_id: str = Field(index=True, unique=True)
    entity_code: str = Field(index=True)
    period_key: str = Field(index=True)
    source_type: str = Field(index=True)
    source_ref: str = Field(index=True)

    status: str = "preview"  # preview / posted / unposted
    total_debits: float = 0.0
    total_credits: float = 0.0
    memo: str = ""

    posted_by: str = ""
    posted_at: Optional[datetime] = None
    unposted_by: str = ""
    unposted_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class JournalLine(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    batch_id: str = Field(index=True)
    line_no: int = 1

    account_code: str = Field(index=True)
    account_name: str = ""
    debit: float = 0.0
    credit: float = 0.0
    memo: str = ""
    source_type: str = ""
    source_ref: str = ""
    source_line_ref: str = ""
    immutable_hash: str = ""  # simple integrity hash


class PostingAuditLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    batch_id: str = Field(index=True)
    action: str  # preview / post / unpost / repost
    actor: str = "system"
    message: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
