from datetime import date, timedelta
from ..util.dates import month_range, prorate_amount

def generate_straight_line(total: float, start: date, end: date):
    """
    ASC 606 straight-line revenue:
    - Even allocation across months
    - Supports mid-month proration
    """
    months = month_range(start, end)
    if not months:
        return {}

    monthly_amount = total / len(months)
    monthly_amount = round(monthly_amount, 2)

    schedule = {}

    # First month proration
    first_month = months[0]
    prorated_first = prorate_amount(start, first_month, monthly_amount)
    schedule[first_month.strftime("%Y-%m")] = prorated_first

    # Middle months
    for m in months[1:-1]:
        schedule[m.strftime("%Y-%m")] = monthly_amount

    # Last month proration
    if len(months) > 1:
        last_month = months[-1]
        prorated_last = prorate_amount(end, last_month, monthly_amount, end_month=True)
        schedule[last_month.strftime("%Y-%m")] = prorated_last

    return schedule


def ai_generate_schedule(payload: dict):
    """
    Inputs:
      - default_start (YYYY-MM-DD)
      - line_hints: [{amount: N}, ...]
    """
    from datetime import date

    start = date.fromisoformat(payload["default_start"])
    total = sum(float(h["amount"]) for h in payload["line_hints"])

    # Build a 12-month schedule
    end = date(start.year + (start.month + 11) // 12,
               ((start.month + 11 - 1) % 12) + 1,
               1)

    from ..util.dates import month_range

    months = month_range(start, end)
    amount = round(total / len(months), 2)

    return {
        "contract_id": payload.get("contract_id"),
        "schedule": {
            m.strftime("%Y-%m"): amount
            for m in months
        }
    }
