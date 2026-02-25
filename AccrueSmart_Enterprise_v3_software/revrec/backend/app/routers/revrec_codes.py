from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from ..db import get_session
from ..models.models import RevRecCode, Product

router = APIRouter(prefix="/revrec_codes", tags=["revrec_codes"])


@router.get("")
def list_revrec_codes(session: Session = Depends(get_session)):
    return session.exec(select(RevRecCode)).all()


@router.post("")
def add_revrec_code(payload: dict, session: Session = Depends(get_session)):
    code = payload.get("code")
    rule_type = payload.get("rule_type")
    description = payload.get("description", "")

    if not code or not rule_type:
        raise HTTPException(400, "code and rule_type are required")

    existing = session.get(RevRecCode, code)
    if existing:
        existing.rule_type = rule_type
        existing.description = description
    else:
        session.add(
            RevRecCode(
                code=code,
                rule_type=rule_type,
                description=description,
            )
        )

    session.commit()
    return {"status": "ok"}


@router.post("/map")
def map_product_to_revrec(payload: dict, session: Session = Depends(get_session)):
    product_code = payload.get("product_code")
    revrec_code = payload.get("revrec_code")

    if not product_code or not revrec_code:
        raise HTTPException(400, "product_code and revrec_code are required")

    product = session.get(Product, product_code)
    if not product:
        raise HTTPException(404, f"Product {product_code} not found")

    rule = session.get(RevRecCode, revrec_code)
    if not rule:
        raise HTTPException(404, f"RevRec code {revrec_code} not found")

    product.revrec_code = revrec_code
    session.commit()
    return {"status": "mapped"}
