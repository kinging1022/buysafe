from django.conf import settings
from django.db import models

from apps.users.states import NG_STATES

# Photos per listing. Position 0 is the cover.
MIN_PHOTOS = 3
MAX_PHOTOS = 5


class Category(models.Model):
    """What a listing is (Phones & tablets, Furniture…). Seeded by a data
    migration; staff can reorder or retire categories in the admin."""

    name = models.CharField(max_length=60)
    slug = models.SlugField(max_length=60, unique=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Listing(models.Model):
    """An item a user has posted for sale. Staff approve or reject it before it
    goes live. What the seller sees (live, in escrow, sold…) is derived from
    this plus its escrow transactions: see status.py. Money is whole naira."""

    class Approval(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    class Condition(models.TextChoices):
        BRAND_NEW = "brand_new", "Brand new"
        LIKE_NEW = "like_new", "Like new"
        GOOD = "good", "Good"
        FAIR = "fair", "Fair"
        FOR_PARTS = "for_parts", "For parts"

    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="listings")
    title = models.CharField(max_length=120)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="listings")
    condition = models.CharField(max_length=20, choices=Condition.choices)
    description = models.TextField(max_length=1000)
    price = models.PositiveIntegerField()
    state = models.CharField(max_length=20, choices=NG_STATES, blank=True, db_index=True)
    area = models.CharField(max_length=60, blank=True)
    # Lowercase copy of `area` for case-insensitive filtering; set on save.
    area_normalized = models.CharField(max_length=60, blank=True, db_index=True, editable=False)
    approval_status = models.CharField(max_length=10, choices=Approval.choices, default=Approval.PENDING)
    # Shown to the seller on a rejected listing. Set by staff when rejecting.
    rejection_reason = models.CharField(max_length=200, blank=True)
    is_deleted = models.BooleanField(default=False)
    # Distinct viewers per day, not counting the seller. See views.record_view().
    view_count = models.PositiveIntegerField(default=0, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["seller", "is_deleted", "-created_at"]),
            models.Index(fields=["approval_status", "is_deleted", "-created_at"], name="listing_public_idx"),
            models.Index(fields=["price"], name="listing_price_idx"),
        ]

    def save(self, *args, **kwargs):
        self.area_normalized = " ".join(self.area.split()).lower()
        if kwargs.get("update_fields") is not None and "area" in kwargs["update_fields"]:
            kwargs["update_fields"] = {*kwargs["update_fields"], "area_normalized"}
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class ListingPhoto(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="listings/%Y/%m/")
    # Lowest first; position 0 is the cover photo on every card.
    position = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "id"]


class ListingInterest(models.Model):
    """A buyer asking about a listing ("N people asked about this").
    One row per buyer per listing."""

    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="interests")
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="listing_interests")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["listing", "buyer"], name="unique_interest_per_buyer")]


class ListingView(models.Model):
    """One viewer of a listing on one day, so `Listing.view_count` counts each
    person once a day. Signed-in viewers are keyed by user, others by a salted
    hash of their IP (the IP itself is never stored)."""

    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="views")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name="+")
    ip_hash = models.CharField(max_length=64, blank=True)
    date = models.DateField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["listing", "user", "date"], condition=models.Q(user__isnull=False), name="one_view_per_user_per_day"
            ),
            models.UniqueConstraint(
                fields=["listing", "ip_hash", "date"], condition=models.Q(user__isnull=True), name="one_view_per_ip_per_day"
            ),
        ]


class ListingQuestion(models.Model):
    """A buyer's public question on a listing, and the seller's one answer.
    Answered questions are public; a pending one is seen only by its asker and
    the owner; a removed one by no one (kept for moderation). See questions.py."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ANSWERED = "answered", "Answered"
        REMOVED = "removed", "Removed"

    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="questions")
    asker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="listing_questions")
    text = models.CharField(max_length=280)
    answer = models.CharField(max_length=500, blank=True)
    answered_at = models.DateTimeField(null=True, blank=True)
    answer_edited_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    removed_at = models.DateTimeField(null=True, blank=True)
    removed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["listing", "status"]),
            models.Index(fields=["asker", "listing", "created_at"]),
        ]

    def __str__(self):
        return self.text[:60]


class ListingQuestionEdit(models.Model):
    """The answer as it was before each edit."""

    question = models.ForeignKey(ListingQuestion, on_delete=models.CASCADE, related_name="edits")
    previous_answer = models.CharField(max_length=500)
    edited_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-edited_at"]
