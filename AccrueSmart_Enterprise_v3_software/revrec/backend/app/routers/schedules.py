from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..db import get_session
from ..models.models import ScheduleRow, Product, RevRecCode
from ..services.schedule_service import load_schedule, save_schedule_rows, clear_schedule

router = APIRouter(prefix="/schedules", tags=["schedules"])


def _safe_set(obj, field_name, value):
    """Set attribute only if model has that field."""
    if hasattr(obj, field_name):
        setattr(obj, field_name, value)


def _make_schedule_row(
    contract_id: str,
    period: str,
    amount: float,
    product_code: str | None = None,
    source: str = "manual",
    event_type: str | None = None,
    notes: str | None = None,
    effective_date: str | None = None,
    is_adjustment: bool | None = None,
    reference_row_id: int | None = None,
):
    row = ScheduleRow(
        contract_id=contract_id,
        period=period,
        amount=float(amount),
        product_code=product_code,
        source=source,
    )

    # Optional audit fields (works only if you add them to ScheduleRow model)
    _safe_set(row, "event_type", event_type)
    _safe_set(row, "notes", notes)
    _safe_set(row, "effective_date", effective_date)
    _safe_set(row, "is_adjustment", is_adjustment)
    _safe_set(row, "reference_row_id", reference_row_id)

    return row


def _enriched_grid(contract_id: str, session: Session):
    rows = session.exec(
        select(ScheduleRow).where(ScheduleRow.contract_id == contract_id)
    ).all()

    # Sort for stable display
    rows = sorted(
        rows,
        key=lambda r: (
            str(getattr(r, "period", "")),
            str(getattr(r, "product_code", "")),
            float(getattr(r, "amount", 0)),
        ),
    )

    out = []
    for idx, r in enumerate(rows, start=1):
        product = session.get(Product, r.product_code) if getattr(r, "product_code", None) else None
        rule = session.get(RevRecCode, product.revrec_code) if product and getattr(product, "revrec_code", None) else None

        out.append({
            "line_no": idx,
            "period": r.period,
            "amount": r.amount,
            "product_code": getattr(r, "product_code", None),
            "product_name": product.name if product else None,
            "ssp": product.ssp if product else None,
            "revrec_code": product.revrec_code if product else None,
            "rule_type": rule.rule_type if rule else None,
            "source": getattr(r, "source", None),

            # optional audit fields
            "event_type": getattr(r, "event_type", None),
            "notes": getattr(r, "notes", None),
            "effective_date": getattr(r, "effective_date", None),
            "is_adjustment": getattr(r, "is_adjustment", None),
            "reference_row_id": getattr(r, "reference_row_id", None),
        })

    return out


@router.get("/grid/{contract_id}")
def get_grid(contract_id: str, session: Session = Depends(get_session)):
    # Return enriched grid for the frontend editor
    return _enriched_grid(contract_id, session)


@router.delete("/grid/{contract_id}")
def delete_grid(contract_id: str, session: Session = Depends(get_session)):
    clear_schedule(contract_id, session)
    return {"status": "cleared"}


@router.post("/grid/{contract_id}")
def save_grid(contract_id: str, payload: dict, session: Session = Depends(get_session)):
    rows = payload.get("rows")
    if rows is None:
        raise HTTPException(status_code=400, detail="Missing rows")

    cleaned = []
    for r in rows:
        if "period" not in r or "amount" not in r:
            raise HTTPException(status_code=400, detail="Each row must include period and amount")

        cleaned.append({
            "period": r["period"],
            "amount": float(r["amount"]),
            "product_code": r.get("product_code"),
            "source": r.get("source", "manual"),
        })

    result = save_schedule_rows(contract_id, cleaned, session)

    response = {"status": "saved"}
    if result["preserved_adjustments"] > 0:
        response["warnings"] = [
            f"{result['preserved_adjustments']} posted adjustment row(s) were preserved and not overwritten."
        ]
    return response


