"""Creating and cancelling notifications. Call inside the action's transaction."""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from .kinds import KINDS
from .models import Notification


def notify(user, kind: str, data: dict, *, ref: str = "", delay: timedelta | None = None) -> Notification:
    if kind not in KINDS:
        raise ValueError(f"Unknown notification kind: {kind}")
    return Notification.objects.create(
        user=user, kind=kind, data=data, ref=ref, visible_at=timezone.now() + (delay or timedelta())
    )


def cancel(ref: str, now=None) -> int:
    """Deletes the not-yet-visible notifications for `ref` (an undone action).
    Returns how many; 0 if they've already been shown."""
    now = now or timezone.now()
    deleted, _ = Notification.objects.filter(ref=ref, visible_at__gt=now).delete()
    return deleted
