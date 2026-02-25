
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class JournalBatch(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    period: str
    created_at: datetime
    source: str

class JournalLine(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    batch_id: int
    account: str
    debit: float = 0
    credit: float = 0
    memo: Optional[str] = None
    contract_id: Optional[str] = None
