"""The listing hold, on its own so offers and listings can ask about it
without importing the payment services."""

from django.utils import timezone

from .models import ListingHold


def active_hold(listing, now=None):
    """The hold blocking other buyers right now, or None. A hold past its
    expiry counts as over even before the sweep releases it."""
    return (
        ListingHold.objects.filter(listing=listing, released_at__isnull=True, expires_at__gt=now or timezone.now())
        .select_related("intent")
        .first()
    )
