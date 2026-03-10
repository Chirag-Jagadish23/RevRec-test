from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .routers import (
    fixed_assets,
    close,
    deal_desk,
    graph,          
    gl_posting,     
    equity,
    commissions,
    intercompany,
    audit_log,
    contracts,
    auditor,
    schedules,
    revrec_codes,
    products,
    leases,
    costs,
    tax,
    forecast,
    disclosure_pack,
)

app = FastAPI(title="AccrueSmart API")


@app.on_event("startup")
def on_startup():
    init_db()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(contracts.router)
app.include_router(deal_desk.router)
app.include_router(graph.router)       
app.include_router(close.router)       
app.include_router(gl_posting.router)  
app.include_router(fixed_assets.router)
app.include_router(equity.router)
app.include_router(commissions.router)
app.include_router(intercompany.router)
app.include_router(audit_log.router)
app.include_router(auditor.router)
app.include_router(schedules.router)
app.include_router(revrec_codes.router)
app.include_router(products.router)
app.include_router(leases.router)
app.include_router(costs.router)
app.include_router(tax.router)
app.include_router(forecast.router)
app.include_router(disclosure_pack.router)

@app.get("/")
def root():
    return {"status": "ok", "app": "AccrueSmart API"}
