"""Paying into escrow by bank transfer, refunds and payouts. Views call these
and never set a status themselves.

    start_payment    Buy now / Pay for an accepted offer: checks, a 30-minute
                     ListingHold, a PaymentIntent and its virtual account.
                     Idempotent per buyer and listing while the hold lasts.
    cancel_payment   the buyer gives up: the hold is released
    expire_holds     the minute sweep: intents past 30 minutes expire
    record_transfer  the webhook: store the InboundTransfer once, then match it
                     (exact amount + active intent -> the deal opens; anything
                     else is refunded to the sender)
    refund_transfer  money back to the account it came from, minus the bank fee
                     only when the buyer caused it
    release_payout   the deal's frozen payout to the seller, exactly once
    send_refund / send_payout / send_fee / retry_transfers   talking to the provider
    transfer_succeeded / transfer_failed   the webhook (or the sweep) says where
                     a sent transfer ended up. Money is only gone once it's
                     SUCCESSFUL; our fee moves only after the payout is.

Never accept a transfer that doesn't exactly match an active intent. Never
refund anywhere but the transfer's sender account.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.mail import mail_admins
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.escrow.models import Transaction
from apps.listings import status as listing_status
from apps.listings.models import Listing
from apps.offers.models import Offer

from . import providers
from .holds import active_hold
from .models import (
    FeeTransfer,
    InboundTransfer,
    ListingHold,
    PaymentIntent,
    Payout,
    PayoutAccount,
    Refund,
    TransferStatus,
)
from .names import names_match

logger = logging.getLogger(__name__)

MAX_TRANSFER_ATTEMPTS = 8
# A SENT transfer we've heard nothing about for this long is looked up.
CHECK_SENT_AFTER = timedelta(minutes=10)


class PaymentError(Exception):
    """A rule was broken. `status` is the HTTP status the view returns."""

    def __init__(self, code, detail, status=400, **extra):
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status = status
        self.extra = extra

    def as_dict(self):
        return {"code": self.code, "detail": self.detail, **self.extra}


def hold_duration():
    return timedelta(minutes=settings.PAYMENT_HOLD_MINUTES)


def after_commit(task, *args):
    """Queue a Celery task once the current transaction commits."""
    transaction.on_commit(lambda: task.delay(*args))


# ---------------------------------------------------------------------------
# Who can pay


def payout_ready(seller) -> bool:
    """Listings can only take payment once the seller has a payout account."""
    return PayoutAccount.objects.filter(user=seller).exists()


def buy_blocker(listing, user, now=None):
    """Why `user` can't start paying for `listing` right now, as a
    PaymentError, or None. `user` may be signed out (only the listing-wide
    reasons apply then)."""
    if user.is_authenticated and listing.seller_id == user.pk:
        return PaymentError("own_listing", "You can’t buy your own listing.", status=403)
    if listing_status.listing_display_status(listing) != listing_status.LIVE:
        return PaymentError("not_live", "This item isn’t for sale right now.", status=409)
    if not payout_ready(listing.seller):
        return PaymentError("no_payout", "The seller hasn’t finished setup yet.", status=409)
    hold = active_hold(listing, now)
    if hold and (not user.is_authenticated or hold.buyer_id != user.pk):
        return PaymentError("held", "Someone is paying for this now.", status=409, available_at=hold.expires_at.isoformat())
    return None


def _price(listing, buyer, offer_id, now):
    """(amount, offer): the accepted offer's price while it's held, else the listing's."""
    if offer_id is None:
        return listing.price, None
    offer = Offer.objects.filter(pk=offer_id, listing=listing, buyer=buyer).first()
    if offer is None or not offer.price_hold_active(now):
        raise PaymentError(
            "offer_not_held", "This offer’s price is no longer held. You can still buy at full price.", status=409
        )
    return offer.amount, offer


# ---------------------------------------------------------------------------
# Intents and holds


def _release(hold, reason, now):
    if hold is not None and hold.released_at is None:
        hold.released_at = now
        hold.end_reason = reason
        hold.save(update_fields=["released_at", "end_reason"])


def _close_intent(intent, status, now):
    intent.status = status
    intent.closed_at = now
    intent.save(update_fields=["status", "closed_at"])


