# backend/app/routers/viewer.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

from ..auth import require
from ..services.viewer_ai import extract_contract_view

router = APIRouter(prefix="/viewer", tags=["viewer"])


class ViewerExtractIn(BaseModel):
    text: str = Field(..., min_length=1)
    source_name: Optional[str] = None


@router.get("/health")
def viewer_health():
    return {"status": "ok", "module": "viewer"}


@router.post("/extract")
@require(perms=["reports.memo"])
def extract(inp: ViewerExtractIn) -> Dict[str, Any]:
    try:
        out = extract_contract_view(inp.text)
        if inp.source_name:
            out["source_name"] = inp.source_name
        return out
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
