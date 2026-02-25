
from fastapi import APIRouter
from accounting_core.disclosure_engine import remaining_performance_obligations,revenue_disaggregation,deferred_rollforward
router=APIRouter()
@router.post("/rpo")
def rpo(schedule:list):
    return remaining_performance_obligations(schedule)
@router.post("/disaggregation")
def disagg(schedule:list):
    return revenue_disaggregation(schedule)
@router.post("/rollforward")
def rollforward(schedule:list):
    return deferred_rollforward(schedule)
