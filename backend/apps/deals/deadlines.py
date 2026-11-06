"""Deadlines that pause overnight. From 22:00 to 07:00 Africa/Lagos nobody
is called or reminded, and deal clocks stop: a 4-hour window that starts at
9 PM ends at 10 AM. Every deadline in the app comes from deadline_after().
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

from apps.notifications.clock import LAGOS

QUIET_START = time(22, 0)
QUIET_END = time(7, 0)


def in_quiet_hours(moment: datetime) -> bool:
    local = moment.astimezone(LAGOS).time()
    return local >= QUIET_START or local < QUIET_END


def _resume(moment: datetime) -> datetime:
    """`moment`, or the end of the quiet hours it falls in."""
    if not in_quiet_hours(moment):
        return moment
    local = moment.astimezone(LAGOS)
    day = local.date() if local.time() < QUIET_END else local.date() + timedelta(days=1)
    return datetime.combine(day, QUIET_END, tzinfo=LAGOS)


def _quiet_start_after(moment: datetime) -> datetime:
    """The next 22:00 after an awake `moment`."""
    local = moment.astimezone(LAGOS)
    return datetime.combine(local.date(), QUIET_START, tzinfo=LAGOS)


def deadline_after(start: datetime, hours: float) -> datetime:
    """`hours` of awake time after `start`, skipping quiet hours."""
    remaining = timedelta(hours=hours)
    moment = start
    while True:
        moment = _resume(moment)
        window = _quiet_start_after(moment) - moment
        if remaining <= window:
            return moment + remaining
        remaining -= window
        moment = _quiet_start_after(moment)


def awake_time_between(start: datetime, end: datetime) -> timedelta:
    """Awake time from `start` to `end` (0 if end is earlier)."""
    total = timedelta(0)
    moment = start
    while moment < end:
        moment = _resume(moment)
        if moment >= end:
            break
        stop = min(_quiet_start_after(moment), end)
        total += stop - moment
        moment = stop
    return total
