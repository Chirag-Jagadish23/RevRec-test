
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import date

class AccountingPeriod(SQLModel, table=True):
    period: str = Field(primary_key=True)  # YYYY-MM
    start_date: date
    end_date: date
    status: str = "open"  # open, closed, locked
    closed_at: Optional[date] = None