@router.post("/adjust")
def adjust_schedule(payload: dict, session: Session = Depends(get_session)):
    """
    Audit-safe schedule adjustments:
      - refund: inserts one negative row
      - delay: inserts one negative row (from_period) and one positive row (to_period)
      - true_up: inserts one signed row (+/-)
    """
    contract_id = payload.get("contract_id")
    product_code = payload.get("product_code")
    adjustment_type = payload.get("adjustment_type")
    amount = payload.get("amount")
    notes = payload.get("notes")
    effective_date = payload.get("effective_date")

    if not contract_id:
      raise HTTPException(status_code=400, detail="contract_id is required")
    if not product_code:
      raise HTTPException(status_code=400, detail="product_code is required")
    if not adjustment_type:
      raise HTTPException(status_code=400, detail="adjustment_type is required")
    if amount is None:
      raise HTTPException(status_code=400, detail="amount is required")

    try:
      amount = float(amount)
    except Exception:
      raise HTTPException(status_code=400, detail="amount must be numeric")

    if amount == 0:
      raise HTTPException(status_code=400, detail="amount must be non-zero")

    # Optional but strongly recommended validation:
    product = session.get(Product, product_code)
    if not product:
      raise HTTPException(status_code=404, detail=f"Product not found: {product_code}")

    adjustment_type = str(adjustment_type).strip().lower()

    if adjustment_type == "refund":
      period = payload.get("period")
      if not period:
        raise HTTPException(status_code=400, detail="period is required for refund")

      # Always store refunds as negative rows
      row = _make_schedule_row(
        contract_id=contract_id,
        period=period,
        amount=-abs(amount),
        product_code=product_code,
        source="adjustment_refund",
        event_type="refund",
        notes=notes,
        effective_date=effective_date,
        is_adjustment=True,
      )
      session.add(row)

    elif adjustment_type == "true_up":
      period = payload.get("period")
      if not period:
        raise HTTPException(status_code=400, detail="period is required for true_up")

      row = _make_schedule_row(
        contract_id=contract_id,
        period=period,
        amount=amount,  # can be positive or negative
        product_code=product_code,
        source="adjustment_true_up",
        event_type="true_up",
        notes=notes,
        effective_date=effective_date,
        is_adjustment=True,
      )
      session.add(row)

    elif adjustment_type == "delay":
      from_period = payload.get("from_period")
      to_period = payload.get("to_period")
      if not from_period or not to_period:
        raise HTTPException(status_code=400, detail="from_period and to_period are required for delay")
      if from_period == to_period:
        raise HTTPException(status_code=400, detail="from_period and to_period must differ")

      amt = abs(amount)

      # Negative in old period
      row_out = _make_schedule_row(
        contract_id=contract_id,
        period=from_period,
        amount=-amt,
        product_code=product_code,
        source="adjustment_delay",
        event_type="delay",
        notes=notes or f"Delay out of {from_period} into {to_period}",
        effective_date=effective_date,
        is_adjustment=True,
      )

      # Positive in new period
      row_in = _make_schedule_row(
        contract_id=contract_id,
        period=to_period,
        amount=amt,
        product_code=product_code,
        source="adjustment_delay",
        event_type="delay",
        notes=notes or f"Delay from {from_period} into {to_period}",
        effective_date=effective_date,
        is_adjustment=True,
      )

      session.add(row_out)
      session.add(row_in)

    else:
      raise HTTPException(
        status_code=400,
        detail="adjustment_type must be one of: refund, delay, true_up",
      )

    session.commit()

    return {
      "status": "adjusted",
      "contract_id": contract_id,
      "adjustment_type": adjustment_type,
      "rows": _enriched_grid(contract_id, session),
    }


@router.post("/ai-generate")
def ai_generate(payload: dict, session: Session = Depends(get_session)):
    """
    Placeholder AI route (kept so frontend button doesn't break).
    For now it just returns existing schedule rows.
    """
    contract_id = payload.get("contract_id")
    if not contract_id:
        raise HTTPException(status_code=400, detail="Missing contract_id")

    rows = session.exec(
        select(ScheduleRow).where(ScheduleRow.contract_id == contract_id)
    ).all()

    schedule = [
        {
            "product_code": r.product_code,
            "period": r.period,
            "amount": r.amount,
            "source": "ai",
        }
        for r in rows
    ]

    return {
        "status": "ai_generated",
        "schedule": schedule,
    }
