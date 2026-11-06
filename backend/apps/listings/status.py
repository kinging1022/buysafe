"""What a seller sees for each listing, derived from approval + escrow.

In order:
1. is_deleted                      -> excluded everywhere
2. a completed transaction         -> sold
3. an active (held) transaction    -> in_escrow
4. approval rejected               -> rejected
5. approval pending                -> pending
6. otherwise (approved)            -> live

"Active" on the profile means live + in_escrow.

Everything is a queryset annotation, so a page of listings and the counts
each take one query.
"""

from django.db.models import Case, CharField, Count, Exists, IntegerField, OuterRef, Q, Subquery, Value, When
from django.db.models.functions import Coalesce

from apps.escrow.models import Transaction

from .models import Listing, ListingInterest, ListingPhoto

LIVE = "live"
IN_ESCROW = "in_escrow"
PENDING = "pending"
REJECTED = "rejected"
SOLD = "sold"

ACTIVE = [LIVE, IN_ESCROW]


def _transactions(statuses):
    return Transaction.objects.filter(listing=OuterRef("pk"), status__in=statuses)


def with_display_status(queryset):
    """Drops deleted listings and annotates `display_status`."""
    completed = _transactions([Transaction.Status.COMPLETED])
    active = _transactions(Transaction.ACTIVE_STATUSES)
    return (
        queryset.filter(is_deleted=False)
        .annotate(has_completed_tx=Exists(completed), has_active_tx=Exists(active))
        .annotate(
            display_status=Case(
                When(has_completed_tx=True, then=Value(SOLD)),
                When(has_active_tx=True, then=Value(IN_ESCROW)),
                When(approval_status=Listing.Approval.REJECTED, then=Value(REJECTED)),
                When(approval_status=Listing.Approval.PENDING, then=Value(PENDING)),
                default=Value(LIVE),
                output_field=CharField(),
            )
        )
    )


def with_card_details(queryset):
    """with_display_status() plus what the profile cards show."""
    completed = _transactions([Transaction.Status.COMPLETED]).order_by("-completed_at")
    active = _transactions(Transaction.ACTIVE_STATUSES).order_by("-created_at")
    interest_count = (
        ListingInterest.objects.filter(listing=OuterRef("pk"))
        .order_by()
        .values("listing")
        .annotate(n=Count("pk"))
        .values("n")
    )
    first_image = ListingPhoto.objects.filter(listing=OuterRef("pk")).order_by("position", "id").values("image")[:1]
    return with_display_status(queryset).annotate(
        interest_count=Coalesce(Subquery(interest_count, output_field=IntegerField()), 0),
        first_image=Subquery(first_image),
        meetup_at=Subquery(active.values("meetup_at")[:1]),
        payout=Subquery(completed.values("payout")[:1]),
        sold_at=Subquery(completed.values("completed_at")[:1]),
        # The deal page for "Open deal" / "Receipt" (older transactions have none).
        active_deal_id=Subquery(active.values("deal__id")[:1]),
        sold_deal_id=Subquery(completed.values("deal__id")[:1]),
    )


def listing_display_status(listing):
    """The display status of one listing, or None if it's deleted."""
    if getattr(listing, "display_status", None) is not None:
        return listing.display_status
    return with_display_status(Listing.objects.filter(pk=listing.pk)).values_list("display_status", flat=True).first()


def listing_stats(queryset):
    """{live, in_escrow, sold, all} for a queryset of listings, in one query."""
    return with_display_status(queryset).aggregate(
        live=Count("pk", filter=Q(display_status=LIVE)),
        in_escrow=Count("pk", filter=Q(display_status=IN_ESCROW)),
        sold=Count("pk", filter=Q(display_status=SOLD)),
        all=Count("pk"),
    )
