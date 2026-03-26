# backend/app/routers/contracts.py
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from datetime import datetime
from sqlmodel import Session, select
from sqlalchemy import delete

from ..auth import require
from ..db import get_session
from ..models.models import ContractRecord, ContractLine, ContractModification, Product, ScheduleRow
from ..services.allocation_service import allocate_contract
from ..services.revrec_engine import build_schedule
from ..services.schedule_service import save_schedule_rows, post_catchup_row

router = APIRouter(prefix="/contracts", tags=["contracts"])


# ---------------- DATE PARSER ----------------
def parse_date(d: str):
    try:
        return datetime.strptime(d, "%Y-%m-%d").date()
    except Exception:
        raise HTTPException(400, f"Invalid date format: {d}")


# ---------------- LIST CONTRACTS ----------------
@router.get("")
@require(perms=["contracts.view"])
def list_contracts(
    session: Session = Depends(get_session),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None, description="Filter by contract ID or customer name"),
):
    """
    Paginated contract list for dropdowns and search.
    Returns {items, total, limit, offset}.
    """
    query = select(ContractRecord)

    if search:
        term = f"%{search}%"
        query = query.where(
            (ContractRecord.contract_id.like(term)) |
            (ContractRecord.customer.like(term))
        )

    all_matching = session.exec(query).all()
    total = len(all_matching)

    # Sort by contract_id, then paginate
    all_matching.sort(key=lambda c: str(c.contract_id))
    page = all_matching[offset: offset + limit]

    items = [
        {
            "contract_id": c.contract_id,
            "contract_name": getattr(c, "contract_name", None) or c.customer or c.contract_id,
            "customer": c.customer,
            "transaction_price": float(c.transaction_price or 0),
            "start_date": c.start_date.isoformat() if c.start_date else None,
            "end_date": c.end_date.isoformat() if c.end_date else None,
        }
        for c in page
    ]

    return {"items": items, "total": total, "limit": limit, "offset": offset}


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


# ---------------- MODIFY CONTRACT (amendment with history) ----------------
@router.post("/{contract_id}/modify")
def modify_contract(contract_id: str, payload: dict, session: Session = Depends(get_session)):
    """Record an ASC 606 contract amendment with full before/after snapshot."""
    contract = session.get(ContractRecord, contract_id)
    if not contract:
        raise HTTPException(404, "Contract not found")

    effective_date = payload.get("effective_date")
    if not effective_date:
        raise HTTPException(400, "effective_date is required for contract modifications")

    treatment = payload.get("treatment", "prospective")
    change_type = payload.get("change_type", "other")
    notes = payload.get("notes")

    # --- Capture BEFORE snapshot ---
    old_lines = session.exec(
        select(ContractLine).where(ContractLine.contract_id == contract_id)
    ).all()
    snapshot_before = json.dumps({
        "header": {
            "customer": contract.customer,
            "transaction_price": contract.transaction_price,
            "start_date": contract.start_date.isoformat(),
            "end_date": contract.end_date.isoformat(),
        },
        "lines": [
            {
                "product_code": l.product_code,
                "amount": l.override_price,
                "ssp": l.ssp,
                "revrec_code": l.revrec_code,
            }
            for l in old_lines
        ],
    })

    # --- Apply new contract terms ---
    customer = payload.get("customer", contract.customer)
    transaction_price = payload.get("transaction_price", contract.transaction_price)
    start_date_raw = payload.get("start_date", contract.start_date.isoformat())
    end_date_raw = payload.get("end_date", contract.end_date.isoformat())
    line_items = payload.get("lines", [])

    if not isinstance(line_items, list) or len(line_items) == 0:
        raise HTTPException(400, "lines must be a non-empty array")

    contract.customer = customer
    contract.transaction_price = float(transaction_price)
    contract.start_date = parse_date(start_date_raw)
    contract.end_date = parse_date(end_date_raw)

    session.exec(delete(ContractLine).where(ContractLine.contract_id == contract_id))
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
                contract_id=contract_id,
                product_code=code,
                ssp=product.ssp,
                revrec_code=product.revrec_code,
                override_price=float(amount),
            )
        )

    session.commit()

    # --- Capture AFTER snapshot ---
    new_lines = session.exec(
        select(ContractLine).where(ContractLine.contract_id == contract_id)
    ).all()
    snapshot_after = json.dumps({
        "header": {
            "customer": contract.customer,
            "transaction_price": contract.transaction_price,
            "start_date": contract.start_date.isoformat(),
            "end_date": contract.end_date.isoformat(),
        },
        "lines": [
            {
                "product_code": l.product_code,
                "amount": l.override_price,
                "ssp": l.ssp,
                "revrec_code": l.revrec_code,
            }
            for l in new_lines
        ],
    })

    # --- Record the modification ---
    mod = ContractModification(
        contract_id=contract_id,
        modified_at=datetime.utcnow().isoformat(),
        change_type=change_type,
        treatment=treatment,
        effective_date=effective_date,
        snapshot_before=snapshot_before,
        snapshot_after=snapshot_after,
        notes=notes,
    )
    session.add(mod)
    session.commit()
    session.refresh(mod)

    return {
        "status": "modified",
        "contract_id": contract_id,
        "modification_id": mod.id,
        "treatment": treatment,
        "effective_date": effective_date,
        "message": f"Amendment recorded. Re-allocate revenue to apply {treatment} treatment from {effective_date}.",
    }


