from datetime import datetime

from django.utils import timezone


def local_date_iso(value) -> str | None:
    """Return a date/datetime as an ISO date (YYYY-MM-DD) in the project's local time zone."""
    if value is None:
        return None
    if isinstance(value, datetime):
        value = timezone.localtime(value).date()
    return value.isoformat()
