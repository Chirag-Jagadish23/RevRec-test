from sqlmodel import SQLModel, Field
from typing import Optional

class Product(SQLModel, table=True):
    code: str = Field(primary_key=True)
    name: str
    description: Optional[str] = None
