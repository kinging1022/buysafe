"""Public browse: which listings anyone can see, the filters, and the facet
counts. Only live listings (approved, not deleted, not sold, not in escrow)
are ever returned."""

from django.db.models import Count, OuterRef, Subquery

from apps.users.states import NG_STATES

from . import status as listing_status
from .models import Category, Listing, ListingPhoto

STATE_LABELS = dict(NG_STATES)
SORTS = {
    "newest": ["-created_at", "-id"],
    "price_asc": ["price", "-id"],
    "price_desc": ["-price", "-id"],
}
CONDITIONS = set(Listing.Condition.values)


def live_listings():
    return listing_status.with_display_status(Listing.objects.all()).filter(display_status=listing_status.LIVE)


def _whole_number(value):
    value = (value or "").strip()
    return int(value) if value.isdigit() else None


def _normalized_area(value):
    return " ".join((value or "").split()).lower()


def filter_location(queryset, params):
    """State and area only: the scope the facet counts use."""
    state = (params.get("state") or "").strip()
    if state:
        queryset = queryset.filter(state=state)
    area = _normalized_area(params.get("area"))
    if area:
        queryset = queryset.filter(area_normalized__contains=area)
    return queryset


def filter_listings(queryset, params):
    """Every browse filter. Unknown or malformed values are ignored, so a
    shared URL never errors."""
    queryset = filter_location(queryset, params)
    category = (params.get("category") or "").strip()
    if category:
        queryset = queryset.filter(category__slug=category)
    conditions = [c for c in (params.get("condition") or "").split(",") if c in CONDITIONS]
    if conditions:
        queryset = queryset.filter(condition__in=conditions)
    low, high = _whole_number(params.get("min")), _whole_number(params.get("max"))
    if low is not None:
        queryset = queryset.filter(price__gte=low)
    if high is not None:
        queryset = queryset.filter(price__lte=high)
    return queryset


def browse_queryset(params):
    cover = ListingPhoto.objects.filter(listing=OuterRef("pk")).order_by("position", "id").values("image")[:1]
    queryset = filter_listings(live_listings(), params).select_related("seller", "category")
    return queryset.annotate(cover=Subquery(cover)).order_by(*SORTS.get(params.get("sort"), SORTS["newest"]))


def facets(params):
    """Counts for the quick-pick state chips (nationwide) and the category list
    (scoped to the chosen state/area)."""
    live = live_listings()
    states = [
        {"key": row["state"], "label": STATE_LABELS.get(row["state"], row["state"]), "count": row["n"]}
        for row in live.exclude(state="").values("state").annotate(n=Count("pk")).order_by("-n", "state")
    ]
    scoped = filter_location(live, params)
    counts = dict(scoped.values_list("category_id").annotate(n=Count("pk")))
    categories = [
        {"slug": c.slug, "label": c.name, "count": counts.get(c.pk, 0)} for c in Category.objects.filter(is_active=True)
    ]
    return {
        "total": live.count(),
        "scoped_total": scoped.count(),
        "states": states,
        "categories": categories,
    }
