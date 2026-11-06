from datetime import timedelta

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.listings.models import Listing

from . import services
from .models import Offer
from .serializers import MyOfferSerializer, OfferCreateSerializer, OwnerOfferSerializer

# Withdrawn and expired offers stay on the owner's list this long.
CLOSED_VISIBLE_FOR = timedelta(days=7)


def error_response(err: services.OfferError):
    return Response(err.as_dict(), status=err.status)


class ListingOffersView(APIView):
    """GET /api/listings/{id}/offers/ (owner): open offers, highest first, then
    ones declined in the last 60s (still undoable), then withdrawn or expired
    in the last 7 days. POST (verified buyer): send an offer."""

    throttle_scope = "offers"

    def get_throttles(self):
        # Only sending is rate-limited; the owner's page polls GET every 20s.
        return super().get_throttles() if self.request.method == "POST" else []

    def get(self, request, pk):
        listing = get_object_or_404(Listing, pk=pk, seller=request.user, is_deleted=False)
        now = timezone.now()
        since = now - CLOSED_VISIBLE_FOR
        offers = (
            Offer.objects.filter(listing=listing)
            .filter(Q(status=Offer.Status.PENDING, expires_at__gt=since) | Q(decided_at__gte=since))
            # A decline leaves the list when its Undo window ends.
            .exclude(Q(status=Offer.Status.DECLINED) & ~Q(pk__in=Offer.objects.undoable(now).values("pk")))
            .select_related("buyer")
        )
        open_offers = sorted((o for o in offers if o.effective_status(now) == Offer.Status.PENDING), key=lambda o: (-o.amount, o.created_at))
        # Accepted, price still held: first, newest first.
        accepted = sorted((o for o in offers if o.price_hold_active(now)), key=lambda o: -o.decided_at.timestamp())
        closed = sorted(
            (o for o in offers if o.effective_status(now) != Offer.Status.PENDING and not o.price_hold_active(now)),
            # Declined (undoable) first, then the rest, most recent first.
            key=lambda o: (o.status != Offer.Status.DECLINED, -(o.decided_at or o.expires_at).timestamp()),
        )
        return Response(
            {
                "count": len(open_offers),
                "best": open_offers[0].amount if open_offers else None,
                "results": OwnerOfferSerializer(accepted + open_offers + closed, many=True).data,
            }
        )

    def post(self, request, pk):
        listing = get_object_or_404(Listing, pk=pk, is_deleted=False)
        serializer = OfferCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            offer = services.create_offer(listing, request.user, **serializer.validated_data)
        except services.OfferError as err:
            return error_response(err)
        return Response(MyOfferSerializer(offer).data, status=status.HTTP_201_CREATED)


class OfferDeclineView(APIView):
    """POST /api/offers/{id}/decline/ (the listing's owner). Undoable for 60s."""

    def post(self, request, pk):
        offer = get_object_or_404(Offer, pk=pk, listing__seller=request.user)
        try:
            offer = services.decline_offer(offer, request.user)
        except services.OfferError as err:
            return error_response(err)
        return Response(OwnerOfferSerializer(offer).data)


class OfferAcceptView(APIView):
    """POST /api/offers/{id}/accept/ (the listing's owner). The price is held
    for the buyer; the item stays buyable by anyone at full price."""

    def post(self, request, pk):
        offer = get_object_or_404(Offer, pk=pk, listing__seller=request.user)
        try:
            offer = services.accept_offer(offer, request.user)
        except services.OfferError as err:
            return error_response(err)
        return Response(OwnerOfferSerializer(offer).data)


class OfferUndoDeclineView(APIView):
    """POST /api/offers/{id}/undo-decline/ (the listing's owner), within 60s of declining."""

    def post(self, request, pk):
        offer = get_object_or_404(Offer, pk=pk, listing__seller=request.user)
        try:
            offer = services.undo_decline(offer, request.user)
        except services.OfferError as err:
            return error_response(err)
        return Response(OwnerOfferSerializer(offer).data)


class OfferWithdrawView(APIView):
    """POST /api/offers/{id}/withdraw/ (the buyer who sent it)."""

    def post(self, request, pk):
        offer = get_object_or_404(Offer, pk=pk, buyer=request.user)
        try:
            offer = services.withdraw_offer(offer, request.user)
        except services.OfferError as err:
            return error_response(err)
        return Response(MyOfferSerializer(offer).data)
