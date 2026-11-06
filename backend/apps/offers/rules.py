"""The offer rules. Money is whole naira."""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings

# An offer must be at least this share of the asking price...
MIN_OFFER_PERCENT = 60
# ...rounded up to the next whole ₦1,000.
MIN_OFFER_ROUND_TO = 1_000
NOTE_MAX_LENGTH = 280
# Offers one buyer can send on one listing (any outcome). After that, only Buy now.
MAX_OFFERS_PER_BUYER = 3


def min_offer(price: int) -> int:
    """₦185,000 -> ₦111,000."""
    step = 100 * MIN_OFFER_ROUND_TO
    return -(-price * MIN_OFFER_PERCENT // step) * MIN_OFFER_ROUND_TO


def max_offer(price: int) -> int:
    """Offers must be below the asking price (at full price, use Buy now)."""
    return price - 1


def offer_ttl() -> timedelta:
    return timedelta(minutes=settings.OFFER_TTL_MINUTES)


def as_dict(price: int, last_declined: int | None = None) -> dict:
    """For the offer form: the limits it checks as the buyer types. After a
    decline, a new offer must also be more than `last_declined_amount`."""
    return {
        "min_amount": min_offer(price),
        "min_percent": MIN_OFFER_PERCENT,
        "max_amount": max_offer(price),
        "last_declined_amount": last_declined,
        "max_offers": MAX_OFFERS_PER_BUYER,
    }