def _expire_intent(intent, now):
    _close_intent(intent, PaymentIntent.Status.EXPIRED, now)
    _release(getattr(intent, "hold", None), ListingHold.End.EXPIRED, now)


def _expire_due(queryset, now):
    """Expires the awaiting intents in `queryset` whose 30 minutes are up."""
    due = list(queryset.select_for_update().filter(status=PaymentIntent.Status.AWAITING, expires_at__lte=now))
    for intent in due:
        _expire_intent(intent, now)
    return len(due)


def start_payment(listing: Listing, buyer, offer_id=None) -> PaymentIntent:
    with transaction.atomic():
        listing = Listing.objects.select_for_update().get(pk=listing.pk)
        now = timezone.now()
        _expire_due(PaymentIntent.objects.filter(listing=listing), now)

        # Idempotent: the buyer's own hold returns the same transfer details.
        hold = active_hold(listing, now)
        if hold and hold.buyer_id == buyer.pk:
            return hold.intent

        blocker = buy_blocker(listing, buyer, now)
        if blocker:
            raise blocker
        amount, offer = _price(listing, buyer, offer_id, now)

        try:
            with transaction.atomic():
                intent = PaymentIntent.objects.create(
                    listing=listing, buyer=buyer, offer=offer, amount_expected=amount, expires_at=now + hold_duration()
                )
                ListingHold.objects.create(listing=listing, buyer=buyer, intent=intent, expires_at=intent.expires_at)
        except IntegrityError:  # another buyer's hold won the race
            raise PaymentError("held", "Someone is paying for this now.", status=409) from None

        try:
            account = providers.virtual_accounts().create(str(intent.pk), amount, intent.expires_at, buyer.email)
        except (providers.ProviderError, NotImplementedError):
            logger.exception("Virtual account for intent %s failed", intent.pk)
            raise PaymentError(
                "provider_unavailable", "We couldn’t set up the transfer. Try again in a moment.", status=503
            ) from None
        intent.virtual_account_number = account.account_number
        intent.virtual_account_bank = account.bank
        intent.virtual_account_name = account.account_name
        intent.virtual_account_ref = account.provider_ref or None
        intent.save(
            update_fields=["virtual_account_number", "virtual_account_bank", "virtual_account_name", "virtual_account_ref"]
        )
    return intent


def cancel_payment(intent: PaymentIntent, buyer) -> PaymentIntent:
    with transaction.atomic():
        Listing.objects.select_for_update().get(pk=intent.listing_id)
        intent = PaymentIntent.objects.select_for_update().get(pk=intent.pk)
        if intent.buyer_id != buyer.pk:
            raise PaymentError("not_found", "Not found.", status=404)
        now = timezone.now()
        _expire_due(PaymentIntent.objects.filter(pk=intent.pk), now)
        intent.refresh_from_db()
        if intent.status != PaymentIntent.Status.AWAITING:
            raise PaymentError("not_awaiting", "This payment is no longer waiting for a transfer.", status=409)
        _close_intent(intent, PaymentIntent.Status.CANCELLED, now)
        _release(getattr(intent, "hold", None), ListingHold.End.CANCELLED, now)
    return intent


def expire_holds(now=None) -> int:
    """The minute sweep. Returns how many intents expired. Money that arrives
    for them later is refunded in full (record_transfer)."""
    now = now or timezone.now()
    with transaction.atomic():
        return _expire_due(PaymentIntent.objects.all(), now)


# ---------------------------------------------------------------------------
# Inbound transfers (the webhook)


def _last4(account):
    return account[-4:]


def _listing_taken(listing, intent):
    """Another deal already holds or completed this listing."""
    return (
        Transaction.objects.filter(listing=listing, status__in=[Transaction.Status.HELD, Transaction.Status.COMPLETED])
        .exclude(deal__intent=intent)
        .exists()
    )


def record_transfer(incoming: providers.IncomingTransfer):
    """Store a transfer (once per provider_ref) and act on it. Returns
    (InboundTransfer, created)."""
    existing = InboundTransfer.objects.filter(provider_ref=incoming.provider_ref).first()
    if existing:
        return existing, False
    try:
        with transaction.atomic():
            return _record(incoming), True
    except IntegrityError:  # the same webhook, delivered twice at once
        return InboundTransfer.objects.get(provider_ref=incoming.provider_ref), False