# ---------------- MODIFICATION HISTORY ----------------
@router.get("/{contract_id}/modifications")
def list_modifications(contract_id: str, session: Session = Depends(get_session)):
    """Return the full amendment history for a contract."""
    contract = session.get(ContractRecord, contract_id)
    if not contract:
        raise HTTPException(404, "Contract not found")

    mods = session.exec(
        select(ContractModification)
        .where(ContractModification.contract_id == contract_id)
        .order_by(ContractModification.id)
    ).all()

    return [
        {
            "id": m.id,
            "modified_at": m.modified_at,
            "change_type": m.change_type,
            "treatment": m.treatment,
            "effective_date": m.effective_date,
            "notes": m.notes,
            "snapshot_before": json.loads(m.snapshot_before),
            "snapshot_after": json.loads(m.snapshot_after),
        }
        for m in mods
    ]


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

    # Optional amendment treatment params
    treatment = payload.get("treatment")        # "prospective" | "cumulative_catch_up" | None
    effective_date = payload.get("effective_date")  # YYYY-MM-DD | None

    # Allocation math + schedule generation
    allocations = allocate_contract(contract, lines, session)
    schedule = build_schedule(contract, allocations, session)

    catchup_amount = None

    if treatment == "prospective" and effective_date:
        # Keep rows before effective_period, only add new rows from it forward
        result = save_schedule_rows(
            cid, schedule, session, prospective_from=effective_date[:7]
        )
    elif treatment == "cumulative_catch_up" and effective_date:
        # Post the catch-up delta first (reads existing rows before clearing)
        catchup_amount = post_catchup_row(cid, schedule, effective_date, session)
        # Then do a normal full re-allocation (adjustment rows including the new catch-up are preserved)
        result = save_schedule_rows(cid, schedule, session)
    else:
        result = save_schedule_rows(cid, schedule, session)

    response = {
        "status": "allocated",
        "contract_id": cid,
        "allocations": allocations,
        "schedule": schedule,
    }

    warnings = []
    if result["preserved_adjustments"] > 0:
        warnings.append(
            f"{result['preserved_adjustments']} posted adjustment row(s) were preserved and not overwritten by re-allocation."
        )
    if treatment == "prospective" and effective_date:
        warnings.append(
            f"Prospective treatment applied: schedule rows before {effective_date[:7]} were preserved; new terms applied from {effective_date[:7]} forward."
        )
    if catchup_amount is not None and abs(catchup_amount) > 0:
        warnings.append(
            f"Cumulative catch-up of ${catchup_amount:,.2f} posted to {effective_date[:7]}."
        )

    if warnings:
        response["warnings"] = warnings

    return response
