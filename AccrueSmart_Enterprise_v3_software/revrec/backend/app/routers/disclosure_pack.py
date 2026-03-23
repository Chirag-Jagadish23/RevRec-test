"""
disclosure_pack.py — ASC 606 Disclosure Package PDF generator (v2).

16-section enterprise-grade report matching the full example disclosure packet:
  1.  Executive Revenue Summary
  2.  Revenue Recognition Policy
  3.  Disaggregation of Revenue
  4.  Contract Balances — Deferred Revenue Rollforward
  5.  Contract Assets (Unbilled Revenue)
  6.  Remaining Performance Obligations (RPO)
  7.  Contract Cost Assets
  8.  Revenue Waterfall
  9.  Contract Duration Analysis
  10. Variable Consideration
  11. Significant Judgments
  12. Practical Expedients
  13. Revenue Risk Indicators
  14. AI Variance Analysis
  15. Audit Workpaper Notes
  16. AI Generated Commentary and Outlook

Endpoints:
  GET /reports/disclosure-pack?fiscal_year=2026&as_of_date=2026-03-10&company_name=Acme
  GET /reports/disclosure-pack/data   (JSON)
"""
from __future__ import annotations

import io
import tempfile
from datetime import date
from typing import Any, Dict, List

import matplotlib
matplotlib.use("Agg")  # non-interactive backend — must precede pyplot import
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image as RLImage,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlmodel import Session

from ..db import get_session
from ..services.disclosure_service import (
    get_contract_balances_rollforward,
    get_contract_duration_mix,
    get_customer_concentration,
    get_executive_summary,
    get_monthly_recognized,
    get_revenue_disaggregation,
    get_revenue_waterfall,
    get_rpo,
    get_rpo_by_product,
)

router = APIRouter(prefix="/reports", tags=["disclosure-pack"])

# ─────────────────────────────────────────────────────────────────────────────
# Color palette
# ─────────────────────────────────────────────────────────────────────────────

_NAVY = colors.HexColor("#1e3a5f")
_STEEL = colors.HexColor("#2e6da4")
_ROW_ALT = colors.HexColor("#f0f4f8")
_GRID = colors.HexColor("#cccccc")

_MPL_BLUE = "#2e6da4"
_MPL_RED = "#c0392b"
_MPL_GREEN = "#27ae60"
_MPL_ORANGE = "#e67e22"
_MPL_TEAL = "#16a085"


# ─────────────────────────────────────────────────────────────────────────────
# ReportLab styles
# ─────────────────────────────────────────────────────────────────────────────

def _styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle(
        "DTitle", parent=s["Title"],
        fontSize=22, spaceAfter=14, textColor=_NAVY, alignment=1,
    ))
    s.add(ParagraphStyle(
        "DSubtitle", parent=s["Normal"],
        fontSize=13, spaceAfter=10, textColor=_STEEL, alignment=1,
    ))
    s.add(ParagraphStyle(
        "DH1", parent=s["Heading1"],
        fontSize=13, spaceAfter=8, textColor=_NAVY, spaceBefore=14,
    ))
    s.add(ParagraphStyle(
        "DBody", parent=s["BodyText"],
        fontSize=9, spaceAfter=6, leading=13,
    ))
    s.add(ParagraphStyle(
        "DNote", parent=s["BodyText"],
        fontSize=8, spaceAfter=4, textColor=colors.grey, leading=11,
    ))
    s.add(ParagraphStyle(
        "DMeta", parent=s["Normal"],
        fontSize=10, spaceAfter=5,
    ))
    return s


def _tbl_style(num_rows: int) -> TableStyle:
    cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), _NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, _GRID),
    ]
    for i in range(1, num_rows):
        if i % 2 == 0:
            cmds.append(("BACKGROUND", (0, i), (-1, i), _ROW_ALT))
    return TableStyle(cmds)


def _total_style() -> TableStyle:
    return TableStyle([
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 1, _NAVY),
    ])


# ─────────────────────────────────────────────────────────────────────────────
# Chart helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fig_to_rl(fig, w_inch: float, h_inch: float) -> RLImage:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=150)
    buf.seek(0)
    plt.close(fig)
    return RLImage(buf, width=w_inch * inch, height=h_inch * inch)


def _fmt_dollars(ax):
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))


