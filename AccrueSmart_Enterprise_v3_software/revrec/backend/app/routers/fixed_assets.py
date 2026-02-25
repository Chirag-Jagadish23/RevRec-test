from __future__ import annotations

import csv
import io
from typing import Optional, Literal, List, Dict, Any

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field

from ..auth import require
from ..services.fixed_assets import (
    compute_depreciation_schedule,
    depreciation_journals,
    export_depreciation_csv,
    export_depreciation_journals_csv,
)

router = APIRouter(prefix="/fixed-assets", tags=["fixed-assets"])


# -------------------------
# Models
# -------------------------
DepMethod = Literal["sl", "ddb", "db_switch_sl"]
Convention = Literal["full_month", "mid_month", "half_year"]


class FixedAssetIn(BaseModel):
    asset_id: str
    asset_name: str
    category: str
    in_service_date: str  # YYYY-MM-DD
    cost: float = Field(..., ge=0)
    salvage_value: float = Field(0.0, ge=0)
    useful_life_months: int = Field(..., gt=0, le=1200)
    method: DepMethod = "sl"
    convention: Convention = "full_month"
    decline_rate: float = Field(2.0, gt=0, le=10)
    disposal_date: Optional[str] = None


# -------------------------
# Helpers (CSV parsing)
# -------------------------
REQUIRED_HEADERS = {
    "asset_id",
    "asset_name",
    "category",
    "in_service_date",
    "cost",
    "salvage_value",
    "useful_life_months",
}
OPTIONAL_HEADERS = {"method", "convention", "decline_rate", "disposal_date"}


def _normalize_csv_text(raw: str) -> str:
    txt = raw.lstrip("\ufeff").strip()
    if not txt:
        return ""

    lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
    if not lines:
        return ""

    normalized_lines = []
    for ln in lines:
        # tolerate accidentally fully quoted CSV rows
        if len(ln) >= 2 and ln[0] == '"' and ln[-1] == '"' and "," in ln:
            normalized_lines.append(ln[1:-1])
        else:
            normalized_lines.append(ln)

    return "\n".join(normalized_lines)


def _parse_assets_csv(
    text: str,
    default_method: str = "sl",
    default_convention: str = "full_month",
    default_decline_rate: float = 2.0,
) -> List[Dict[str, Any]]:
    text = _normalize_csv_text(text)
    if not text:
        raise ValueError("CSV is empty")

    reader = csv.DictReader(io.StringIO(text))
    headers = [h.strip() for h in (reader.fieldnames or []) if h and h.strip()]
    if not headers:
        raise ValueError("CSV has no headers")

    header_set = set(headers)
    missing = REQUIRED_HEADERS - header_set
    if missing:
        raise ValueError(
            f"Missing required headers: {sorted(list(missing))}. "
            f"Required: {sorted(list(REQUIRED_HEADERS))}. "
            f"Optional: {sorted(list(OPTIONAL_HEADERS))}"
        )

    rows: List[Dict[str, Any]] = []
    for i, r in enumerate(reader, start=2):
        try:
            asset_id = (r.get("asset_id") or "").strip()
            asset_name = (r.get("asset_name") or "").strip()
            category = (r.get("category") or "").strip()
            in_service_date = (r.get("in_service_date") or "").strip()

            if not asset_id:
                raise ValueError("asset_id is required")
            if not asset_name:
                raise ValueError("asset_name is required")
            if not category:
                raise ValueError("category is required")
            if not in_service_date:
                raise ValueError("in_service_date is required")

            cost = float((r.get("cost") or "").strip())
            salvage_value = float((r.get("salvage_value") or "0").strip())
            useful_life_months = int((r.get("useful_life_months") or "").strip())

            method = ((r.get("method") or "").strip() or default_method)
            convention = ((r.get("convention") or "").strip() or default_convention)

            decline_rate_raw = (r.get("decline_rate") or "").strip()
            decline_rate = (
                float(decline_rate_raw) if decline_rate_raw != "" else float(default_decline_rate)
            )

            disposal_date = ((r.get("disposal_date") or "").strip() or None)

            rows.append(
                {
                    "asset_id": asset_id,
                    "asset_name": asset_name,
                    "category": category,
                    "in_service_date": in_service_date,
                    "cost": cost,
                    "salvage_value": salvage_value,
                    "useful_life_months": useful_life_months,
                    "method": method,
                    "convention": convention,
                    "decline_rate": decline_rate,
                    "disposal_date": disposal_date,
                }
            )
        except Exception as e:
            raise ValueError(f"Invalid CSV row at line {i}: {e}")

    if not rows:
        raise ValueError("CSV has headers but no data rows")

    return rows


