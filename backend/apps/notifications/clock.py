"""Times as people in Nigeria read them, in notifications and SMS."""

from datetime import datetime

from django.utils.dateparse import parse_datetime

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    from backports.zoneinfo import ZoneInfo

LAGOS = ZoneInfo("Africa/Lagos")


def lagos(value) -> datetime:
    if isinstance(value, str):
        value = parse_datetime(value)
    return value.astimezone(LAGOS)


def clock(value) -> str:
    """'6:40 PM'"""
    local = lagos(value)
    return f"{local.hour % 12 or 12}:{local.minute:02d} {'AM' if local.hour < 12 else 'PM'}"


def short_title(title: str) -> str:
    """'Samsung fridge, 2 doors' -> 'Samsung fridge'"""
    return title.split(",")[0].strip()
