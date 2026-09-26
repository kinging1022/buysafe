import hashlib

from django.core.cache import cache
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.permissions import IsVerifiedUser

from . import browse, fees
from . import status as listing_status
from .models import Category, Listing
from .serializers import (
    CategorySerializer,
    ListingWriteSerializer,
    MyListingSerializer,
    OwnerListingSerializer,
    PublicListingSerializer,
)


class MyListingsPagination(PageNumberPagination):
    page_size = 12


class MyListingsView(ListAPIView):
    """GET /api/me/listings/?tab=active|all&page=  (newest first, 12 per page)"""

    serializer_class = MyListingSerializer
    pagination_class = MyListingsPagination

    def get_queryset(self):
        queryset = listing_status.with_card_details(Listing.objects.filter(seller=self.request.user))
        if self.request.query_params.get("tab") == "active":
            queryset = queryset.filter(display_status__in=listing_status.ACTIVE)
        return queryset.order_by("-created_at", "-id")


class MyListingStatsView(APIView):
    """GET /api/me/listing-stats/ -> {live, in_escrow, sold, all}"""

    def get(self, request):
        return Response(listing_status.listing_stats(Listing.objects.filter(seller=request.user)))


# ---------------------------------------------------------------------------
# Public browse, post an item, edit, fees


class BrowsePagination(PageNumberPagination):
    page_size = 24


class ListingsView(ListAPIView):
    """GET /api/listings/ (public): live listings with filters, 24 per page.
    POST (signed in, phone verified): create a listing with its 3–5 photos
    in one multipart request. It starts in review."""

    serializer_class = PublicListingSerializer
    pagination_class = BrowsePagination
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [IsVerifiedUser()]

    def get_queryset(self):
        return browse.browse_queryset(self.request.query_params)

    def post(self, request):
        serializer = ListingWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        listing = serializer.save(seller=request.user)
        return Response(OwnerListingSerializer(listing).data, status=status.HTTP_201_CREATED)


class ListingDetailView(APIView):
    """GET/PATCH /api/listings/{id}/: the owner's own listing (404 for anyone
    else). Editing sends it back to review. Not editable in escrow or sold."""

    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_listing(self, request, pk):
        return get_object_or_404(Listing, pk=pk, seller=request.user, is_deleted=False)

    def get(self, request, pk):
        return Response(OwnerListingSerializer(self.get_listing(request, pk)).data)

    def patch(self, request, pk):
        listing = self.get_listing(request, pk)
        if listing_status.listing_display_status(listing) in (listing_status.IN_ESCROW, listing_status.SOLD):
            return Response(
                {"code": "not_editable", "detail": "This item has a deal in progress or is sold, so it can’t be edited."},
                status=status.HTTP_409_CONFLICT,
            )
        serializer = ListingWriteSerializer(listing, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        listing.refresh_from_db()
        return Response(OwnerListingSerializer(listing).data)


class FacetsView(APIView):
    """GET /api/listings/facets/?state=&area= (public): counts for the state
    chips and the category list. Cached for 60 seconds."""

    permission_classes = [AllowAny]

    def get(self, request):
        state = request.query_params.get("state", "")
        area = " ".join(request.query_params.get("area", "").split()).lower()
        key = "facets:" + hashlib.sha1(f"{state}|{area}".encode()).hexdigest()
        data = cache.get(key)
        if data is None:
            data = browse.facets({"state": state, "area": area})
            cache.set(key, data, 60)
        return Response(data)


class CategoriesView(ListAPIView):
    """GET /api/categories/ (public): active categories in display order."""

    permission_classes = [AllowAny]
    serializer_class = CategorySerializer
    pagination_class = None
    queryset = Category.objects.filter(is_active=True)


class FeeQuoteView(APIView):
    """GET /api/listings/fee-quote/?price= : the fee, payout and tip for a price."""

    throttle_scope = "fee_quote"

    def get(self, request):
        raw = (request.query_params.get("price") or "").strip()
        if not raw.isdigit():
            return Response({"code": "invalid", "detail": "Enter the price in whole naira."}, status=400)
        price = int(raw)
        if price < fees.MIN_PRICE:
            return Response(
                {
                    "code": "below_minimum",
                    "detail": f"Minimum price is {fees.naira(fees.MIN_PRICE)}.",
                    "min_price": fees.MIN_PRICE,
                    # Which tier the price falls in, for the receipt's tag.
                    "tier_key": fees.tier_key_for(price),
                },
                status=400,
            )
        if price > fees.MAX_PRICE:
            return Response(
                {"code": "above_maximum", "detail": f"Maximum price is {fees.naira(fees.MAX_PRICE)}.", "max_price": fees.MAX_PRICE},
                status=400,
            )
        return Response(fees.calculate_fee(price).as_dict())


class FeeScheduleView(APIView):
    """GET /api/listings/fee-schedule/ (public): the tiers for "How the fee works"."""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response(fees.fee_schedule())
