# backend/app/routers/contracts.py
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from sqlmodel import Session, select
from sqlalchemy import delete

from ..auth import require
from ..db import get_session
from ..models.models import ContractRecord, ContractLine, Product
from ..services.allocation_service import allocate_contract
from ..services.revrec_engine import build_schedule
from ..services.schedule_service import save_schedule_rows

router = APIRouter(prefix="/contracts", tags=["contracts"])


# ---------------- DATE PARSER ----------------
def parse_date(d: str):
    try:
        return datetime.strptime(d, "%Y-%m-%d").date()
    except Exception:
        raise HTTPException(400, f"Invalid date format: {d}")


# ---------------- LIST CONTRACTS (NEW) ----------------
@router.get("")
@require(perms=["contracts.view"])
def list_contracts(session: Session = Depends(get_session)):
    """
    Returns a lightweight list for dropdowns / auditor page.
    Stable keys:
      - contract_id
      - contract_name (fallback to customer if no explicit name field)
      - customer
    """
    rows = session.exec(select(ContractRecord)).all()

    result = []
    for c in rows:
        # If your model later adds contract_name, this will use it automatically.
        contract_name = getattr(c, "contract_name", None) or c.customer or c.contract_id

        result.append(
            {
                "contract_id": c.contract_id,
                "contract_name": contract_name,
                "customer": c.customer,
                "transaction_price": float(c.transaction_price or 0),
                "start_date": c.start_date.isoformat() if c.start_date else None,
                "end_date": c.end_date.isoformat() if c.end_date else None,
            }
        )

    # Optional: sort newest-ish by ID (or replace with created_at later)
    result.sort(key=lambda x: str(x["contract_id"]))
    return result


# ---------------- GET CONTRACT ----------------
@router.get("/{contract_id}")
def load_contract(contract_id: str, session: Session = Depends(get_session)):
    contract = session.get(ContractRecord, contract_id)
    if not contract:
        raise HTTPException(404, "Contract not found")

    lines = session.exec(
        select(ContractLine).where(ContractLine.contract_id == contract_id)
    ).all()

    return {
        "contract_id": contract.contract_id,
        "customer": contract.customer,
        "transaction_price": contract.transaction_price,
        "start_date": contract.start_date.isoformat(),
        "end_date": contract.end_date.isoformat(),
        "lines": [
            {"product_code": l.product_code, "amount": l.override_price}
            for l in lines
        ],
    }


# ---------------- SAVE CONTRACT ----------------
@router.post("/save")
def save_contract(payload: dict, session: Session = Depends(get_session)):
    cid = payload.get("contract_id")
    if not cid:
        raise HTTPException(400, "Missing contract_id")

    customer = payload.get("customer", "")
    transaction_price = payload.get("transaction_price")
    start_date_raw = payload.get("start_date")
    end_date_raw = payload.get("end_date")
    line_items = payload.get("lines", [])

    if transaction_price is None:
        raise HTTPException(400, "Missing transaction_price")
    if not start_date_raw or not end_date_raw:
        raise HTTPException(400, "Missing start_date or end_date")
    if not isinstance(line_items, list):
        raise HTTPException(400, "lines must be an array")

    # Parse dates
    start = parse_date(start_date_raw)
    end = parse_date(end_date_raw)

    # Upsert contract header
    contract = session.get(ContractRecord, cid)
    if not contract:
        contract = ContractRecord(
            contract_id=cid,
            customer=customer,
            transaction_price=float(transaction_price),
            start_date=start,
            end_date=end,
        )
        session.add(contract)
    else:
        contract.customer = customer
        contract.transaction_price = float(transaction_price)
        contract.start_date = start
        contract.end_date = end

    # Delete old lines
    session.exec(delete(ContractLine).where(ContractLine.contract_id == cid))

    # Insert new lines using Product snapshots
    for item in line_items:
        code = item.get("product_code")
        amount = item.get("amount")

        if not code:
            raise HTTPException(400, "Each line must include product_code")
        if amount is None:
            raise HTTPException(400, f"Missing amount for product {code}")

        product = session.get(Product, code)
        if not product:
            raise HTTPException(400, f"Product {code} not found")

        session.add(
            ContractLine(
                contract_id=cid,
                product_code=code,
                ssp=product.ssp,                   # snapshot SSP
                revrec_code=product.revrec_code,   # snapshot revrec rule
                override_price=float(amount),      # selling price from contract
            )
        )

    session.commit()
    return {"status": "saved", "contract_id": cid}


# ---------------- ALLOCATE REVENUE ----------------
@router.post("/allocate")
def allocate(payload: dict, session: Session = Depends(get_session)):
    cid = payload.get("contract_id")
    if not cid:
        raise HTTPException(400, "Missing contract_id")

    contract = session.get(ContractRecord, cid)
    if not contract:
        raise HTTPException(404, "Contract not found")

    lines = session.exec(
        select(ContractLine).where(ContractLine.contract_id == cid)
    ).all()

    if not lines:
        raise HTTPException(400, "No line items to allocate")

    # Allocation math + schedule generation
    allocations = allocate_contract(contract, lines, session)
    schedule = build_schedule(contract, allocations, session)

    # Persist schedule rows
    save_schedule_rows(cid, schedule, session)

    return {
        "status": "allocated",
        "contract_id": cid,
        "allocations": allocations,
        "schedule": schedule,
    }