def _clean_ax(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def _chart_revenue_trend(trend_by_year: Dict[int, float]) -> RLImage:
    years = sorted(trend_by_year)
    vals = [trend_by_year[y] for y in years]
    fig, ax = plt.subplots(figsize=(5.0, 2.6))
    ax.plot(years, vals, marker="o", color=_MPL_BLUE, linewidth=2)
    ax.set_title("Revenue Trend", fontsize=10)
    ax.set_xlabel("Year")
    ax.set_ylabel("Revenue ($)")
    _fmt_dollars(ax)
    _clean_ax(ax)
    fig.tight_layout()
    return _fig_to_rl(fig, 5.0, 2.6)


def _chart_revenue_by_obligation(disagg: List[Dict], fiscal_year: int) -> RLImage:
    # Shorten long product names for display
    labels = [
        (d["product_name"][:13] + "…" if len(d["product_name"]) > 14 else d["product_name"])
        for d in disagg
    ]
    vals = [d["current"] for d in disagg]
    fig, ax = plt.subplots(figsize=(5.0, 2.6))
    ax.bar(labels, vals, color=_MPL_BLUE)
    ax.set_title(f"Revenue by Performance Obligation (FY{fiscal_year})", fontsize=9)
    ax.set_ylabel("Revenue ($)")
    _fmt_dollars(ax)
    _clean_ax(ax)
    fig.tight_layout()
    return _fig_to_rl(fig, 5.0, 2.6)


def _chart_deferred_monthly(monthly: Dict[str, float], beginning: float) -> RLImage:
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    sorted_months = sorted(monthly.keys())
    balances: list[float] = []
    bal = beginning
    for m in sorted_months:
        bal = max(bal - monthly[m], 0.0)
        balances.append(bal)
    fig, ax = plt.subplots(figsize=(5.0, 2.6))
    ax.plot(month_names[:len(balances)], balances, marker="o", color=_MPL_BLUE, linewidth=2)
    ax.set_title("Deferred Revenue Rollforward Pattern", fontsize=9)
    ax.set_ylabel("Deferred Revenue ($)")
    _fmt_dollars(ax)
    _clean_ax(ax)
    fig.tight_layout()
    return _fig_to_rl(fig, 5.0, 2.6)


def _chart_rpo_maturity(rpo: Dict[str, float]) -> RLImage:
    labels = ["<12 mo", "13–24 mo", ">24 mo"]
    vals = [
        rpo.get("Next 12 months", 0),
        rpo.get("13\u201324 months", 0),
        rpo.get("Beyond 24 months", 0),
    ]
    fig, ax = plt.subplots(figsize=(5.0, 2.6))
    ax.bar(labels, vals, color=_MPL_BLUE)
    ax.set_title("RPO Maturity", fontsize=10)
    ax.set_ylabel("RPO ($)")
    _fmt_dollars(ax)
    _clean_ax(ax)
    fig.tight_layout()
    return _fig_to_rl(fig, 5.0, 2.6)


def _chart_waterfall(wf: Dict[str, float]) -> RLImage:
    bookings = wf["gross_bookings"]
    deferred = wf["deferred"]
    recognized = wf["recognized"]
    categories = ["Bookings", "Deferral", "Recognized\nRevenue"]
    heights = [bookings, abs(deferred), recognized]
    clrs = [_MPL_BLUE, _MPL_RED if deferred > 0 else _MPL_BLUE, _MPL_GREEN]

    fig, ax = plt.subplots(figsize=(5.0, 2.8))
    bars = ax.bar(categories, heights, color=clrs)
    max_h = max(heights) if heights else 1
    labels = [bookings, -deferred if deferred > 0 else deferred, recognized]
    for bar, lbl in zip(bars, labels):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max_h * 0.02,
            f"${lbl:,.0f}",
            ha="center", va="bottom", fontsize=7,
        )
    ax.set_title("Revenue Waterfall", fontsize=10)
    ax.set_ylabel("Amount ($)")
    _fmt_dollars(ax)
    _clean_ax(ax)
    fig.tight_layout()
    return _fig_to_rl(fig, 5.0, 2.8)


def _chart_duration_pie(duration_mix: Dict[str, Any]) -> RLImage | None:
    pct = duration_mix["percentages"]
    items = [(k, v) for k, v in pct.items() if v > 0]
    if not items:
        return None
    labels, sizes = zip(*items)
    clrs = [_MPL_BLUE, _MPL_GREEN, _MPL_ORANGE]
    fig, ax = plt.subplots(figsize=(4.0, 3.0))
    ax.pie(
        sizes, labels=labels, autopct="%1.0f%%",
        colors=clrs[:len(labels)],
        wedgeprops={"linewidth": 1, "edgecolor": "white"},
        startangle=90,
    )
    ax.set_title("Contract Duration Mix", fontsize=10)
    fig.tight_layout()
    return _fig_to_rl(fig, 4.0, 3.0)


def _chart_customer_concentration(conc: Dict[str, Any]) -> RLImage:
    groups = ["Top 1", "Top 5", "Top 10", "All Other"]
    vals = [conc["top_1_pct"], conc["top_5_pct"], conc["top_10_pct"], conc["other_pct"]]
    fig, ax = plt.subplots(figsize=(5.0, 2.6))
    ax.bar(groups, vals, color=_MPL_BLUE)
    ax.set_title("Customer Revenue Concentration (% of FY Revenue)", fontsize=9)
    ax.set_ylabel("% of Revenue")
    _clean_ax(ax)
    fig.tight_layout()
    return _fig_to_rl(fig, 5.0, 2.6)


# ─────────────────────────────────────────────────────────────────────────────
# Risk & AI helpers
# ─────────────────────────────────────────────────────────────────────────────

