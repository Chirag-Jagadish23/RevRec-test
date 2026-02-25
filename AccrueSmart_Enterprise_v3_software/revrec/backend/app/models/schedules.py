from sqlmodel import SQLModel, Field
from typing import Optional

class ScheduleRow(SQLModel, table=True):
    id: Optional[int] = Field(primary_key=True)
    contract_id: str
    line_no: int
    period: str
    amount: float
    product_code: Optional[str] = None
    revrec_code: Optional[str] = None
    source: str = "engine"
