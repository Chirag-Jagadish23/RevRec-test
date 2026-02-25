from fastapi import FastAPI
from .db import init_db
from .routers import contracts, schedules
from .seed import seed_data

app = FastAPI()

app.include_router(contracts.router)
app.include_router(schedules.router)

@app.on_event("startup")
def startup():
    init_db()
    seed_data()