def _find_intent(incoming):
    if incoming.account_ref:
        return PaymentIntent.objects.filter(virtual_account_ref=incoming.account_ref).first()
    return PaymentIntent.objects.filter(virtual_account_number=incoming.account_number).first()


def _record(incoming):
    intent = _find_intent(incoming)
    fields = dict(
        provider_ref=incoming.provider_ref,
        account_number=incoming.account_number or (intent.virtual_account_number if intent else ""),
        amount=Decimal(incoming.amount),
        sender_name=incoming.sender_name[:120],
        sender_bank=incoming.sender_bank[:60],
        sender_bank_code=incoming.sender_bank_code[:10],
        sender_account=incoming.sender_account,
        sender_account_last4=_last4(incoming.sender_account),
        received_at=incoming.received_at,
        session_id=incoming.session_id[:60],
    )
    if intent is None:
        inbound = InboundTransfer.objects.create(**fields, outcome=InboundTransfer.Outcome.REFUND_UNMATCHED)
        refund_transfer(inbound, Refund.Reason.UNMATCHED)
        logger.warning(
            "Transfer %s to unknown account ····%s refunded",
            inbound.provider_ref, (inbound.account_number or incoming.account_ref)[-4:],
        )
        return inbound

    # One transfer at a time per listing: this is what stops two buyers both
    # getting the item.
    listing = Listing.objects.select_for_update().get(pk=intent.listing_id)
    intent = PaymentIntent.objects.select_for_update().get(pk=intent.pk)
    now = timezone.now()
    if intent.status == PaymentIntent.Status.AWAITING and intent.expires_at <= now:
        _expire_intent(intent, now)

    if intent.status == PaymentIntent.Status.RECEIVED:
        outcome, reason = InboundTransfer.Outcome.REFUND_DUPLICATE, Refund.Reason.DUPLICATE
    elif intent.status != PaymentIntent.Status.AWAITING or _listing_taken(listing, intent):
        outcome, reason = InboundTransfer.Outcome.REFUND_LATE, Refund.Reason.LATE
    elif Decimal(incoming.amount) != Decimal(intent.amount_expected):
        outcome, reason = InboundTransfer.Outcome.REFUND_WRONG_AMOUNT, Refund.Reason.WRONG_AMOUNT
    else:
        outcome, reason = InboundTransfer.Outcome.ACCEPTED, None

    inbound = InboundTransfer.objects.create(**fields, matched_intent=intent, outcome=outcome)
    if outcome == InboundTransfer.Outcome.ACCEPTED:
        _accept(intent, inbound, listing, now)
        return inbound

    refund_transfer(inbound, reason)
    if intent.status != PaymentIntent.Status.RECEIVED:
        # The buyer's pay screen shows what happened (wrong amount / too late).
        if intent.status == PaymentIntent.Status.AWAITING:
            _release(getattr(intent, "hold", None), ListingHold.End.REFUNDED, now)
        _close_intent(intent, PaymentIntent.Status.REFUNDED, now)
    return inbound


def _accept(intent, inbound, listing, now):
    from apps.deals.services import open_deal
    from apps.offers.services import close_offers

    intent.status = PaymentIntent.Status.RECEIVED
    intent.received_at = now
    intent.closed_at = now
    intent.save(update_fields=["status", "received_at", "closed_at"])
    _release(getattr(intent, "hold", None), ListingHold.End.PAID, now)
    open_deal(intent, inbound, listing)
    close_offers(listing, paid_by=intent.buyer, keep=intent.offer, now=now)


# ---------------------------------------------------------------------------
# Refunds


