from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import date

class ContractRecord(SQLModel, table=True):
    contract_id: str = Field(primary_key=True)
    customer: Optional[str] = None
    transaction_price: float = 0

    start_date: Optional[date] = None
    end_date: Optional[date] = None
    currency: str = "USD"
    entity: Optional[str] = None

    lines: List["ContractLine"] = Relationship(back_populates="contract")


class ContractLine(SQLModel, table=True):
    id: Optional[int] = Field(primary_key=True)
    contract_id: str = Field(foreign_key="contractrecord.contract_id")
    sku: str
    amount: float

    contract: Optional[ContractRecord] = Relationship(back_populates="lines")
