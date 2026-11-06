from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

# A declined offer can be undone (back to pending) for this long, and the
# buyer isn't told until it's over.
UNDO_DECLINE_WINDOW = timedelta(seconds=60)


class OfferQuerySet(models.QuerySet):
    def open(self, now=None):
        """Pending and not yet past its expiry (the sweep may not have run yet)."""
        return self.filter(status=Offer.Status.PENDING, expires_at__gt=now or timezone.now())

    def undoable(self, now=None):
        """Declined within the Undo window."""
        return self.filter(status=Offer.Status.DECLINED, decided_at__gt=(now or timezone.now()) - UNDO_DECLINE_WINDOW)

    def price_held(self, now=None):
        """Accepted, and its price is still held for the buyer."""
        return self.filter(status=Offer.Status.ACCEPTED, price_held_until__gt=now or timezone.now())

    def open_to_buyer(self, now=None):
        """What the buyer sees as still waiting: open, or declined but still
        undoable (the buyer isn't told about a decline until the Undo window ends)."""
        now = now or timezone.now()
        return self.filter(
            Q(status=Offer.Status.PENDING, expires_at__gt=now)
            | Q(status=Offer.Status.DECLINED, decided_at__gt=now - UNDO_DECLINE_WINDOW)
        )


class Offer(models.Model):
    """A buyer's price for a listing, below the asking price. Offers are for
    negotiating the price only: no money moves. Money is whole naira.

    An accepted offer holds its price for the buyer until `price_held_until`,
    but doesn't reserve the item: anyone can still buy at full price, and the
    first to pay gets it. See services.py.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        WITHDRAWN = "withdrawn", "Withdrawn"
        EXPIRED = "expired", "Expired"
        DECLINED = "declined", "Declined"
        ACCEPTED = "accepted", "Accepted"
        # Someone paid for the item, so every other offer on it closed.
        CLOSED = "closed", "Closed"

    listing = models.ForeignKey("listings.Listing", on_delete=models.CASCADE, related_name="offers")
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="offers")
    amount = models.PositiveIntegerField()
    note = models.CharField(max_length=280, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    # When it left `pending` (withdrawn, expired, declined, accepted or closed).
    decided_at = models.DateTimeField(null=True, blank=True)
    # Accepted: the buyer can pay this price until then.
    price_held_until = models.DateTimeField(null=True, blank=True)

    objects = OfferQuerySet.as_manager()

    class Meta:
        ordering = ["-amount", "-created_at"]
        indexes = [models.Index(fields=["listing", "status"])]
        constraints = [
            # One open offer per buyer per listing.
            models.UniqueConstraint(
                fields=["listing", "buyer"],
                condition=Q(status="pending"),
                name="one_open_offer_per_buyer",
            ),
        ]

    def __str__(self):
        return f"{self.amount} on {self.listing} ({self.status})"

    def effective_status(self, now=None):
        """`expired` for a pending offer past its expiry that the sweep hasn't reached."""
        if self.status == self.Status.PENDING and self.expires_at <= (now or timezone.now()):
            return self.Status.EXPIRED
        return self.status

    def price_hold_active(self, now=None):
        return self.status == self.Status.ACCEPTED and bool(self.price_held_until) and self.price_held_until > (
            now or timezone.now()
        )

    def undo_until(self):
        """Until when a decline can be undone, or None if it isn't declined."""
        if self.status != self.Status.DECLINED or not self.decided_at:
            return None
        return self.decided_at + UNDO_DECLINE_WINDOW
