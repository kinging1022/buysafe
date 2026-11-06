"""A deal: one paid-for listing, from the moment the buyer's transfer is
matched until the money is released to the seller or refunded. Every chat
belongs to exactly one deal. State changes live in services.py; views never
set a state themselves.

A Deal takes its PaymentIntent's id, so the "Deal 317" the buyer saw on the
transfer screen is /deals/317.
"""

from django.conf import settings
from django.db import models

from .storage import get_private_storage


class Deal(models.Model):
    class State(models.TextChoices):
        AWAITING_VIDEO = "awaiting_video", "Waiting for the seller’s live video"
        VIDEO_TO_RATE = "video_to_rate", "Waiting for the buyer to rate the video"
        # The 3rd video was rated Bad: the buyer picks a refund or the meetup.
        AWAITING_DECISION = "awaiting_decision", "Waiting for the buyer to decide"
        CHAT_OPEN = "chat_open", "Chat open: meet, then the buyer confirms"
        RELEASED = "released", "Released to the seller"
        REFUNDED = "refunded", "Refunded to the buyer"

    ACTIVE = [State.AWAITING_VIDEO, State.VIDEO_TO_RATE, State.AWAITING_DECISION, State.CHAT_OPEN]
    CLOSED = [State.RELEASED, State.REFUNDED]

    class Choice(models.TextChoices):
        REFUND = "refund", "Cancel for a full refund"
        CONTINUE = "continue", "Continue to the meetup"

    intent = models.OneToOneField("payments.PaymentIntent", on_delete=models.PROTECT, related_name="deal")
    # The accepted transfer: refunds go back to its sender, and nowhere else.
    inbound = models.OneToOneField("payments.InboundTransfer", on_delete=models.PROTECT, related_name="deal")
    transaction = models.OneToOneField("escrow.Transaction", on_delete=models.PROTECT, related_name="deal")
    listing = models.ForeignKey("listings.Listing", on_delete=models.PROTECT, related_name="deals")
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="deals_bought")
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="deals_sold")
    # Frozen when the payment is matched (calculate_fee); never recalculated.
    amount = models.PositiveIntegerField()
    fee = models.PositiveIntegerField()
    payout = models.PositiveIntegerField()
    fee_rate_label = models.CharField(max_length=20)  # "10%", "flat fee"

    state = models.CharField(max_length=20, choices=State.choices, default=State.AWAITING_VIDEO)
    video_count = models.PositiveSmallIntegerField(default=0)
    # When the current step started and must end (awake time: deadlines.py).
    step_started_at = models.DateTimeField(null=True, blank=True)
    current_deadline = models.DateTimeField(null=True, blank=True)
    # Set by the sweep while quiet hours pause the clock (for display).
    deadline_paused_at = models.DateTimeField(null=True, blank=True)
    buyer_choice_after_3_bad = models.CharField(max_length=10, choices=Choice.choices, blank=True)

    paid_at = models.DateTimeField()
    chat_opened_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    released_ref = models.CharField(max_length=100, blank=True)
    refund = models.OneToOneField(
        "payments.Refund", on_delete=models.PROTECT, null=True, blank=True, related_name="deal"
    )
    refunded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["buyer", "state"]),
            models.Index(fields=["seller", "state"]),
            models.Index(fields=["state", "current_deadline"]),
        ]

    def __str__(self):
        return f"Deal {self.pk} ({self.state})"

    def role_of(self, user):
        if user.pk == self.buyer_id:
            return "buyer"
        if user.pk == self.seller_id:
            return "seller"
        return None

    def other(self, user):
        return self.seller if user.pk == self.buyer_id else self.buyer


