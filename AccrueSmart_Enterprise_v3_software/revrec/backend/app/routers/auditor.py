from fastapi import APIRouter, Request
from ..auth import require
from ..services.auditor import summarize_audit

router = APIRouter(prefix="/auditor", tags=["auditor"])


@router.post("/summary")
@require(perms=["reports.memo"])
async def summary(request: Request):
    payload = await request.json()
    return summarize_audit(payload)


@router.get("/llm/health")
def llm_health():
    from ..llm.gateway import LLMGateway
    llm = LLMGateway()
    return {"provider": llm.provider, "model": llm.model}
