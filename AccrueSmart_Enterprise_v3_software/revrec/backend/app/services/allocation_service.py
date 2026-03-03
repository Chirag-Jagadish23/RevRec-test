from datetime import date
from typing import List
from sqlmodel import Session
from ..models.models import ContractRecord, ContractLine, RevRecCode


def months_between(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + (end.month - start.month) + 1


def allocate_contract(contract: ContractRecord, lines: List[ContractLine], session: Session):
    """
    ASC-606 Relative SSP Allocation:
    allocated_total = (line SSP / total SSP) * transaction price
    """
    total_ssp = sum(l.ssp for l in lines)
    if total_ssp <= 0:
        raise ValueError("Total SSP = 0, cannot allocate")

    months = months_between(contract.start_date, contract.end_date)
    allocations = []

    for line in lines:

        # ASC-606 step: relative SSP weight
        weight = line.ssp / total_ssp

        # Allocated revenue for this SKU
        allocated_total = round(contract.transaction_price * weight, 2)

        # Monthly amount (for straight-line)
        monthly_amount = round(allocated_total / months, 2)
        # Last row absorbs any cent-level rounding remainder so total always equals allocated_total
        last_row_amount = round(allocated_total - monthly_amount * (months - 1), 2)

        # Load the rule object
        rule = session.get(RevRecCode, line.revrec_code)

        allocations.append({
            "product_code": line.product_code,
            "revrec_code": line.revrec_code,
            "rule_type": rule.rule_type if rule else "straight_line",
            "allocated_total": allocated_total,
            "monthly_amount": monthly_amount,
            "last_row_amount": last_row_amount,
            "months": months,
        })

    return allocations