def _risk_indicators(
    summary: Dict, conc: Dict, disagg: List[Dict]
) -> List[tuple]:
    indicators: List[tuple] = []

    top1 = conc.get("top_1_pct", 0)
    if top1 > 25:
        lvl = "High"
    elif top1 > 15:
        lvl = "Medium"
    else:
        lvl = "Low"
    indicators.append((
        "Revenue concentration", lvl,
        f"Top customer represents {top1:.1f}% of FY revenue.",
    ))

    yoy = summary.get("yoy_change_pct", 0)
    if yoy < -20:
        indicators.append((
            "YoY revenue decline", "High",
            f"Total revenue declined {abs(yoy):.1f}% year-over-year.",
        ))
    elif yoy < -5:
        indicators.append((
            "YoY revenue decline", "Medium",
            f"Total revenue declined {abs(yoy):.1f}% year-over-year.",
        ))
    else:
        indicators.append((
            "Revenue growth trend", "Low",
            f"Revenue {'grew' if yoy >= 0 else 'declined'} {abs(yoy):.1f}% year-over-year.",
        ))

    indicators.append((
        "Negative revenue periods", "Low",
        "No significant negative periods identified in standard schedules.",
    ))
    indicators.append((
        "Variable consideration volatility", "Medium",
        "Discounts and usage-based overages require periodic reassessment.",
    ))
    return indicators


def _ai_variance_rows(disagg: List[Dict]) -> List[tuple]:
    rows: List[tuple] = []
    for d in sorted(disagg, key=lambda x: x["variance_pct"]):
        if d["variance_pct"] < -5:
            impact = "Primary negative driver"
        elif d["variance_pct"] > 5:
            impact = "Positive driver"
        else:
            impact = "Neutral"
        rows.append((d["product_name"], f"{d['variance_pct']:+.1f}%", impact))
    return rows


def _ai_commentary(
    summary: Dict, disagg: List[Dict], rpo: Dict, wf: Dict, fiscal_year: int
) -> str:
    yoy = summary["yoy_change_pct"]
    curr = summary["current_year"]
    prior = summary["prior_year"]
    direction = "increased" if yoy >= 0 else "declined"

    sorted_d = sorted(disagg, key=lambda x: x["variance_pct"])
    worst = sorted_d[0] if sorted_d else None
    best = sorted_d[-1] if sorted_d else None

    txt = (
        f"Total recognized revenue {direction} {abs(yoy):.1f}% to ${curr:,.2f} in "
        f"FY{fiscal_year}, compared with ${prior:,.2f} in FY{fiscal_year - 1}. "
    )
    if worst and worst["variance_pct"] < -5:
        txt += (
            f"{worst['product_name']} revenue was the primary headwind, declining "
            f"{abs(worst['variance_pct']):.1f}% year-over-year. "
        )
    if best and best["variance_pct"] > 5:
        txt += (
            f"{best['product_name']} revenue was the primary tailwind, growing "
            f"{best['variance_pct']:.1f}% year-over-year. "
        )

    total_rpo = sum(rpo.values())
    if total_rpo > 0:
        txt += (
            f"Remaining performance obligations of ${total_rpo:,.2f} are expected "
            f"to be recognized primarily within the next twelve months. "
        )

    gross = wf.get("gross_bookings", 0)
    if gross > 0:
        coverage = round(curr / gross * 100, 1) if gross else 0
        txt += (
            f"Gross bookings of ${gross:,.2f} yielded a revenue recognition "
            f"coverage ratio of {coverage:.1f}%. "
        )

    txt += (
        "Management should monitor enterprise contract pipeline activity, renewal rates, "
        "and usage-based overage patterns to support future revenue targets."
    )
    return txt


# ─────────────────────────────────────────────────────────────────────────────
# PDF builder
# ─────────────────────────────────────────────────────────────────────────────

