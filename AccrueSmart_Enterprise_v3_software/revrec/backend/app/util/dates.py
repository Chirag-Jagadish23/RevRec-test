from datetime import date, timedelta

def month_range(start: date, end: date):
    """
    Returns list of month start dates between start and end.
    """
    months = []
    cur = date(start.year, start.month, 1)

    while cur <= end:
        months.append(cur)
        if cur.month == 12:
            cur = date(cur.year + 1, 1, 1)
        else:
            cur = date(cur.year, cur.month + 1, 1)

    return months


def days_in_month(dt: date):
    if dt.month == 12:
        next_month = date(dt.year + 1, 1, 1)
    else:
        next_month = date(dt.year, dt.month + 1, 1)
    return (next_month - date(dt.year, dt.month, 1)).days


def prorate_amount(dt: date, month_start: date, full_amount: float, end_month=False):
    """
    Proration for first/last month:
    - dt = start or end date
    - month_start = first day of that month
    """
    dim = days_in_month(month_start)

    if end_month:
        # last month: revenue until dt (exclusive)
        used_days = dt.day
    else:
        # first month: revenue from dt → end of month
        used_days = dim - dt.day + 1

    prorated = full_amount * (used_days / dim)
    return round(prorated, 2)
