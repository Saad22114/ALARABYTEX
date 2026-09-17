from datetime import date, timedelta

from django.utils import timezone

PERIODS = ("today", "week", "month", "last_month", "custom")


def _parse_date(value, fallback):
    if value is None or value == "":
        return fallback
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return fallback


def resolve_range(query_params, default_period="today"):
    """Resolve a dashboard period into an inclusive (start, end) date range.

    Supported period values: today, week, month, last_month, custom.
    For custom, reads date_from / date_to. Returns (start, end, period).
    """
    today = timezone.localdate()
    raw_period = query_params.get("period")
    if not raw_period:
        if query_params.get("date_from") or query_params.get("date_to"):
            raw_period = "custom"
        else:
            raw_period = default_period or "today"
    period = str(raw_period).strip()

    if period == "today":
        start = end = today
    elif period == "week":
        start = today - timedelta(days=today.weekday())
        end = today
    elif period == "month":
        start = today.replace(day=1)
        end = today
    elif period == "last_month":
        end = today.replace(day=1) - timedelta(days=1)
        start = end.replace(day=1)
    elif period == "custom":
        start = _parse_date(query_params.get("date_from"), today)
        end = _parse_date(query_params.get("date_to"), today)
        if start > end:
            start, end = end, start
    else:
        period = "today"
        start = end = today

    return start, end, period
