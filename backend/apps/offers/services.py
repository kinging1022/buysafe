"""Offer state changes: one function per transition. Views call these and
never set a status themselves.

    (none)   -> pending    create_offer   buyer sends an offer; SMS + in-app to the seller
    pending  -> withdrawn  withdraw_offer buyer takes it back
    pending  -> expired    expire_offers  its 48h ran out; SMS to the buyer
    pending  -> declined   decline_offer  seller says no; the buyer is notified
                                          in the app once the 60s Undo window ends
    declined -> pending    undo_decline   within those 60s; the buyer never knows
    pending  -> accepted   accept_offer   seller says yes; the price is held for
                                          the buyer for OFFER_PRICE_HOLD_HOURS. The
                                          item stays buyable at full price by anyone:
                                          first to pay gets it
    pending/accepted -> closed  close_offers  someone paid (apps.payments)
"""

from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from apps.listings import status as listing_status
from apps.listings.models import Listing
from apps.notifications import sms
from apps.notifications.services import cancel as cancel_notification
from apps.notifications.services import notify
from apps.payments.holds import active_hold

from . import rules
from .models import UNDO_DECLINE_WINDOW, Offer


class OfferError(Exception):
    """A rule was broken. `status` is the HTTP status the view returns."""

    def __init__(self, code, detail, status=400, **extra):
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status = status
        self.extra = extra

    def as_dict(self):
        return {"code": self.code, "detail": self.detail, **self.extra}


def offer_blocker(listing, user):
    """Why `user` can't make an offer on `listing` right now, as an OfferError,
    or None. Doesn't check the amount."""
    if user.is_authenticated and listing.seller_id == user.pk:
        return OfferError("own_listing", "You can’t make an offer on your own listing.", status=403)
    if listing_status.listing_display_status(listing) != listing_status.LIVE:
        return OfferError("not_live", "This item isn’t taking offers.", status=409)
    hold = active_hold(listing)
    if hold and (not user.is_authenticated or hold.buyer_id != user.pk):
        return OfferError("held", "Someone is paying for this now.", status=409)
    if not user.is_authenticated:
        return None
    mine = Offer.objects.filter(listing=listing, buyer=user)
    if mine.price_held().exists():
        return OfferError("offer_accepted", "Your offer was accepted. Pay into escrow to get it.", status=409)
    if mine.open_to_buyer().exists():
        return OfferError("offer_open", "You already have an offer waiting on this item.", status=409)
    if mine.count() >= rules.MAX_OFFERS_PER_BUYER:
        return OfferError(
            "offer_limit",
            f"You’ve made {rules.MAX_OFFERS_PER_BUYER} offers on this item. You can still Buy now.",
            status=409,
        )
    return None


def _final_declines(listing, buyer):
    """The buyer's declined offers whose Undo window is over (the buyer knows)."""
    return Offer.objects.filter(
        listing=listing,
        buyer=buyer,
        status=Offer.Status.DECLINED,
        decided_at__lte=timezone.now() - UNDO_DECLINE_WINDOW,
    )


def last_declined_amount(listing, buyer):
    """The buyer's highest declined offer on this listing (a new one must beat it), or None."""
    if not buyer.is_authenticated:
        return None
    return _final_declines(listing, buyer).aggregate(m=Max("amount"))["m"]


def declined_notice(listing, buyer):
    """The amount for "Your ₦X offer wasn’t accepted." when the buyer's latest
    offer on this listing was declined (and it's final), else None."""
    if not buyer.is_authenticated:
        return None
    latest = Offer.objects.filter(listing=listing, buyer=buyer).order_by("-created_at").first()
    if latest and _final_declines(listing, buyer).filter(pk=latest.pk).exists():
        return latest.amount
    return None