def refund_transfer(inbound: InboundTransfer, reason: str, amount=None) -> Refund:
    """Send money back to the account it came from. The bank fee is deducted
    only when the buyer caused the refund (Refund.BUYER_FAULT). Call inside a
    transaction; the transfer starts after commit."""
    gross = Decimal(amount if amount is not None else inbound.amount)
    fee = Decimal(settings.REFUND_BANK_FEE) if reason in Refund.BUYER_FAULT else Decimal(0)
    fee = min(fee, gross)
    refund = Refund.objects.create(inbound=inbound, amount=gross - fee, fee=fee, reason=reason)
    if refund.amount > 0 and not (inbound.sender_account and inbound.sender_bank_code):
        # We don't know exactly where it came from (the provider left out the
        # sender, or its bank didn't match one code), so there's nowhere we're
        # allowed to send it: staff refund it by hand.
        refund.status = TransferStatus.MANUAL
        refund.last_error = "Sender account or bank unknown"
        refund.save(update_fields=["status", "last_error"])
        transaction.on_commit(
            lambda: mail_admins(
                f"buysafe: refund {refund.pk} needs a person",
                f"₦{refund.amount} ({refund.get_reason_display()}) for inbound {inbound.provider_ref}: "
                f"we don't have the sender's account and bank code (session {inbound.session_id or 'unknown'}).",
            )
        )
    elif refund.amount > 0:
        from .tasks import send_refund

        after_commit(send_refund, refund.pk)
    else:  # nothing left to send once the fee is taken
        refund.status = TransferStatus.SUCCESSFUL
        refund.save(update_fields=["status"])
    return refund


def _backoff(attempts):
    return timedelta(minutes=min(2 ** attempts, 360))


# Where a transfer can't move on from by itself.
FINAL = (TransferStatus.SUCCESSFUL, TransferStatus.GAVE_UP, TransferStatus.MANUAL)


def _send(obj, send_call, label):
    """Hand one refund or payout to the provider. Locked, so it can't go twice."""
    with transaction.atomic():
        obj = type(obj).objects.select_for_update().get(pk=obj.pk)
        if obj.status not in (TransferStatus.PENDING, TransferStatus.FAILED):
            return obj
        now = timezone.now()
        try:
            ref = send_call(obj)
        except (providers.ProviderError, NotImplementedError) as exc:
            obj.attempts += 1
            obj.last_error = str(exc)[:200]
            if obj.attempts >= MAX_TRANSFER_ATTEMPTS:
                obj.status = TransferStatus.GAVE_UP
                transaction.on_commit(
                    lambda: mail_admins(f"buysafe: {label} {obj.pk} failed {obj.attempts} times", obj.last_error)
                )
            else:
                obj.status = TransferStatus.FAILED
                obj.next_attempt_at = now + _backoff(obj.attempts)
            logger.warning("%s %s failed (attempt %s): %s", label, obj.pk, obj.attempts, obj.last_error)
        else:
            # The webhook can settle it before send() returns (it came within
            # a second in the sandbox): never move it back to SENT.
            model = type(obj)
            if model.objects.filter(pk=obj.pk, status__in=FINAL).exists():
                model.objects.filter(pk=obj.pk).update(provider_ref=ref, sent_at=obj.sent_at or now, last_error="")
                return model.objects.get(pk=obj.pk)
            obj.status = TransferStatus.SENT
            obj.provider_ref = ref
            obj.sent_at = now
            obj.last_error = ""
        obj.save()
    return obj


def send_refund(refund_id) -> Refund:
    refund = Refund.objects.select_related("inbound").get(pk=refund_id)
    inbound = refund.inbound
    return _send(
        refund,
        lambda r: providers.transfers().send(
            inbound.sender_bank_code,
            inbound.sender_account,  # always the account the money came from
            r.amount,
            f"buysafe refund {r.pk}",
            r.idempotency_key,
        ),
        "Refund",
    )


# ---------------------------------------------------------------------------
# Payouts


def release_payout(deal) -> Payout:
    """Create the deal's one Payout (the frozen amount) and send it after
    commit. Calling it again returns the same Payout: the unique deal and
    idempotency key mean the money can only move once."""
    account = PayoutAccount.objects.get(user=deal.seller)
    payout, created = Payout.objects.get_or_create(
        deal=deal,
        defaults=dict(
            amount=deal.payout,
            bank_code=account.bank_code,
            bank_name=account.bank_name,
            account_number=account.account_number,
            account_last4=account.account_last4,
            account_name=account.account_name,
            idempotency_key=f"payout-deal-{deal.pk}",
        ),
    )
    if created:
        from .tasks import send_payout

        after_commit(send_payout, payout.pk)
    return payout


