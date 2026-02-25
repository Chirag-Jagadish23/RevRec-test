from sqlmodel import SQLModel, Field
from typing import Optional, Dict, Any
from sqlalchemy import Column, JSON

class RevRecCode(SQLModel, table=True):
    code: str = Field(primary_key=True)
    rule_type: str
    # JSON storage for flexible rule parameters
    params: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class SKURevRecRule(SQLModel, table=True):
    sku: str = Field(primary_key=True)
    revrec_code: str
