import hashlib

from django.core.cache import cache
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.offers import rules as offer_rules
from apps.offers.models import Offer
from apps.offers.serializers import MyOfferSerializer
from apps.offers.services import declined_notice, last_declined_amount, offer_blocker
from apps.payments.holds import active_hold
from apps.payments.models import PaymentIntent
from apps.payments.services import buy_blocker, payout_ready
from apps.users.permissions import IsVerifiedUser

from . import browse, fees
from . import status as listing_status
from .models import Category, Listing
from .serializers import (
    CategorySerializer,
    ListingDetailSerializer,
    ListingWriteSerializer,
    MyListingSerializer,
    OwnerListingSerializer,
    PublicListingSerializer,
)
from .viewing import record_view


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
    """GET /api/listings/{id}/ (public): the listing page, plus a `viewer` block
    saying what the person looking can do, and for the owner an `owner` block
    (the edit form's prefill, the fee at full price, views). Pending and
    rejected listings are the owner's only. Records a view.

    PATCH (owner): edit. Editing sends it back to review. Not editable in
    escrow or sold."""

    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [IsVerifiedUser()]

    def get_listing(self, request, pk):
        return get_object_or_404(Listing, pk=pk, seller=request.user, is_deleted=False)

    def get(self, request, pk):
        listing = get_object_or_404(
            listing_status.with_display_status(Listing.objects.select_related("seller", "category")).prefetch_related(
                "photos"
            ),
            pk=pk,
        )
        is_owner = request.user.is_authenticated and listing.seller_id == request.user.pk
        if not is_owner and listing.display_status in (listing_status.PENDING, listing_status.REJECTED):
            raise Http404
        record_view(listing, request)

        data = ListingDetailSerializer(listing).data
        data["offer_rules"] = offer_rules.as_dict(listing.price, last_declined_amount(listing, request.user))
        data["viewer"] = self.viewer(listing, request.user, is_owner)
        if is_owner:
            listing.refresh_from_db(fields=["view_count"])
            data["owner"] = {
                **OwnerListingSerializer(listing).data,
                "view_count": listing.view_count,
                # No payout account: the red "Buyers can’t pay for this yet." banner.
                "payout_ready": payout_ready(request.user),
            }
        return Response(data)

    @staticmethod
    def viewer(listing, user, is_owner):
        signed_in = user.is_authenticated
        my_offer = Offer.objects.open_to_buyer().filter(listing=listing, buyer=user).first() if signed_in else None
        accepted = Offer.objects.price_held().filter(listing=listing, buyer=user).first() if signed_in else None
        offer_block = offer_blocker(listing, user)
        buy_block = buy_blocker(listing, user)
        hold = active_hold(listing)
        mine = hold is not None and signed_in and hold.buyer_id == user.pk
        return {
            "is_owner": is_owner,
            "my_open_offer": MyOfferSerializer(my_offer).data if my_offer else None,
            # "Your ₦X offer wasn’t accepted." after a final decline.
            "declined_amount": None if my_offer else declined_notice(listing, user),
            # OFFER ACCEPTED · FIRST TO PAY GETS IT (the price is held until then).
            "accepted_offer": (
                {"id": accepted.pk, "amount": accepted.amount, "price_held_until": accepted.price_held_until}
                if accepted
                else None
            ),
            "can_offer": offer_block is None,
            "offer_reason": offer_block.code if offer_block else None,
            "can_buy": buy_block is None,
            # own_listing, not_live, no_payout ("The seller hasn’t finished setup
            # yet.") or held ("Someone is paying for this now.").
            "buy_reason": buy_block.code if buy_block else None,
            # Someone else's 30-minute payment window: when it frees up.
            "held_until": hold.expires_at if hold and not mine else None,
            # The viewer's own transfer in progress, to resume the pay screen.
            "my_payment": (
                {"id": hold.intent_id, "expires_at": hold.expires_at}
                if mine and hold.intent.status == PaymentIntent.Status.AWAITING
                else None
            ),
        }

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
