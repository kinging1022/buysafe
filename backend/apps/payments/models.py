"""Paying into escrow by bank transfer. There is no wallet and no balance:
money is only ever held for one deal, then released to the seller's payout
account or refunded to the account it came from.

    PaymentIntent    a buyer's 30-minute window to transfer an exact amount
                     into a virtual account made for it
    ListingHold      while an intent waits, nobody else can pay (one per listing)
    InboundTransfer  money that arrived, and what we did with it
    Refund           money going back: always to the InboundTransfer's sender
    PayoutAccount    where a seller is paid (name-matched to their profile)
    Payout           the one release of a deal's frozen payout to the seller

Money is whole naira, except transfers and refunds (Decimal): a transfer can
arrive with kobo, and that isn't the exact amount.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .crypto import EncryptedCharField


class PaymentIntent(models.Model):
    class Status(models.TextChoices):
        AWAITING = "awaiting", "Awaiting transfer"
        RECEIVED = "received", "Received"
        EXPIRED = "expired", "Expired"
        REFUNDED = "refunded", "Refunded"
        CANCELLED = "cancelled", "Cancelled"

    listing = models.ForeignKey("listings.Listing", on_delete=models.PROTECT, related_name="payment_intents")
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payment_intents")
    # The accepted offer this pays for, if any (its price instead of the listing's).
    offer = models.ForeignKey("offers.Offer", on_delete=models.PROTECT, null=True, blank=True, related_name="payment_intents")
    amount_expected = models.PositiveIntegerField()
    # Set right after creation (the provider needs our id as the deal ref).
    virtual_account_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    virtual_account_bank = models.CharField(max_length=40, blank=True)
    virtual_account_name = models.CharField(max_length=80, blank=True)
    # The provider's id for the account, when payments are reported against
    # it instead of the number (Anchor's PayWithTransfer reference).
    virtual_account_ref = models.CharField(max_length=100, unique=True, null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.AWAITING)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    received_at = models.DateTimeField(null=True, blank=True)
    # When it left `awaiting` for any reason.
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "expires_at"]), models.Index(fields=["listing", "buyer", "status"])]

    def __str__(self):
        return f"Intent {self.pk}: {self.amount_expected} for {self.listing_id} ({self.status})"


class ListingHold(models.Model):
    """While a buyer's intent waits for their transfer, every other buyer sees
    Buy now and Make an offer disabled. One active hold per listing."""

    class End(models.TextChoices):
        PAID = "paid", "Paid"
        CANCELLED = "cancelled", "Cancelled by the buyer"
        EXPIRED = "expired", "Expired"
        REFUNDED = "refunded", "Wrong amount, refunded"

    listing = models.ForeignKey("listings.Listing", on_delete=models.CASCADE, related_name="holds")
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    intent = models.OneToOneField(PaymentIntent, on_delete=models.CASCADE, related_name="hold")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    released_at = models.DateTimeField(null=True, blank=True)
    end_reason = models.CharField(max_length=10, choices=End.choices, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["listing"], condition=Q(released_at__isnull=True), name="one_active_hold_per_listing"
            )
        ]

    def is_active(self, now=None):
        return self.released_at is None and self.expires_at > (now or timezone.now())


class InboundTransfer(models.Model):
    """A transfer into one of our virtual accounts. Recorded once per
    provider_ref, however often the webhook repeats."""

    class Outcome(models.TextChoices):
        ACCEPTED = "accepted", "Accepted: exact amount, active intent"
        REFUND_WRONG_AMOUNT = "refund_wrong_amount", "Refunded minus the bank fee: wrong amount"
        REFUND_LATE = "refund_late", "Refunded in full: intent expired or item already paid for"
        REFUND_DUPLICATE = "refund_duplicate", "Refunded in full: this deal was already paid"
        REFUND_UNMATCHED = "refund_unmatched", "Refunded in full: no intent for this account"

    provider_ref = models.CharField(max_length=100, unique=True)
    account_number = models.CharField(max_length=20, db_index=True)  # the virtual account paid into
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    sender_name = models.CharField(max_length=120, blank=True)
    sender_bank = models.CharField(max_length=60, blank=True)
    sender_bank_code = models.CharField(max_length=10, blank=True)
    sender_account_last4 = models.CharField(max_length=4, blank=True)
    sender_account = EncryptedCharField()
    received_at = models.DateTimeField()
    # The NIP session id: what a bank needs to trace this transfer.
    session_id = models.CharField(max_length=60, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    matched_intent = models.ForeignKey(
        PaymentIntent, on_delete=models.PROTECT, null=True, blank=True, related_name="inbound_transfers"
    )
    outcome = models.CharField(max_length=20, choices=Outcome.choices)

    class Meta:
        ordering = ["-received_at"]

    def __str__(self):
        return f"{self.amount} from {self.sender_bank} ····{self.sender_account_last4} ({self.outcome})"


class TransferStatus(models.TextChoices):
    PENDING = "pending", "Pending"  # created, not yet handed to the provider
    SENT = "sent", "Sent"  # the provider accepted it; not final until SUCCESSFUL
    SUCCESSFUL = "successful", "Arrived"  # the other bank has it: only now is the money gone
    FAILED = "failed", "Failed"  # will be retried with backoff
    GAVE_UP = "gave_up", "Gave up"  # too many failures: staff were alerted
    MANUAL = "manual", "Needs a person"  # we don't know where to send it: staff were alerted


class Refund(models.Model):
    """Money going back to whoever sent it. There is no destination field: a
    refund can only go to its InboundTransfer's sender account."""

    class Reason(models.TextChoices):
        WRONG_AMOUNT = "wrong_amount", "Wrong amount"
        LATE = "late", "Arrived too late"
        DUPLICATE = "duplicate", "Paid twice"
        UNMATCHED = "unmatched", "No deal for this account"
        SELLER_MISSED_VIDEO = "seller_missed_video", "Seller missed the video deadline"
        CANCELLED_AFTER_3_BAD = "cancelled_after_3_bad", "Cancelled after 3 bad videos"
        NO_SHOW = "no_show", "Seller didn’t show up"

    # Only these deduct the bank fee: the buyer caused them.
    BUYER_FAULT = {Reason.WRONG_AMOUNT}

    inbound = models.ForeignKey(InboundTransfer, on_delete=models.PROTECT, related_name="refunds")
    amount = models.DecimalField(max_digits=14, decimal_places=2)  # what's sent back
    fee = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    reason = models.CharField(max_length=24, choices=Reason.choices)
    status = models.CharField(max_length=10, choices=TransferStatus.choices, default=TransferStatus.PENDING)
    provider_ref = models.CharField(max_length=100, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    settled_at = models.DateTimeField(null=True, blank=True)  # SUCCESSFUL
    session_id = models.CharField(max_length=60, blank=True)  # NIP session id, for a bank to trace it

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "next_attempt_at"])]

    @property
    def idempotency_key(self):
        return f"refund-{self.pk}"