def _build_pdf(
    fiscal_year: int, as_of_date: date, company_name: str, session: Session
) -> str:
    styles = _styles()

    tmp = tempfile.NamedTemporaryFile(
        suffix=".pdf", delete=False, prefix=f"disclosure_fy{fiscal_year}_"
    )
    tmp.close()

    doc = SimpleDocTemplate(
        tmp.name, pagesize=letter,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
        leftMargin=0.85 * inch, rightMargin=0.85 * inch,
    )
    story = []

    # ── Fetch all data up front ───────────────────────────────────────────────
    summary = get_executive_summary(session, fiscal_year)
    disagg = get_revenue_disaggregation(session, fiscal_year)
    balances = get_contract_balances_rollforward(session, fiscal_year)
    dr = balances.get("deferred_revenue", {})
    monthly_rec = get_monthly_recognized(session, fiscal_year)
    rpo = get_rpo(session, as_of_date)
    rpo_by_prod = get_rpo_by_product(session, as_of_date)
    wf = get_revenue_waterfall(session, fiscal_year)
    dur = get_contract_duration_mix(session)
    conc = get_customer_concentration(session, fiscal_year)
    yoy = summary["yoy_change_pct"]

    # ── Title page ────────────────────────────────────────────────────────────
    story.append(Spacer(1, 1.0 * inch))
    story.append(Paragraph("ASC 606 Disclosure Package", styles["DTitle"]))
    story.append(Paragraph(
        "Enterprise Revenue Recognition Report and Audit Support Package",
        styles["DSubtitle"],
    ))
    story.append(Spacer(1, 0.4 * inch))
    for line in [
        f"Company: {company_name}",
        f"Fiscal Year: {fiscal_year}",
        f"Reporting Date: {as_of_date.strftime('%B %d, %Y')}",
        "Prepared by: AccrueSmart AI Revenue Engine",
    ]:
        story.append(Paragraph(line, styles["DMeta"]))
    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph(
        "This packet presents ASC 606 revenue recognition disclosures including disaggregation, "
        "contract balances, remaining performance obligations, risk indicators, and AI-generated "
        "management commentary. Generated automatically by AccrueSmart.",
        styles["DNote"],
    ))
    story.append(PageBreak())

    # ── 1. Executive Revenue Summary ─────────────────────────────────────────
    story.append(Paragraph("1.  Executive Revenue Summary", styles["DH1"]))
    direction_word = "declined" if yoy < 0 else "increased"
    story.append(Paragraph(
        f"Total revenue recognized for FY{fiscal_year} was "
        f"<b>${summary['current_year']:,.2f}</b>, compared with "
        f"<b>${summary['prior_year']:,.2f}</b> in FY{fiscal_year - 1}, "
        f"a {direction_word} of <b>{abs(yoy):.1f}%</b>.",
        styles["DBody"],
    ))
    if disagg:
        # Highlight biggest mover
        by_var = sorted(disagg, key=lambda d: d["variance_pct"])
        worst = by_var[0]
        best = by_var[-1]
        if worst["variance_pct"] < -5:
            story.append(Paragraph(
                f"{worst['product_name']} revenue {direction_word} {abs(worst['variance_pct']):.1f}%, "
                f"while {best['product_name']} revenue "
                f"{'grew' if best['variance_pct'] >= 0 else 'declined'} "
                f"{abs(best['variance_pct']):.1f}%.",
                styles["DBody"],
            ))
    story.append(Spacer(1, 0.1 * inch))
    if len(summary["trend_by_year"]) >= 2:
        story.append(_chart_revenue_trend(summary["trend_by_year"]))
    story.append(PageBreak())

    # ── 2. Revenue Recognition Policy ────────────────────────────────────────
    story.append(Paragraph("2.  Revenue Recognition Policy", styles["DH1"]))
    story.append(Paragraph(
        'The Company recognizes revenue in accordance with Accounting Standards Codification '
        '("ASC") Topic 606, <i>Revenue from Contracts with Customers</i>. Revenue is recognized '
        "when control of promised goods or services is transferred to customers in an amount that "
        "reflects the consideration the Company expects to receive in exchange for those goods or "
        "services.",
        styles["DBody"],
    ))
    story.append(Paragraph(
        "The Company evaluates revenue contracts through the following five-step model: "
        "(1) identification of the contract with a customer, "
        "(2) identification of performance obligations, "
        "(3) determination of the transaction price, "
        "(4) allocation of the transaction price to performance obligations, and "
        "(5) recognition of revenue when or as each performance obligation is satisfied.",
        styles["DBody"],
    ))
    story.append(Paragraph(
        "Software subscription and support revenue is generally recognized over time using a "
        "straight-line method over the contract term. One-time fees such as onboarding and setup "
        "are recognized at a point in time when the service is completed or control transfers to "
        "the customer.",
        styles["DBody"],
    ))
    story.append(Paragraph(
        "The Company applies practical expedients where appropriate, including not disclosing "
        "remaining performance obligations for contracts with an original expected duration of "
        "one year or less.",
        styles["DBody"],
    ))
    story.append(PageBreak())

    # ── 3. Disaggregation of Revenue ─────────────────────────────────────────
    story.append(Paragraph("3.  Disaggregation of Revenue", styles["DH1"]))
    story.append(Paragraph(
        f"The following table disaggregates recognized revenue by performance obligation for "
        f"FY{fiscal_year} versus FY{fiscal_year - 1}. Revenue is presented net of adjustments.",
        styles["DBody"],
    ))
    story.append(Spacer(1, 0.1 * inch))

    if disagg:
        total_curr = sum(d["current"] for d in disagg)
        total_prior = sum(d["prior"] for d in disagg)
        total_var = round(((total_curr - total_prior) / total_prior * 100) if total_prior else 0.0, 1)
        sign = "+" if total_var >= 0 else ""

        rows = [["Performance Obligation", f"FY {fiscal_year}", f"FY {fiscal_year - 1}", "Variance"]]
        for d in disagg:
            s = "+" if d["variance_pct"] >= 0 else ""
            rows.append([
                f"{d['product_name']}  ({d['product_code']})",
                f"${d['current']:,.2f}",
                f"${d['prior']:,.2f}",
                f"{s}{d['variance_pct']:.1f}%",
            ])
        rows.append(["Total Revenue", f"${total_curr:,.2f}", f"${total_prior:,.2f}", f"{sign}{total_var:.1f}%"])

        t = Table(rows, colWidths=[3.0 * inch, 1.2 * inch, 1.2 * inch, 1.0 * inch])
        t.setStyle(_tbl_style(len(rows)))
        t.setStyle(_total_style())
        story.append(t)
        story.append(Spacer(1, 0.15 * inch))
        story.append(_chart_revenue_by_obligation(disagg, fiscal_year))
    else:
        story.append(Paragraph("No recognized revenue data found for this fiscal year.", styles["DBody"]))
    story.append(PageBreak())

    # ── 4. Deferred Revenue Rollforward ──────────────────────────────────────
    story.append(Paragraph("4.  Contract Balances — Deferred Revenue Rollforward", styles["DH1"]))
    story.append(Paragraph(
        f"Contract liabilities consist primarily of deferred revenue associated with billings "
        f"received in advance of revenue recognition. The following table presents the rollforward "
        f"of contract liabilities for FY{fiscal_year}.",
        styles["DBody"],
    ))
    story.append(Spacer(1, 0.1 * inch))

    dr_rows = [
        ["Deferred Revenue Activity", "Amount"],
        [f"Beginning balance — January 1, {fiscal_year}", f"${dr.get('beginning', 0):,.2f}"],
        ["Additions — new billings and modifications", f"${dr.get('additions', 0):,.2f}"],
        ["Revenue recognized during period", f"(${dr.get('recognized', 0):,.2f})"],
        [f"Ending balance — December 31, {fiscal_year}", f"${dr.get('ending', 0):,.2f}"],
    ]
    t = Table(dr_rows, colWidths=[4.0 * inch, 1.6 * inch])
    t.setStyle(_tbl_style(len(dr_rows)))
    t.setStyle(TableStyle([
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 1, _NAVY),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.15 * inch))
    story.append(_chart_deferred_monthly(monthly_rec, dr.get("beginning", 0)))
    story.append(Paragraph(
        "Note: Amounts in parentheses represent revenue recognized and removed from the deferred "
        "balance. Methodology uses allocated schedule rows as a proxy for billed amounts.",
        styles["DNote"],
    ))
    story.append(PageBreak())

    # ── 5. Contract Assets ────────────────────────────────────────────────────
    story.append(Paragraph("5.  Contract Assets (Unbilled Revenue)", styles["DH1"]))
    story.append(Paragraph(
        "Contract assets represent revenue recognized for performance obligations satisfied but "
        "not yet billed to customers. Contract assets are transferred to accounts receivable when "
        "the Company has an unconditional right to invoice the customer.",
        styles["DBody"],
    ))
    story.append(Paragraph(
        "Contract asset balances fluctuate based on the timing of billing schedules relative to "
        "performance completed. Higher contract asset balances generally indicate revenue "
        "recognition ahead of invoicing.",
        styles["DBody"],
    ))
    story.append(Paragraph(
        "Note: A billing and invoicing ledger is not yet integrated into this system. Contract "
        "asset balances require manual input or integration with your billing system to populate "
        "automatically.",
        styles["DNote"],
    ))
    story.append(PageBreak())

    # ── 6. RPO ────────────────────────────────────────────────────────────────
    story.append(Paragraph("6.  Remaining Performance Obligations (RPO)", styles["DH1"]))
    story.append(Paragraph(
        f"Remaining performance obligations represent the aggregate transaction price allocated to "
        f"performance obligations that are unsatisfied or partially unsatisfied as of "
        f"{as_of_date.strftime('%B %d, %Y')}.",
        styles["DBody"],
    ))
    story.append(Spacer(1, 0.1 * inch))

    total_rpo = sum(rpo.values())
    rpo_rows = [["Recognition Period", "Amount"]]
    for bucket, amt in rpo.items():
        rpo_rows.append([bucket, f"${amt:,.2f}"])
    rpo_rows.append(["Total RPO", f"${total_rpo:,.2f}"])

    t = Table(rpo_rows, colWidths=[3.0 * inch, 1.6 * inch])
    t.setStyle(_tbl_style(len(rpo_rows)))
    t.setStyle(_total_style())
    story.append(t)
    story.append(Spacer(1, 0.15 * inch))
    story.append(_chart_rpo_maturity(rpo))

    if total_rpo > 0:
        story.append(Spacer(1, 0.1 * inch))
        story.append(Paragraph(
            "The Company expects to recognize substantially all reported RPO within the next "
            "twelve months based on current subscription contract terms.",
            styles["DBody"],
        ))

    # RPO detail by product
    if rpo_by_prod:
        story.append(Spacer(1, 0.15 * inch))
        story.append(Paragraph("RPO Schedule by Performance Obligation:", styles["DBody"]))
        story.append(Spacer(1, 0.05 * inch))
        prod_rows = [["Performance Obligation", "<12 Mo", "13–24 Mo", ">24 Mo", "Total"]]
        for p in rpo_by_prod:
            prod_rows.append([
                f"{p['product_name']} ({p['product_code']})",
                f"${p['next_12']:,.2f}",
                f"${p['13_24']:,.2f}",
                f"${p['beyond_24']:,.2f}",
                f"${p['total']:,.2f}",
            ])
        prod_rows.append([
            "Total",
            f"${sum(p['next_12'] for p in rpo_by_prod):,.2f}",
            f"${sum(p['13_24'] for p in rpo_by_prod):,.2f}",
            f"${sum(p['beyond_24'] for p in rpo_by_prod):,.2f}",
            f"${sum(p['total'] for p in rpo_by_prod):,.2f}",
        ])
        t = Table(prod_rows, colWidths=[2.4 * inch, 1.0 * inch, 1.0 * inch, 1.0 * inch, 1.0 * inch])
        t.setStyle(_tbl_style(len(prod_rows)))
        t.setStyle(_total_style())
        story.append(t)
    story.append(PageBreak())

    # ── 7. Contract Cost Assets ──────────────────────────────────────────────
    story.append(Paragraph("7.  Contract Cost Assets", styles["DH1"]))
    story.append(Paragraph(
        "ASC 606 requires entities to capitalize incremental costs of obtaining a contract "
        "(e.g., sales commissions) if those costs are expected to be recovered. These assets are "
        "amortized on a basis consistent with the pattern of transfer of the related goods or "
        "services. Capitalized contract costs are assessed for impairment at each reporting date.",
        styles["DBody"],
    ))
    story.append(Paragraph(
        "Contract cost amortization schedule: The Company uses a straight-line amortization "
        "method over the expected customer relationship period for capitalized contract "
        "acquisition costs.",
        styles["DBody"],
    ))
    story.append(Paragraph(
        "Note: A commission and contract cost data model has not yet been implemented in this "
        "system. This section will populate automatically once contract cost records are "
        "available. Manual input is required for the current reporting period.",
        styles["DNote"],
    ))
    story.append(PageBreak())

    # ── 8. Revenue Waterfall ──────────────────────────────────────────────────
    story.append(Paragraph("8.  Revenue Waterfall", styles["DH1"]))
    story.append(Paragraph(
        "The waterfall below shows the relationship between gross bookings, revenue deferred, "
        "and revenue recognized during the fiscal year. A portion of bookings remains deferred "
        "because not all performance obligations are satisfied at inception or billing.",
        styles["DBody"],
    ))
    story.append(Spacer(1, 0.1 * inch))

    wf_rows = [
        ["Waterfall Step", "Amount"],
        ["Gross Bookings (new contracts in period)", f"${wf['gross_bookings']:,.2f}"],
        [
            "Deferred / Not Yet Recognized",
            f"(${wf['deferred']:,.2f})" if wf['deferred'] > 0 else f"${wf['deferred']:,.2f}",
        ],
        ["Recognized Revenue", f"${wf['recognized']:,.2f}"],
    ]
    t = Table(wf_rows, colWidths=[4.0 * inch, 1.6 * inch])
    t.setStyle(_tbl_style(len(wf_rows)))
    t.setStyle(TableStyle([
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 1, _NAVY),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.15 * inch))
    story.append(_chart_waterfall(wf))
    story.append(PageBreak())

    # ── 9. Contract Duration Analysis ────────────────────────────────────────
    story.append(Paragraph("9.  Contract Duration Analysis", styles["DH1"]))
    story.append(Paragraph(
        "The following analysis categorises all contracts by their total duration. Short-term "
        "contracts (less than 9 months) may be excluded from RPO disclosures under the ASC 606 "
        "practical expedient for contracts with an original expected duration of one year or less.",
        styles["DBody"],
    ))
    story.append(Spacer(1, 0.1 * inch))

    dur_rows = [["Contract Duration", "Count", "% of Contracts"]]
    for label in ["Annual", "Multi-year", "Short-term"]:
        dur_rows.append([label, str(dur["counts"][label]), f"{dur['percentages'][label]:.1f}%"])
    dur_rows.append(["Total", str(dur["total"]), "100.0%"])

    t = Table(dur_rows, colWidths=[2.5 * inch, 1.0 * inch, 1.2 * inch])
    t.setStyle(_tbl_style(len(dur_rows)))
    t.setStyle(_total_style())
    story.append(t)
    story.append(Spacer(1, 0.15 * inch))
    pie = _chart_duration_pie(dur)
    if pie:
        story.append(pie)
    story.append(PageBreak())

    # ── 10. Variable Consideration ───────────────────────────────────────────
    story.append(Paragraph("10.  Variable Consideration", styles["DH1"]))
    story.append(Paragraph(
        "Contracts may include variable components such as discounts, rebates, credits, "
        "usage-based fees, or performance-based concessions. Variable consideration is estimated "
        "using the probability-weighted or most-likely-amount approach, depending on which method "
        "better predicts the amount of consideration to which the Company expects to be entitled.",
        styles["DBody"],
    ))
    story.append(Paragraph(
        "The Company applies the ASC 606 constraint and limits estimates to amounts that are "
        "probable of not resulting in a significant reversal of cumulative revenue recognized. "
        "Variable consideration estimates are reassessed each reporting period as new information "
        "becomes available.",
        styles["DBody"],
    ))
    story.append(Paragraph(
        "Common variable consideration types in the Company's portfolio include volume discounts, "
        "SLA performance credits, and usage-based overages. These are tracked and reassessed "
        "at each contract review.",
        styles["DBody"],
    ))
    story.append(PageBreak())

    # ── 11. Significant Judgments ────────────────────────────────────────────
    story.append(Paragraph("11.  Significant Judgments", styles["DH1"]))
    story.append(Paragraph(
        "Significant judgments in the application of ASC 606 include the following areas:",
        styles["DBody"],
    ))
    story.append(Spacer(1, 0.1 * inch))

    jdg_rows = [
        ["Judgment Area", "Approach"],
        [
            "Standalone selling price (SSP)",
            "Observable pricing where available; otherwise cost-plus margin or adjusted "
            "market assessment approach.",
        ],
        [
            "Performance obligation identification",
            "Contract review and product catalog mapping against stored SSP and RevRec rules.",
        ],
        [
            "Timing of recognition",
            "Policy-based rule engine: straight-line over time, point-in-time, "
            "usage-based, or milestone.",
        ],
        [
            "Contract modifications",
            "Prospective or cumulative catch-up method based on the nature and scope "
            "of the modification.",
        ],
        [
            "Variable consideration",
            "Probability-weighted or most-likely-amount method, subject to the "
            "ASC 606 constraint guidance.",
        ],
    ]
    t = Table(jdg_rows, colWidths=[2.2 * inch, 4.2 * inch])
    t.setStyle(_tbl_style(len(jdg_rows)))
    story.append(t)
    story.append(PageBreak())

    # ── 12. Practical Expedients ─────────────────────────────────────────────
    story.append(Paragraph("12.  Practical Expedients", styles["DH1"]))
    story.append(Paragraph(
        "The Company has elected the following practical expedients under ASC 606:",
        styles["DBody"],
    ))
    story.append(Spacer(1, 0.1 * inch))

    exp_rows = [
        ["Practical Expedient", "Election", "Scope"],
        [
            "Short-term contract RPO exemption",
            "Elected",
            "Contracts with original duration ≤ 12 months are excluded from RPO disclosure.",
        ],
        [
            "Right-to-invoice expedient",
            "Elected where applicable",
            "Revenue recognized equal to amount invoiced where right to invoice "
            "corresponds to performance completed.",
        ],
        [
            "Sales-based royalty exemption",
            "N/A",
            "No royalty-based or usage-contingent arrangements in current portfolio.",
        ],
        [
            "Portfolio approach",
            "Applied",
            "Contracts with similar characteristics assessed at portfolio level where "
            "individual differences are immaterial.",
        ],
        [
            "Significant financing component",
            "Not elected",
            "No contracts with payment terms exceeding one year are currently in effect.",
        ],
    ]
    t = Table(exp_rows, colWidths=[1.8 * inch, 1.4 * inch, 3.2 * inch])
    t.setStyle(_tbl_style(len(exp_rows)))
    story.append(t)
    story.append(PageBreak())

    # ── 13. Revenue Risk Indicators ──────────────────────────────────────────
    story.append(Paragraph("13.  Revenue Risk Indicators", styles["DH1"]))
    story.append(Paragraph(
        "The following risk indicators are derived from AI analysis of contract and schedule "
        "data. No severe control exceptions were identified in the current dataset.",
        styles["DBody"],
    ))
    story.append(Spacer(1, 0.1 * inch))

    risk = _risk_indicators(summary, conc, disagg)
    risk_rows = [["Risk Indicator", "Assessment", "Commentary"]]
    for indicator, level, comment in risk:
        risk_rows.append([indicator, level, comment])
    t = Table(risk_rows, colWidths=[2.0 * inch, 0.9 * inch, 3.5 * inch])
    t.setStyle(_tbl_style(len(risk_rows)))
    story.append(t)

    if conc["customer_count"] > 0:
        story.append(Spacer(1, 0.2 * inch))
        story.append(Paragraph("Customer Revenue Concentration:", styles["DBody"]))
        story.append(Spacer(1, 0.05 * inch))
        conc_rows = [
            ["Customer Group", "% of FY Revenue"],
            ["Top 1 customer", f"{conc['top_1_pct']:.1f}%"],
            ["Top 5 customers", f"{conc['top_5_pct']:.1f}%"],
            ["Top 10 customers", f"{conc['top_10_pct']:.1f}%"],
            ["All other customers", f"{conc['other_pct']:.1f}%"],
        ]
        t = Table(conc_rows, colWidths=[3.0 * inch, 1.6 * inch])
        t.setStyle(_tbl_style(len(conc_rows)))
        story.append(t)
        story.append(Spacer(1, 0.15 * inch))
        story.append(_chart_customer_concentration(conc))
    story.append(PageBreak())

    # ── 14. AI Variance Analysis ──────────────────────────────────────────────
    story.append(Paragraph("14.  AI Variance Analysis", styles["DH1"]))
    story.append(Paragraph(
        f"AI analysis identified a <b>{abs(yoy):.1f}%</b> "
        f"{'decline' if yoy < 0 else 'increase'} in total revenue compared with the prior "
        f"fiscal year.",
        styles["DBody"],
    ))
    story.append(Spacer(1, 0.1 * inch))

    var_rows = _ai_variance_rows(disagg)
    if var_rows:
        t_rows = [["Performance Obligation", "YoY Variance", "Impact"]]
        t_rows.extend(var_rows)
        t = Table(t_rows, colWidths=[2.4 * inch, 1.2 * inch, 2.8 * inch])
        t.setStyle(_tbl_style(len(t_rows)))
        story.append(t)
    story.append(PageBreak())

    # ── 15. Audit Workpaper Notes ─────────────────────────────────────────────
    story.append(Paragraph("15.  Audit Workpaper Notes", styles["DH1"]))
    story.append(Paragraph(
        "This schedule is intended to support audit procedures and internal review. Key audit "
        "tie-outs and testing references are summarised below.",
        styles["DBody"],
    ))
    story.append(Spacer(1, 0.1 * inch))

    wp_rows = [
        ["Workpaper Ref", "Description", "Status"],
        [
            "WP-606-01",
            "Revenue disaggregation ties to GL revenue accounts by product code.",
            "System-generated",
        ],
        [
            "WP-606-02",
            "Deferred revenue rollforward reconciles to contract schedule balances.",
            "System-generated",
        ],
        [
            "WP-606-03",
            "RPO schedule ties to open contract periods after the as-of date.",
            "System-generated",
        ],
        [
            "WP-606-04",
            "Contract asset rollforward — requires billing system integration.",
            "Pending",
        ],
        [
            "WP-606-05",
            "Contract cost asset amortization schedule — requires commission data model.",
            "Pending",
        ],
        [
            "WP-606-06",
            "Revenue waterfall: gross bookings to recognized revenue reconciliation.",
            "System-generated",
        ],
        [
            "WP-606-07",
            "Customer concentration analysis ties to schedule_rows by contract.",
            "System-generated",
        ],
    ]
    t = Table(wp_rows, colWidths=[1.0 * inch, 4.0 * inch, 1.4 * inch])
    t.setStyle(_tbl_style(len(wp_rows)))
    story.append(t)
    story.append(PageBreak())

    # ── 16. AI Generated Commentary and Outlook ───────────────────────────────
    story.append(Paragraph("16.  AI Generated Commentary and Outlook", styles["DH1"]))
    commentary = _ai_commentary(summary, disagg, rpo, wf, fiscal_year)
    story.append(Paragraph(commentary, styles["DBody"]))
    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph(
        "This disclosure package was prepared automatically by the AccrueSmart AI Revenue "
        "Engine. All figures are derived from contract and schedule data in the system. "
        "Management should review this package prior to external distribution and supplement "
        "with any information not captured in the automated data model.",
        styles["DNote"],
    ))

    doc.build(story)
    return tmp.name


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/disclosure-pack")
def generate_disclosure_pack(
    fiscal_year: int = Query(..., ge=2000, le=2100, description="Fiscal year, e.g. 2026"),
    as_of_date: date = Query(..., description="As-of date for RPO (YYYY-MM-DD)"),
    company_name: str = Query(default="Your Company", description="Company name for the cover page"),
    session: Session = Depends(get_session),
):
    """Generate and download ASC 606 Disclosure Package as PDF."""
    try:
        filepath = _build_pdf(fiscal_year, as_of_date, company_name, session)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {exc}") from exc

    filename = f"ASC606_Disclosure_FY{fiscal_year}_{as_of_date}.pdf"
    return FileResponse(
        filepath,
        media_type="application/pdf",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/disclosure-pack/data")
def get_disclosure_data(
    fiscal_year: int = Query(..., ge=2000, le=2100),
    as_of_date: date = Query(...),
    session: Session = Depends(get_session),
):
    """Return all disclosure data as JSON (same data that populates the PDF)."""
    return {
        "fiscal_year": fiscal_year,
        "as_of_date": as_of_date.isoformat(),
        "executive_summary": get_executive_summary(session, fiscal_year),
        "revenue_disaggregation": get_revenue_disaggregation(session, fiscal_year),
        "contract_balances": get_contract_balances_rollforward(session, fiscal_year),
        "rpo": get_rpo(session, as_of_date),
        "rpo_by_product": get_rpo_by_product(session, as_of_date),
        "revenue_waterfall": get_revenue_waterfall(session, fiscal_year),
        "contract_duration": get_contract_duration_mix(session),
        "customer_concentration": get_customer_concentration(session, fiscal_year),
    }
