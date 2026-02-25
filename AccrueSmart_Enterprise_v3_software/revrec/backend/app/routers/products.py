from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from ..db import get_session
from ..models.models import Product  # IMPORTANT: use the SAME Product model everywhere

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("")
def list_products(session: Session = Depends(get_session)):
    return session.exec(select(Product)).all()


@router.post("")
def add_product(payload: dict, session: Session = Depends(get_session)):
    code = payload.get("code") or payload.get("product_code")
    name = payload.get("name")
    if not code or not name:
        raise HTTPException(400, "code and name are required")

    existing = session.get(Product, code)
    if existing:
        # update existing
        existing.name = name
        if "ssp" in payload and payload["ssp"] is not None:
            existing.ssp = float(payload["ssp"])
        if payload.get("revrec_code"):
            existing.revrec_code = payload["revrec_code"]
    else:
        prod = Product(
            product_code=code,
            name=name,
            ssp=float(payload.get("ssp", 0)),
            revrec_code=payload.get("revrec_code", "STRAIGHT_LINE"),
        )
        session.add(prod)

    session.commit()
    return {"status": "ok"}
