from sqlmodel import Session, select
from datetime import date
from ..models.contracts import ContractRecord, ContractLine
from ..models.revrec import SKURevRecRule
from ..services.schedule_logic import generate_straight_line
from ..services.schedules_crud import save_grid

def allocate_contract(payload: dict, session: Session):
    """
    Allocates transaction price across performance obligations.
    Supports ONLY straight-line for now.
    """
    contract_id = payload["contract_id"]
    record = session.get(ContractRecord, contract_id)
    if not record:
        raise ValueError("Contract not found")

    start = record.start_date
    end = record.end_date
    tp = float(record.transaction_price)

    # Load line items
    lines = session.exec(select(ContractLine).where(
        ContractLine.contract_id == contract_id
    )).all()

    if not lines:
        raise ValueError("No line items found")

    total_ssp = sum(l.amount for l in lines)
    if total_ssp <= 0:
        raise ValueError("SSP total cannot be zero")

    # ------------------------------
    # ASC 606 ALLOCATION
    # ------------------------------
    allocated_amounts = {
        line.sku: (tp * line.amount / total_ssp)
        for line in lines
    }

    # ------------------------------
    # BUILD SCHEDULES
    # Straight-line for all SKUs (for now)
    # ------------------------------
    all_rows = []
    line_no = 1

    for line in lines:
        allocated = allocated_amounts[line.sku]
        # Use RevRec Code if mapped
        revrec_rule = session.get(SKURevRecRule, line.sku)
        rule_type = revrec_rule.revrec_code if revrec_rule else "straight_line"

        # Straight-line schedule
        schedule = generate_straight_line(
            total=allocated,
            start=start,
            end=end
        )

        # Convert dict → rows for DB
        for period, amt in schedule.items():
            all_rows.append({
                "line_no": line_no,
                "period": period,
                "amount": amt,
                "product_code": line.sku,
                "revrec_code": rule_type,
            })
            line_no += 1

    # Save to schedule grid
    save_grid(session, contract_id, all_rows)

    return {
        "allocated": allocated_amounts,
        "schedule_rows": all_rows
    }