def _csv_filename_safe(name: str) -> str:
    keep = []
    for ch in name:
        if ch.isalnum() or ch in ("-", "_"):
            keep.append(ch)
        else:
            keep.append("_")
    return "".join(keep)


# -------------------------
# Endpoints
# -------------------------
@router.get("/health")
def health():
    return {"status": "ok", "module": "fixed-assets"}


@router.post("/depreciation/schedule")
@require(perms=["reports.memo"])
def depreciation_schedule(inp: FixedAssetIn):
    try:
        payload = inp.model_dump()
        return compute_depreciation_schedule(**payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/depreciation/journals")
@require(perms=["reports.memo"])
def depreciation_journal_entries(inp: FixedAssetIn):
    try:
        payload = inp.model_dump()
        sched = compute_depreciation_schedule(**payload)
        journals = depreciation_journals(sched)
        return {
            "asset_id": sched.get("asset_id"),
            "asset_name": sched.get("asset_name"),
            "rows": journals,
            "count": len(journals),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/depreciation/export")
@require(perms=["reports.memo"])
def export_schedule_csv(inp: FixedAssetIn):
    try:
        payload = inp.model_dump()
        csv_text = export_depreciation_csv(payload)
        fname = f"{_csv_filename_safe(inp.asset_id)}_depreciation_schedule.csv"
        return {"filename": fname, "content": csv_text}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/depreciation/export-journals")
@require(perms=["reports.memo"])
def export_journals_csv(inp: FixedAssetIn):
    try:
        payload = inp.model_dump()
        csv_text = export_depreciation_journals_csv(payload)
        fname = f"{_csv_filename_safe(inp.asset_id)}_depreciation_journals.csv"
        return {"filename": fname, "content": csv_text}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/depreciation/csv/calc")
@require(perms=["reports.memo"])
async def calc_from_csv(
    file: UploadFile = File(...),
    method: DepMethod = Form("sl"),
    convention: Convention = Form("full_month"),
    decline_rate: float = Form(2.0),
):
    """
    Bulk CSV upload.
    Required headers:
      asset_id,asset_name,category,in_service_date,cost,salvage_value,useful_life_months
    Optional:
      method,convention,decline_rate,disposal_date

    Returns:
      - If 1 row: schedule shape directly (frontend-friendly)
      - If many rows: summary + per-asset results
    """
    try:
        raw = await file.read()
        text = raw.decode("utf-8", errors="replace")

        asset_rows = _parse_assets_csv(
            text=text,
            default_method=method,
            default_convention=convention,
            default_decline_rate=decline_rate,
        )

        results = []
        errors = []

        for idx, asset in enumerate(asset_rows, start=1):
            try:
                sched = compute_depreciation_schedule(**asset)
                results.append(sched)
            except Exception as e:
                errors.append(
                    {
                        "row_num": idx,
                        "asset_id": asset.get("asset_id"),
                        "error": str(e),
                    }
                )

        # Single-row convenience mode for frontend
        if len(asset_rows) == 1 and len(results) == 1 and not errors:
            return results[0]

        return {
            "status": "ok",
            "rows_loaded": len(asset_rows),
            "success_count": len(results),
            "error_count": len(errors),
            "results": results,
            "errors": errors,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
