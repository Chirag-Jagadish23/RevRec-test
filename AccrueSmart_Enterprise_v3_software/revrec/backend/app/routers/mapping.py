from fastapi import APIRouter, Depends
from sqlmodel import Session
from ..models.revrec import SKURevRecRule
from ..db import get_session

router = APIRouter()

@router.post("/map")
def map_sku_to_revrec(product_code: str, revrec_code: str, session: Session = Depends(get_session)):
    rule = session.get(SKURevRecRule, product_code)
    if not rule:
        rule = SKURevRecRule(sku=product_code)
        session.add(rule)
    rule.revrec_code = revrec_code
    session.commit()
    return {"ok": True}