class PayoutAccount(models.Model):
    """Where a seller is paid. Its name matched the seller's profile name when
    it was saved (see names.py). A listing can't take payment without one."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payout_account")
    bank_code = models.CharField(max_length=10)
    bank_name = models.CharField(max_length=60)
    account_number = EncryptedCharField()
    account_last4 = models.CharField(max_length=4)
    account_name = models.CharField(max_length=120)
    verified_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.bank_name} ····{self.account_last4} ({self.account_name})"


class Payout(models.Model):
    """A deal's frozen payout on its way to the seller. One per deal, with a
    fixed idempotency key, so it can only ever be sent once. The destination
    is a snapshot of the seller's payout account when the buyer confirmed."""

    deal = models.OneToOneField("deals.Deal", on_delete=models.PROTECT, related_name="payout_transfer")
    amount = models.PositiveIntegerField()
    bank_code = models.CharField(max_length=10)
    bank_name = models.CharField(max_length=60)
    account_number = EncryptedCharField()
    account_last4 = models.CharField(max_length=4)
    account_name = models.CharField(max_length=120)
    idempotency_key = models.CharField(max_length=60, unique=True)
    status = models.CharField(max_length=10, choices=TransferStatus.choices, default=TransferStatus.PENDING)
    provider_ref = models.CharField(max_length=100, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    settled_at = models.DateTimeField(null=True, blank=True)  # SUCCESSFUL
    session_id = models.CharField(max_length=60, blank=True)  # NIP session id, for a bank to trace it

    class Meta:
        indexes = [models.Index(fields=["status", "next_attempt_at"])]


class FeeTransfer(models.Model):
    """Our fee for a deal, moved from the deposit account to the revenue
    account once the seller's payout has arrived (never before: until then
    the money isn't settled). One per deal, with a fixed key, so it can only
    move once."""

    deal = models.OneToOneField("deals.Deal", on_delete=models.PROTECT, related_name="fee_transfer")
    amount = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=TransferStatus.choices, default=TransferStatus.PENDING)
    provider_ref = models.CharField(max_length=100, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["status", "next_attempt_at"])]

    @property
    def idempotency_key(self):
        return f"fee-deal-{self.deal_id}"