def validate_amount(price, amount, last_declined=None):
    minimum = rules.min_offer(price)
    if amount < minimum:
        raise OfferError(
            "below_minimum",
            f"Offers must be at least ₦{minimum:,} ({rules.MIN_OFFER_PERCENT}% of the asking price).",
            min_amount=minimum,
        )
    if last_declined is not None and amount <= last_declined:
        raise OfferError(
            "not_above_declined",
            f"Your new offer must be more than ₦{last_declined:,}.",
            min_amount=last_declined + 1,
        )
    if amount >= price:
        raise OfferError("not_below_price", "That’s the full price. Just use Buy now.")


def create_offer(listing: Listing, buyer, amount: int, note: str = "") -> Offer:
    with transaction.atomic():
        # Lock the listing so two offers from one buyer can't slip past the check.
        listing = Listing.objects.select_for_update().get(pk=listing.pk)
        now = timezone.now()
        # A pending offer past its expiry still holds the unique constraint
        # until the sweep marks it; expire it now so the buyer can offer again.
        _expire(Offer.objects.filter(listing=listing, buyer=buyer, status=Offer.Status.PENDING, expires_at__lte=now), now)
        blocker = offer_blocker(listing, buyer)
        if blocker:
            raise blocker
        validate_amount(listing.price, amount, last_declined_amount(listing, buyer))
        try:
            with transaction.atomic():
                offer = Offer.objects.create(
                    listing=listing, buyer=buyer, amount=amount, note=note, expires_at=now + rules.offer_ttl()
                )
        except IntegrityError:
            raise OfferError("offer_open", "You already have an offer waiting on this item.", status=409) from None
        notify(
            listing.seller,
            "offer_new",
            {
                "listing_id": listing.pk,
                "listing_title": listing.title,
                "amount": amount,
                "buyer_name": f"{buyer.first_name} {buyer.last_name[:1].upper()}.",
            },
        )
        sms.send(listing.seller, "offer_new", amount=amount, title=listing.title)
    return offer


def withdraw_offer(offer: Offer, buyer) -> Offer:
    with transaction.atomic():
        offer = Offer.objects.select_for_update().get(pk=offer.pk)
        if offer.buyer_id != buyer.pk:
            raise OfferError("not_found", "Not found.", status=404)
        now = timezone.now()
        # A decline still in its Undo window looks pending to the buyer, so
        # withdrawing it works too (and the decline is never shown).
        undoable_decline = offer.status == Offer.Status.DECLINED and offer.undo_until() > now
        if offer.effective_status(now) != Offer.Status.PENDING and not undoable_decline:
            raise OfferError("not_pending", "This offer is no longer waiting for a reply.", status=409)
        if undoable_decline:
            cancel_notification(_declined_ref(offer), now)
        offer.status = Offer.Status.WITHDRAWN
        offer.decided_at = now
        offer.save(update_fields=["status", "decided_at"])
    return offer


def _lock_for_seller(offer, seller):
    """Locks the listing, then the offer. 404 unless `seller` owns the listing."""
    Listing.objects.select_for_update().get(pk=offer.listing_id)
    offer = Offer.objects.select_for_update().select_related("listing", "buyer").get(pk=offer.pk)
    if offer.listing.seller_id != seller.pk:
        raise OfferError("not_found", "Not found.", status=404)
    return offer


def _declined_ref(offer):
    return f"offer:{offer.pk}:declined"


def decline_offer(offer: Offer, seller) -> Offer:
    with transaction.atomic():
        offer = _lock_for_seller(offer, seller)
        if offer.effective_status() != Offer.Status.PENDING:
            raise OfferError("not_pending", "This offer is no longer waiting for a reply.", status=409)
        offer.status = Offer.Status.DECLINED
        offer.decided_at = timezone.now()
        offer.save(update_fields=["status", "decided_at"])
        # Shown to the buyer only once the Undo window is over. Never a reason.
        notify(
            offer.buyer,
            "offer_declined",
            {
                "amount": offer.amount,
                "listing_id": offer.listing_id,
                "listing_title": offer.listing.title,
                "seller_first_name": seller.first_name,
            },
            ref=_declined_ref(offer),
            delay=UNDO_DECLINE_WINDOW,
        )
    return offer


