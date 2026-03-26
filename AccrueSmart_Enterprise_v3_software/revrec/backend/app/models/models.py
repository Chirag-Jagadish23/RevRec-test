from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import date, datetime


# -------------------------------------------------------------
# PRODUCT CATALOG
# -------------------------------------------------------------
class Product(SQLModel, table=True):
    __tablename__ = "products"

    product_code: str = Field(primary_key=True)
    name: str
    ssp: float
    revrec_code: str = Field(default="STRAIGHT_LINE")

    # relationship to SKU rules
    # sku_rule: Optional["SKURevRecRule"] = Relationship(back_populates="product")


# -------------------------------------------------------------
# REVREC RULE DEFINITIONS
# -------------------------------------------------------------
class RevRecCode(SQLModel, table=True):
    __tablename__ = "revrec_codes"

    code: str = Field(primary_key=True)
    description: Optional[str] = None
    rule_type: str = "straight_line"


# -------------------------------------------------------------
# CONTRACT HEADER
# -------------------------------------------------------------
class ContractRecord(SQLModel, table=True):
    __tablename__ = "contracts"

    contract_id: str = Field(primary_key=True)
    customer: str
    transaction_price: float

    start_date: date
    end_date: date

    lines: List["ContractLine"] = Relationship(back_populates="contract")


# -------------------------------------------------------------
# CONTRACT LINE ITEMS (SSP SNAPSHOTS)
# -------------------------------------------------------------
class ContractLine(SQLModel, table=True):
    __tablename__ = "contract_lines"

    id: Optional[int] = Field(default=None, primary_key=True)
    contract_id: str = Field(foreign_key="contracts.contract_id")
    product_code: str = Field(foreign_key="products.product_code")

    # snapshot values (ASC-606 requirement)
    ssp: float
    revrec_code: str
    override_price: float

    contract: Optional[ContractRecord] = Relationship(back_populates="lines")


# -------------------------------------------------------------
# MONTHLY SCHEDULE ROWS (with audit-friendly adjustments)
# -------------------------------------------------------------
class ScheduleRow(SQLModel, table=True):
    __tablename__ = "schedule_rows"

    id: Optional[int] = Field(default=None, primary_key=True)

    # keep FK to contract for traceability
    contract_id: str = Field(foreign_key="contracts.contract_id", index=True)

    # product code is usually present, but allow optional for rare manual rows if needed
    product_code: Optional[str] = Field(default=None, index=True)

    # YYYY-MM
    period: str = Field(index=True)

    # positive = revenue recognized; negative = refund/reversal, etc.
    amount: float

    # allocated | ai | manual | adjustment_refund | adjustment_delay | adjustment_true_up
    source: str = Field(default="manual", index=True)

    # --- NEW audit fields ---
    # recognition | refund | delay | true_up
    event_type: str = Field(default="recognition", index=True)

    # True when row was inserted as an adjustment (refund/delay/true-up)
    is_adjustment: bool = Field(default=False, index=True)

    # Human-readable explanation for audit trail
    notes: Optional[str] = None

    # Optional date string (YYYY-MM-DD) for when adjustment became effective
    effective_date: Optional[str] = None

    # Optional link to another row (future use for explicit row-to-row traceability)
    reference_row_id: Optional[int] = Field(default=None, index=True)


# -------------------------------------------------------------
# MILESTONES (for milestone rule_type revenue recognition)
# -------------------------------------------------------------
class Milestone(SQLModel, table=True):
    __tablename__ = "milestones"

    id: Optional[int] = Field(default=None, primary_key=True)
    contract_id: str = Field(foreign_key="contracts.contract_id", index=True)
    product_code: str = Field(index=True)

    # Date when the milestone is achieved / revenue recognized (YYYY-MM-DD)
    milestone_date: str

    # Amount to recognize when this milestone is locked
    amount: float

    # Human-readable description of the milestone event
    description: Optional[str] = None

    # Whether this milestone has been confirmed/locked by the user
    is_locked: bool = Field(default=False)

    # ISO datetime string of when it was locked
    locked_at: Optional[str] = None


# -------------------------------------------------------------
# CONTRACT MODIFICATIONS (ASC 606 amendment history)
# -------------------------------------------------------------
class ContractModification(SQLModel, table=True):
    __tablename__ = "contract_modifications"

    id: Optional[int] = Field(default=None, primary_key=True)
    contract_id: str = Field(foreign_key="contracts.contract_id", index=True)

    # ISO datetime when the amendment was recorded
    modified_at: str

    # "price_change" | "add_product" | "remove_product" | "other"
    change_type: str = Field(default="other")

    # "prospective" | "cumulative_catch_up"
    treatment: str = Field(default="prospective")

    # YYYY-MM-DD — the date from which new terms apply
    effective_date: str

    # Full JSON snapshots of {header, lines} before and after the change
    snapshot_before: str
    snapshot_after: str

    # Optional human-readable description of what changed and why
    notes: Optional[str] = None