def send_payout(payout_id) -> Payout:
    from apps.deals.models import Deal

    payout = Payout.objects.get(pk=payout_id)
    payout = _send(
        payout,
        lambda p: providers.transfers().send(
            p.bank_code, p.account_number, Decimal(p.amount), f"buysafe deal {p.deal_id}", p.idempotency_key
        ),
        "Payout",
    )
    if payout.status == TransferStatus.SENT:
        Deal.objects.filter(pk=payout.deal_id).update(released_ref=payout.provider_ref)
    return payout


def start_fee(deal) -> FeeTransfer | None:
    """Our fee for the deal, moved once its payout has arrived. None when
    there's no fee. Calling it again returns the same FeeTransfer."""
    if not deal.fee:
        return None
    fee, created = FeeTransfer.objects.get_or_create(deal=deal, defaults={"amount": deal.fee})
    if created:
        from .tasks import send_fee

        after_commit(send_fee, fee.pk)
    return fee


def send_fee(fee_id) -> FeeTransfer:
    fee = FeeTransfer.objects.get(pk=fee_id)
    fee = _send(
        fee,
        lambda f: providers.transfers().collect_fee(Decimal(f.amount), f"buysafe fee deal {f.deal_id}", f.idempotency_key),
        "Fee",
    )
    if fee.status == TransferStatus.SENT:  # an internal transfer: done when the provider answers
        FeeTransfer.objects.filter(pk=fee.pk, status=TransferStatus.SENT).update(status=TransferStatus.SUCCESSFUL)
        fee.refresh_from_db()
    return fee


def _find_transfer(provider_ref, reference=""):
    """The Refund or Payout a provider transfer belongs to, locked. By our
    reference too, for an event that beat send() back."""
    for model in (Refund, Payout):
        obj = model.objects.select_for_update().filter(provider_ref=provider_ref).first()
        if obj:
            return obj
    if reference:
        sender = providers.transfers()
        for model in (Refund, Payout):
            for obj in model.objects.select_for_update().filter(provider_ref="").exclude(status__in=FINAL):
                if sender.reference(obj.idempotency_key) == reference:
                    return obj
        # The lock above waited for send() to commit, which set provider_ref.
        for model in (Refund, Payout):
            obj = model.objects.select_for_update().filter(provider_ref=provider_ref).first()
            if obj:
                return obj
    return None


def transfer_succeeded(result: providers.TransferSucceeded):
    """The other bank has the money. A payout's fee moves now. Returns the
    Refund or Payout, or None."""
    with transaction.atomic():
        obj = _find_transfer(result.provider_ref, result.reference)
        if obj is None:
            logger.warning("Transfer success for unknown provider ref %s", result.provider_ref)
            return None
        if obj.status == TransferStatus.SUCCESSFUL:
            return obj  # told twice
        if obj.status in FINAL:
            label = type(obj).__name__
            transaction.on_commit(
                lambda: mail_admins(
                    f"buysafe: {label} {obj.pk} arrived after we marked it {obj.status}",
                    f"Provider ref {result.provider_ref}: check it by hand.",
                )
            )
            logger.error("%s %s arrived while %s", label, obj.pk, obj.status)
            return obj
        now = timezone.now()
        obj.status = TransferStatus.SUCCESSFUL
        obj.provider_ref = obj.provider_ref or result.provider_ref
        obj.sent_at = obj.sent_at or now
        obj.settled_at = now
        obj.session_id = result.session_id[:60]
        obj.last_error = ""
        obj.save()
        if isinstance(obj, Payout):
            start_fee(obj.deal)
    return obj


