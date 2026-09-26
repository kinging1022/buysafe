from django.conf import settings
from django.db import models


class Transaction(models.Model):
    """An escrow deal on a listing. The buyer's money is HELD until the deal
    is COMPLETED (released to the seller) or refunded/cancelled."""

    class Status(models.TextChoices):
        PENDING_PAYMENT = "pending_payment", "Pending payment"
        HELD = "held", "Held"
        COMPLETED = "completed", "Completed"
        REFUNDED = "refunded", "Refunded"
        CANCELLED = "cancelled", "Cancelled"

    # Money is with buysafe: the listing shows as "in escrow".
    ACTIVE_STATUSES = [Status.HELD]

    listing = models.ForeignKey("listings.Listing", on_delete=models.PROTECT, related_name="transactions")
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="purchases")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING_PAYMENT)
    # Whole naira.
    amount = models.PositiveIntegerField()
    # What the seller receives after fees. Set when the deal completes.
    payout = models.PositiveIntegerField(null=True, blank=True)
    meetup_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["listing", "status"])]

    def __str__(self):
        return f"{self.listing} ({self.get_status_display()})"
