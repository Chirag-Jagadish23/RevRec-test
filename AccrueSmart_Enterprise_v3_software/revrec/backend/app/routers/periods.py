
from fastapi import APIRouter, Depends
from sqlmodel import Session
from db import get_session
from services.period_service import close_period, reopen_period

router=APIRouter(prefix="/periods")

@router.post("/close/{period}")
def close(period:str,session:Session=Depends(get_session)):
    return close_period(session,period)

@router.post("/reopen/{period}")
def reopen(period:str,session:Session=Depends(get_session)):
    return reopen_period(session,period)