def transfer_failed(failure: providers.TransferFailed):
    """The provider failed or reversed a refund or payout after accepting it.
    It isn't resent automatically (the provider may refuse the same
    reference): staff are alerted. Returns the Refund or Payout, or None."""
    with transaction.atomic():
        obj = _find_transfer(failure.provider_ref, failure.reference)
        if obj is None:
            logger.warning("Transfer failure for unknown provider ref %s", failure.provider_ref)
            return None
        if obj.status != TransferStatus.GAVE_UP:
            label = type(obj).__name__
            obj.status = TransferStatus.GAVE_UP
            obj.provider_ref = obj.provider_ref or failure.provider_ref
            obj.last_error = failure.reason[:200]
            obj.save(update_fields=["status", "provider_ref", "last_error"])
            transaction.on_commit(
                lambda: mail_admins(f"buysafe: {label} {obj.pk} {failure.reason}", f"Provider ref {failure.provider_ref}")
            )
            logger.error("%s %s: %s", label, obj.pk, failure.reason)
        return obj


def check_sent(now=None) -> int:
    """Asks the provider about SENT refunds and payouts we've heard nothing
    about, in case a webhook was lost. Returns how many were settled."""
    now = now or timezone.now()
    sender = providers.transfers()
    settled = 0
    for model in (Refund, Payout):
        for obj in model.objects.filter(status=TransferStatus.SENT, sent_at__lte=now - CHECK_SENT_AFTER):
            try:
                result = sender.status(obj.provider_ref)
            except (providers.ProviderError, NotImplementedError):
                logger.warning("Couldn't check %s %s", model.__name__, obj.pk)
                continue
            if isinstance(result, providers.TransferSucceeded):
                transfer_succeeded(result)
                settled += 1
            elif isinstance(result, providers.TransferFailed):
                transfer_failed(result)
                settled += 1
    return settled


def retry_transfers(now=None) -> int:
    """The minute sweep: failed refunds and payouts whose backoff is over, and
    pending ones whose task was lost. Returns how many were tried."""
    now = now or timezone.now()
    stale = now - timedelta(minutes=5)
    due = Q(status=TransferStatus.FAILED, next_attempt_at__lte=now) | Q(status=TransferStatus.PENDING, created_at__lte=stale)
    tried = 0
    for refund_id in Refund.objects.filter(due).values_list("pk", flat=True):
        send_refund(refund_id)
        tried += 1
    for payout_id in Payout.objects.filter(due).values_list("pk", flat=True):
        send_payout(payout_id)
        tried += 1
    for fee_id in FeeTransfer.objects.filter(due).values_list("pk", flat=True):
        send_fee(fee_id)
        tried += 1
    check_sent(now)
    return tried


# ---------------------------------------------------------------------------
# The seller's payout account


def validate_account(bank_code, account_number):
    from .banks import bank_name

    if not bank_name(bank_code):
        raise PaymentError("invalid_bank", "Choose your bank.")
    if not (isinstance(account_number, str) and account_number.isdigit() and len(account_number) == 10):
        raise PaymentError("invalid_account", "Enter the 10-digit account number.")


def look_up_account(user, bank_code, account_number) -> dict:
    """Name enquiry. {account_name, matches}. Raises PaymentError."""
    validate_account(bank_code, account_number)
    try:
        name = providers.transfers().name_enquiry(bank_code, account_number)
    except (providers.ProviderError, NotImplementedError):
        raise PaymentError("lookup_failed", "We couldn’t reach the bank. Try again in a moment.", status=502) from None
    return {"account_name": name, "matches": names_match(user.first_name, user.last_name, name)}


def save_payout_account(user, bank_code, account_number) -> PayoutAccount:
    """Looks the name up again (never trusts the client's) and saves it if it
    matches. The caller checks the OTP when an existing account changes."""
    from .banks import bank_name

    result = look_up_account(user, bank_code, account_number)
    if not result["matches"]:
        raise PaymentError(
            "name_mismatch",
            "This account isn’t in your name.",
            account_name=result["account_name"],
        )
    account, _ = PayoutAccount.objects.update_or_create(
        user=user,
        defaults=dict(
            bank_code=bank_code,
            bank_name=bank_name(bank_code),
            account_number=account_number,
            account_last4=_last4(account_number),
            account_name=result["account_name"],
            verified_at=timezone.now(),
        ),
    )
    return account


def is_change(user, bank_code, account_number) -> bool:
    """True if saving would replace a different existing payout account."""
    existing = PayoutAccount.objects.filter(user=user).first()
    return existing is not None and (existing.bank_code, existing.account_number) != (bank_code, account_number)