def undo_decline(offer: Offer, seller) -> Offer:
    with transaction.atomic():
        offer = _lock_for_seller(offer, seller)
        if offer.status != Offer.Status.DECLINED:
            raise OfferError("not_declined", "This offer isn’t declined.", status=409)
        now = timezone.now()
        if offer.undo_until() <= now:
            raise OfferError("too_late", "It’s too late to undo. The buyer has been told.", status=409)
        offer.status = Offer.Status.PENDING
        offer.decided_at = None
        offer.save(update_fields=["status", "decided_at"])
        cancel_notification(_declined_ref(offer), now)
    return offer


def accept_offer(offer: Offer, seller) -> Offer:
    with transaction.atomic():
        offer = _lock_for_seller(offer, seller)
        if offer.effective_status() != Offer.Status.PENDING:
            raise OfferError("not_pending", "This offer is no longer waiting for a reply.", status=409)
        if listing_status.listing_display_status(offer.listing) != listing_status.LIVE:
            raise OfferError("not_live", "This item isn’t taking offers.", status=409)
        now = timezone.now()
        offer.status = Offer.Status.ACCEPTED
        offer.decided_at = now
        offer.price_held_until = now + timedelta(hours=settings.OFFER_PRICE_HOLD_HOURS)
        offer.save(update_fields=["status", "decided_at", "price_held_until"])
        notify(
            offer.buyer,
            "offer_accepted",
            {
                "amount": offer.amount,
                "listing_id": offer.listing_id,
                "listing_title": offer.listing.title,
                "seller_first_name": seller.first_name,
                "held_until": offer.price_held_until.isoformat(),
            },
            ref=f"offer:{offer.pk}:accepted",
        )
        sms.send(
            offer.buyer,
            "offer_accepted",
            seller=seller.first_name,
            amount=offer.amount,
            title=offer.listing.title,
            until=offer.price_held_until,
        )
    return offer


def close_offers(listing: Listing, paid_by, keep: Offer = None, now=None) -> int:
    """Someone paid for the listing: every other pending or accepted offer on
    it closes, and their buyers (not the payer) are told. Call inside the
    payment's transaction, with the listing locked. Returns how many closed."""
    now = now or timezone.now()
    offers = Offer.objects.select_for_update().filter(
        listing=listing, status__in=[Offer.Status.PENDING, Offer.Status.ACCEPTED]
    )
    if keep is not None:
        offers = offers.exclude(pk=keep.pk)
    offers = list(offers.select_related("buyer"))
    Offer.objects.filter(pk__in=[o.pk for o in offers]).update(status=Offer.Status.CLOSED, decided_at=now)
    told = {paid_by.pk}
    for offer in offers:
        if offer.buyer_id in told:
            continue
        told.add(offer.buyer_id)
        notify(offer.buyer, "offer_closed", {"listing_id": listing.pk, "listing_title": listing.title})
    return len(offers)


def _expire(queryset, now):
    """Marks the given pending offers expired; returns them."""
    offers = list(queryset.select_for_update().select_related("buyer", "listing"))
    if offers:
        Offer.objects.filter(pk__in=[o.pk for o in offers]).update(status=Offer.Status.EXPIRED, decided_at=now)
    return offers


def expire_offers(now=None) -> int:
    """The sweep (every minute): pending offers past their expiry -> expired,
    with an SMS to each buyer. Returns how many expired."""
    now = now or timezone.now()
    with transaction.atomic():
        offers = _expire(Offer.objects.filter(status=Offer.Status.PENDING, expires_at__lte=now), now)
        for offer in offers:
            sms.send(offer.buyer, "offer_expired", amount=offer.amount, title=offer.listing.title)
    return len(offers)
