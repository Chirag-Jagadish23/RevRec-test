from __future__ import annotations

import csv
import io
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field

from ..auth import require
from ..services.asc740 import TempDiff, compute_deferred_tax, ai_tax_memo

router = APIRouter(prefix="/tax", tags=["tax"])


# -------------------------
# Models
# -------------------------
class TempDiffIn(BaseModel):
    label: Optional[str] = "Unlabeled Temp Difference"   # backward compatible
    period: str
    amount: float
    reversal_year: int = Field(..., ge=2000, le=2100)
    va_pct: Optional[float] = Field(0.0, ge=0, le=1)    # row-level VA


class Asc740In(BaseModel):
    company: str

    # v1-style
    statutory_rate: Optional[float] = Field(None, ge=0, le=1)

    # v2-style blended mode
    use_blended_rate: bool = False
    federal_rate: Optional[float] = Field(None, ge=0, le=1)
    state_rate: float = Field(0.0, ge=0, le=1)
    state_deductible_federal: bool = True

    # global fallback VA
    valuation_allowance_pct: float = Field(0.0, ge=0, le=1)

    # optional reporting helpers
    beginning_net_deferred_tax: float = 0.0
    pretax_book_income: Optional[float] = None

    differences: List[TempDiffIn]


# -------------------------
# Helpers
# -------------------------
REQUIRED_HEADERS = {"label", "period", "amount", "reversal_year"}
OPTIONAL_HEADERS = {"va_pct"}


def _normalize_csv_text(raw: str) -> str:
    """
    Makes parser tolerant of:
    - UTF-8 BOM
    - accidental quoted single-column CSV rows like:
      "label,period,amount,reversal_year,va_pct"
    """
    txt = raw.lstrip("\ufeff").strip()

    if not txt:
        return txt

    lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
    if not lines:
        return ""

    # If every non-empty line is one quoted string containing commas,
    # unwrap it into a proper CSV line.
    normalized_lines = []
    for ln in lines:
        if len(ln) >= 2 and ln[0] == '"' and ln[-1] == '"' and "," in ln:
            inner = ln[1:-1]
            normalized_lines.append(inner)
        else:
            normalized_lines.append(ln)

    return "\n".join(normalized_lines)


def _parse_csv_temp_diffs(text: str, default_va_pct: float = 0.0) -> List[TempDiff]:
    text = _normalize_csv_text(text)
    if not text:
        raise ValueError("CSV is empty")

    reader = csv.DictReader(io.StringIO(text))
    headers = [h.strip() for h in (reader.fieldnames or []) if h and h.strip()]
    header_set = set(headers)

    if not headers:
        raise ValueError("CSV has no headers")

    missing = REQUIRED_HEADERS - header_set
    if missing:
        raise ValueError(
            f"Missing required headers: {sorted(list(missing))}. "
            f"Required headers: {sorted(list(REQUIRED_HEADERS))}. "
            f"Optional: {sorted(list(OPTIONAL_HEADERS))}"
        )

    rows: List[TempDiff] = []
    for i, r in enumerate(reader, start=2):  # line 2 = first data row
        try:
            label = (r.get("label") or "").strip() or "Unlabeled Temp Difference"
            period = (r.get("period") or "").strip()
            amount_raw = (r.get("amount") or "").strip()
            reversal_year_raw = (r.get("reversal_year") or "").strip()

            va_pct_raw = (r.get("va_pct") or "").strip()
            va_pct = float(va_pct_raw) if va_pct_raw != "" else float(default_va_pct)

            rows.append(
                TempDiff(
                    label=label,
                    period=period,
                    amount=float(amount_raw),
                    reversal_year=int(reversal_year_raw),
                    va_pct=va_pct,
                )
            )
        except Exception as e:
            raise ValueError(f"Invalid CSV row at line {i}: {e}")

    if not rows:
        raise ValueError("CSV has headers but no data rows")

    return rows


def _to_tempdiffs(inp: Asc740In) -> List[TempDiff]:
    diffs: List[TempDiff] = []
    for d in inp.differences:
        diffs.append(
            TempDiff(
                label=(d.label or "Unlabeled Temp Difference"),
                period=d.period,
                amount=float(d.amount),
                reversal_year=int(d.reversal_year),
                va_pct=float(d.va_pct or 0.0),
            )
        )
    return diffs


def _run_calc(company: str, body: Asc740In, diffs: List[TempDiff]) -> Dict[str, Any]:
    results = compute_deferred_tax(
        differences=diffs,
        statutory_rate=body.statutory_rate,
        valuation_allowance_pct=body.valuation_allowance_pct,
        federal_rate=body.federal_rate,
        state_rate=body.state_rate,
        use_blended_rate=body.use_blended_rate,
        state_deductible_federal=body.state_deductible_federal,
        beginning_net_deferred_tax=body.beginning_net_deferred_tax,
        pretax_book_income=body.pretax_book_income,
    )
    return results


# -------------------------
# Endpoints
# -------------------------
@router.post("/asc740/calc")
@require(perms=["reports.memo"])
def calc(inp: Asc740In):
    try:
        diffs = _to_tempdiffs(inp)
        return _run_calc(inp.company, inp, diffs)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/asc740/memo")
@require(perms=["reports.memo"])
def memo(inp: Asc740In):
    try:
        diffs = _to_tempdiffs(inp)
        res = _run_calc(inp.company, inp, diffs)
        return {"memo": ai_tax_memo(inp.company, res)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/asc740/csv/calc")
@require(perms=["reports.memo"])
async def calc_from_csv(
    file: UploadFile = File(...),
    company: str = Form("DemoCo"),
    statutory_rate: Optional[float] = Form(None),
    use_blended_rate: bool = Form(False),
    federal_rate: Optional[float] = Form(None),
    state_rate: float = Form(0.0),
    state_deductible_federal: bool = Form(True),
    valuation_allowance_pct: float = Form(0.0),
    beginning_net_deferred_tax: float = Form(0.0),
    pretax_book_income: Optional[float] = Form(None),
):
    """
    Multipart CSV upload endpoint.
    Required CSV headers:
      label, period, amount, reversal_year
    Optional:
      va_pct
    """
    try:
        raw = await file.read()
        text = raw.decode("utf-8", errors="replace")
        diffs = _parse_csv_temp_diffs(text, default_va_pct=valuation_allowance_pct)

        # Build a lightweight body object for reuse
        class _Body:
            pass

        body = _Body()
        body.company = company
        body.statutory_rate = statutory_rate
        body.use_blended_rate = use_blended_rate
        body.federal_rate = federal_rate
        body.state_rate = state_rate
        body.state_deductible_federal = state_deductible_federal
        body.valuation_allowance_pct = valuation_allowance_pct
        body.beginning_net_deferred_tax = beginning_net_deferred_tax
        body.pretax_book_income = pretax_book_income

        results = compute_deferred_tax(
            differences=diffs,
            statutory_rate=body.statutory_rate,
            valuation_allowance_pct=body.valuation_allowance_pct,
            federal_rate=body.federal_rate,
            state_rate=body.state_rate,
            use_blended_rate=body.use_blended_rate,
            state_deductible_federal=body.state_deductible_federal,
            beginning_net_deferred_tax=body.beginning_net_deferred_tax,
            pretax_book_income=body.pretax_book_income,
        )

        return {
            "status": "ok",
            "company": company,
            "rows_loaded": len(diffs),
            "results": results,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
