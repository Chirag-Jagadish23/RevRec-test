from fastapi import APIRouter
from sqlmodel import Session, select
from ..db import engine
from ..models.contracts import ContractRecord, ContractLine

router = APIRouter(prefix="/contracts", tags=["contracts"])

# Save / Update contract
@router.post("/")
def save_contract(payload: dict):
    with Session(engine) as session:

        contract = session.get(ContractRecord, payload["contract_id"])
        if not contract:
            contract = ContractRecord(contract_id=payload["contract_id"])
            session.add(contract)

        contract.customer = payload.get("customer")
        contract.transaction_price = payload.get("transaction_price")
        contract.start_date = payload.get("start_date")
        contract.end_date = payload.get("end_date")

        # delete old lines
        session.exec(
            select(ContractLine).where(ContractLine.contract_id == contract.contract_id)
        ).all()
        session.query(ContractLine).filter(
            ContractLine.contract_id == contract.contract_id
        ).delete()

        # insert lines
        for l in payload.get("lines", []):
            session.add(
                ContractLine(
                    contract_id=contract.contract_id,
                    sku=l["sku"],
                    amount=l["amount"]
                )
            )

        session.commit()
        return {"status": "saved"}
        

# Load contract
@router.get("/{contract_id}")
def load_contract(contract_id: str):
    with Session(engine) as session:
        contract = session.get(ContractRecord, contract_id)
        if not contract:
            return None

        lines = session.exec(
            select(ContractLine).where(ContractLine.contract_id == contract_id)
        ).all()

        return {
            "contract_id": contract.contract_id,
            "customer": contract.customer,
            "transaction_price": contract.transaction_price,
            "start_date": contract.start_date,
            "end_date": contract.end_date,
            "lines": [{"sku": l.sku, "amount": l.amount} for l in lines]
        }