class LiveVideo(models.Model):
    """One of the seller's (up to 3) live videos. Recorded with the in-app
    camera, never picked from a gallery; the server checks it was just recorded."""

    class Verdict(models.TextChoices):
        PENDING = "pending", "Waiting for a rating"
        GOOD = "good", "Good"
        BAD = "bad", "Bad"
        AUTO_GOOD = "auto_good", "Not rated in time (counts as Good)"

    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name="videos")
    n = models.PositiveSmallIntegerField()
    file = models.FileField(storage=get_private_storage, upload_to="deal-videos/%Y/%m/")
    thumb = models.ImageField(storage=get_private_storage, upload_to="deal-videos/%Y/%m/", blank=True)
    mime = models.CharField(max_length=40)
    duration = models.FloatField()  # seconds
    captured_at = models.DateTimeField()  # what the device said
    container_created_at = models.DateTimeField(null=True, blank=True)  # from the file, when it has one
    received_at = models.DateTimeField()  # server clock: the one we trust
    # "RECORDED IN-APP · 29 SEP 5:52 PM · SURULERE", from server time and the listing's area.
    overlay_text = models.CharField(max_length=120)
    verdict = models.CharField(max_length=10, choices=Verdict.choices, default=Verdict.PENDING)
    # After Bad: {"chips": [...], "note": "..."} for the next video.
    instructions = models.JSONField(default=dict, blank=True)
    rated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["n"]
        constraints = [models.UniqueConstraint(fields=["deal", "n"], name="one_video_per_number")]


class Message(models.Model):
    """One item in a deal's chat. `sender` is null for system messages.
    Before the chat opens, contact details are masked in `masked_body` (what
    both people see); `body` keeps the original for moderation."""

    class Kind(models.TextChoices):
        TEXT = "text", "Text"
        PHOTO = "photo", "Photo"
        LIVE_VIDEO = "live_video", "Live video"
        SYSTEM = "system", "System"
        RATING = "rating", "Rating"
        INSTRUCTION = "instruction", "What to show next"
        MEETUP = "meetup", "Meetup"

    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    body = models.TextField(blank=True)
    masked_body = models.TextField(blank=True)
    # Structured details: the system event, a video's number, a rating, the
    # instruction chips, a meetup id.
    data = models.JSONField(default=dict, blank=True)
    attachment = models.FileField(storage=get_private_storage, upload_to="deal-photos/%Y/%m/", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    # What counts as unread (a Bad rating shows as the video's caption, not a message).
    UNREAD_KINDS = [Kind.TEXT, Kind.PHOTO, Kind.LIVE_VIDEO, Kind.INSTRUCTION, Kind.MEETUP]

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["deal", "created_at"]), models.Index(fields=["deal", "read_at"])]

    @property
    def shown_body(self):
        return self.masked_body or self.body


class Meetup(models.Model):
    class Status(models.TextChoices):
        PROPOSED = "proposed", "Proposed"
        CONFIRMED = "confirmed", "Confirmed by both"
        CANCELLED = "cancelled", "Replaced"

    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name="meetups")
    proposer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    when = models.DateTimeField()
    place = models.CharField(max_length=160)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PROPOSED)
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class Reminder(models.Model):
    """A reminder that went out. Unique per step, channel and number, so the
    sweep can run every minute without repeating one (and a step never gets
    a second automated call)."""

    class Channel(models.TextChoices):
        PUSH = "push", "In-app"
        SMS = "sms", "SMS"
        CALL = "call", "Automated call"

    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name="reminders")
    step = models.CharField(max_length=20)  # "video_2", "rate_1", "confirm"
    channel = models.CharField(max_length=5, choices=Channel.choices)
    n = models.PositiveSmallIntegerField(default=0)  # which reminder in the step
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["deal", "step", "channel", "n"], name="one_reminder_per_slot")
        ]


class VideoUpload(models.Model):
    """A resumable upload in progress: chunks append to a temp file until it's
    complete, then it becomes a LiveVideo."""

    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name="uploads")
    uploader = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    n = models.PositiveSmallIntegerField()
    size = models.PositiveIntegerField()
    mime = models.CharField(max_length=40)
    duration = models.FloatField()
    captured_at = models.DateTimeField()
    received_bytes = models.PositiveIntegerField(default=0)
    path = models.CharField(max_length=200)  # relative to PRIVATE_MEDIA_ROOT
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)


class DealReport(models.Model):
    """"Report a problem". Staff follow up; a no-show refund is done from the
    admin (DealAdmin) for now."""

    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name="reports")
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    text = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
