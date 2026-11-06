"""The deal state machine: every change of state happens here, inside a
transaction with the deal row locked. Anything not allowed from the current
state raises DealError (HTTP 409).

    (payment matched)  -> awaiting_video     open_deal (from apps.payments)
    awaiting_video     -> video_to_rate      add_video (seller)
    awaiting_video     -> refunded           miss_video_deadline (sweep): full refund
    video_to_rate      -> chat_open          rate_video Good, or auto_good (sweep, at 2h)
    video_to_rate      -> awaiting_video     rate_video Bad, videos 1–2: a fresh 4h window
    video_to_rate      -> awaiting_decision  rate_video Bad on video 3
    awaiting_decision  -> refunded           decide "refund": full refund
    awaiting_decision  -> chat_open          decide "continue"
    chat_open          -> released           confirm_receipt (buyer): the frozen payout, once
    chat_open          -> refunded           refund_no_show (staff, from the admin)

Before chat_open the seller can only send live videos, and contact details
in the buyer's messages are masked. The fee and payout are frozen at
open_deal and never recalculated. Refunds go to the paying account only.
"""

from __future__ import annotations

import logging

from django.core.mail import mail_admins
from django.db import transaction
from django.utils import timezone

from apps.escrow.models import Transaction
from apps.listings.contact_guard import mask_contacts
from apps.listings.fees import calculate_fee
from apps.listings.photos import process_photo
from apps.notifications import sms
from apps.notifications.clock import lagos, short_title
from apps.notifications.services import notify
from apps.payments.models import Refund

from . import reminders, rules
from .deadlines import deadline_after, in_quiet_hours
from .models import Deal, DealReport, LiveVideo, Meetup, Message

logger = logging.getLogger(__name__)


class DealError(Exception):
    def __init__(self, code, detail, status=409, **extra):
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status = status
        self.extra = extra

    def as_dict(self):
        return {"code": self.code, "detail": self.detail, **self.extra}


def _lock(deal) -> Deal:
    return Deal.objects.select_for_update().select_related("listing", "buyer", "seller", "inbound").get(pk=deal.pk)


def _require(deal, *states):
    if deal.state not in states:
        raise DealError("wrong_state", "That can’t be done at this stage of the deal.", state=deal.state)


def _require_role(deal, user, role):
    if deal.role_of(user) != role:
        raise DealError("not_allowed", "Only the " + role + " can do that.", status=403)


def _system(deal, event, **data):
    return Message.objects.create(deal=deal, kind=Message.Kind.SYSTEM, body=event, data=data)


def _start_step(deal, state, hours, now):
    deal.state = state
    deal.step_started_at = now
    deal.current_deadline = deadline_after(now, hours) if hours else None
    deal.deadline_paused_at = now if hours and in_quiet_hours(now) else None


def whose_turn(deal) -> str | None:
    """"buyer", "seller" or None: who the deal is waiting on right now."""
    return {
        Deal.State.AWAITING_VIDEO: "seller",
        Deal.State.VIDEO_TO_RATE: "buyer",
        Deal.State.AWAITING_DECISION: "buyer",
    }.get(deal.state)


# ---------------------------------------------------------------------------
# Opening


def open_deal(intent, inbound, listing) -> Deal:
    """The buyer's transfer matched: the money is held and the seller's 4
    hours to send a live video start. Called by apps.payments inside its
    transaction, with the listing locked."""
    now = timezone.now()
    quote = calculate_fee(intent.amount_expected)
    tx = Transaction.objects.create(
        listing=listing, buyer=intent.buyer, status=Transaction.Status.HELD, amount=quote.price
    )
    deal = Deal(
        id=intent.pk,
        intent=intent,
        inbound=inbound,
        transaction=tx,
        listing=listing,
        buyer=intent.buyer,
        seller=listing.seller,
        amount=quote.price,
        fee=quote.fee,
        payout=quote.payout,
        fee_rate_label=quote.rate_label,
        paid_at=now,
    )
    _start_step(deal, Deal.State.AWAITING_VIDEO, rules.VIDEO_HOURS, now)
    deal.save(force_insert=True)
    _system(deal, "paid", amount=deal.amount)
    reminders.send_due(deal, now)
    return deal


# ---------------------------------------------------------------------------
# Live videos


def overlay_text(received_at, area) -> str:
    """"RECORDED IN-APP · 29 SEP 5:52 PM · SURULERE" (server time)."""
    local = lagos(received_at)
    clock = f"{local.hour % 12 or 12}:{local.minute:02d} {'AM' if local.hour < 12 else 'PM'}"
    parts = ["RECORDED IN-APP", f"{local.day} {local.strftime('%b').upper()} {clock}"]
    if area:
        parts.append(area.upper())
    return " · ".join(parts)


def add_video(deal, seller, *, file_name, mime, duration, captured_at, container_created_at, now=None) -> LiveVideo:
    """The seller's live video arrived (already checked by the upload view)."""
    now = now or timezone.now()
    with transaction.atomic():
        deal = _lock(deal)
        _require_role(deal, seller, "seller")
        _require(deal, Deal.State.AWAITING_VIDEO)
        n = deal.video_count + 1
        video = LiveVideo.objects.create(
            deal=deal,
            n=n,
            file=file_name,
            mime=mime,
            duration=duration,
            captured_at=captured_at,
            container_created_at=container_created_at,
            received_at=now,
            overlay_text=overlay_text(now, deal.listing.area),
        )
        deal.video_count = n
        _start_step(deal, Deal.State.VIDEO_TO_RATE, rules.RATE_HOURS, now)
        deal.save()
        Message.objects.create(deal=deal, sender=seller, kind=Message.Kind.LIVE_VIDEO, data={"video_id": video.pk, "n": n})
        reminders.send_due(deal, now)
    return video


def _open_chat(deal, now):
    deal.state = Deal.State.CHAT_OPEN
    deal.chat_opened_at = now
    deal.step_started_at = now
    deal.current_deadline = None
    deal.deadline_paused_at = None


def rate_video(deal, buyer, n, verdict, chips=(), note="") -> Deal:
    now = timezone.now()
    with transaction.atomic():
        deal = _lock(deal)
        _require_role(deal, buyer, "buyer")
        _require(deal, Deal.State.VIDEO_TO_RATE)
        video = deal.videos.filter(n=n).first()
        if video is None or n != deal.video_count or video.verdict != LiveVideo.Verdict.PENDING:
            raise DealError("not_current", "That video can’t be rated now.")
        if verdict not in (LiveVideo.Verdict.GOOD, LiveVideo.Verdict.BAD):
            raise DealError("invalid", "Rate it Good or Bad.", status=400)
        video.verdict = verdict
        video.rated_at = now

        if verdict == LiveVideo.Verdict.GOOD:
            video.save(update_fields=["verdict", "rated_at"])
            Message.objects.create(
                deal=deal, sender=buyer, kind=Message.Kind.RATING, data={"n": n, "verdict": verdict}
            )
            _open_chat(deal, now)
            deal.save()
            return deal

        chips = list(dict.fromkeys(chips or []))
        if any(chip not in rules.INSTRUCTION_CHIPS for chip in chips):
            raise DealError("invalid", "Pick from the suggestions.", status=400)
        note = " ".join((note or "").split())
        if len(note) > rules.INSTRUCTION_NOTE_MAX:
            raise DealError("invalid", f"Keep it under {rules.INSTRUCTION_NOTE_MAX} characters.", status=400)
        note = mask_contacts(note)  # the chat isn't open yet
        video.instructions = {"chips": chips, "note": note}
        video.save(update_fields=["verdict", "rated_at", "instructions"])
        Message.objects.create(deal=deal, sender=buyer, kind=Message.Kind.RATING, data={"n": n, "verdict": verdict})

        if n < rules.MAX_VIDEOS:
            Message.objects.create(
                deal=deal,
                sender=buyer,
                kind=Message.Kind.INSTRUCTION,
                data={"next_n": n + 1, "chips": chips, "note": note},
            )
            # A fresh 4-hour window for the next video.
            _start_step(deal, Deal.State.AWAITING_VIDEO, rules.VIDEO_HOURS, now)
            deal.save()
            reminders.send_due(deal, now)
        else:
            deal.state = Deal.State.AWAITING_DECISION
            deal.step_started_at = now
            deal.current_deadline = None
            deal.deadline_paused_at = None
            deal.save()
    return deal


def auto_good(deal, now=None) -> Deal:
    """The buyer didn't rate in time: it counts as Good and the chat opens."""
    now = now or timezone.now()
    with transaction.atomic():
        deal = _lock(deal)
        _require(deal, Deal.State.VIDEO_TO_RATE)
        if deal.current_deadline is None or deal.current_deadline > now:
            raise DealError("not_due", "The buyer still has time to rate the video.")
        video = deal.videos.get(n=deal.video_count)
        video.verdict = LiveVideo.Verdict.AUTO_GOOD
        video.rated_at = now
        video.save(update_fields=["verdict", "rated_at"])
        Message.objects.create(deal=deal, kind=Message.Kind.RATING, data={"n": video.n, "verdict": video.verdict})
        _open_chat(deal, now)
        deal.save()
    return deal


def decide(deal, buyer, choice) -> Deal:
    """After the 3rd Bad: a full refund, or on to the meetup."""
    now = timezone.now()
    with transaction.atomic():
        deal = _lock(deal)
        _require_role(deal, buyer, "buyer")
        _require(deal, Deal.State.AWAITING_DECISION)
        if choice not in (Deal.Choice.REFUND, Deal.Choice.CONTINUE):
            raise DealError("invalid", "Choose a refund or the meetup.", status=400)
        deal.buyer_choice_after_3_bad = choice
        if choice == Deal.Choice.REFUND:
            _refund(deal, Refund.Reason.CANCELLED_AFTER_3_BAD, now)
        else:
            _open_chat(deal, now)
            _system(deal, "chat_unlocked")
        deal.save()
    return deal


# ---------------------------------------------------------------------------
# Closing


def _refund(deal, reason, now):
    """Full refund of the deal to the paying account. Never charged a fee:
    none of the deal refunds are the buyer's fault."""
    from apps.payments.services import refund_transfer

    deal.refund = refund_transfer(deal.inbound, reason, amount=deal.amount)
    deal.state = Deal.State.REFUNDED
    deal.refunded_at = now
    deal.current_deadline = None
    deal.deadline_paused_at = None
    Transaction.objects.filter(pk=deal.transaction_id).update(status=Transaction.Status.REFUNDED)
    why = f"{deal.seller.first_name} didn’t send a video in time." if reason == Refund.Reason.SELLER_MISSED_VIDEO else ""
    notify(
        deal.buyer,
        "deal_refunded",
        {"deal_id": deal.pk, "amount": deal.amount, "bank_name": deal.inbound.sender_bank, "why": why},
    )


def miss_video_deadline(deal, now=None) -> Deal:
    """The seller's 4 hours ran out without a video: cancelled, full refund."""
    now = now or timezone.now()
    with transaction.atomic():
        deal = _lock(deal)
        _require(deal, Deal.State.AWAITING_VIDEO)
        if deal.current_deadline is None or deal.current_deadline > now:
            raise DealError("not_due", "The seller still has time to send the video.")
        _system(deal, "video_missed", hours=rules.VIDEO_HOURS)
        _refund(deal, Refund.Reason.SELLER_MISSED_VIDEO, now)
        deal.save()
    return deal


def refund_no_show(deal, staff_user) -> Deal:
    """Staff, after a "Report a problem" about a no-show. The admin action."""
    now = timezone.now()
    with transaction.atomic():
        deal = _lock(deal)
        _require(deal, Deal.State.CHAT_OPEN, Deal.State.AWAITING_DECISION)
        _system(deal, "no_show")
        _refund(deal, Refund.Reason.NO_SHOW, now)
        deal.save()
    logger.info("Deal %s refunded for a no-show by %s", deal.pk, staff_user)
    return deal


def confirm_receipt(deal, buyer, checked: bool) -> Deal:
    """The buyer has the item: the frozen payout goes to the seller's payout
    account, exactly once."""
    from apps.payments.services import release_payout

    if not checked:
        raise DealError("unchecked", "Tick the box to confirm you have the item.", status=400)
    now = timezone.now()
    with transaction.atomic():
        deal = _lock(deal)
        _require_role(deal, buyer, "buyer")
        _require(deal, Deal.State.CHAT_OPEN)
        deal.state = Deal.State.RELEASED
        deal.confirmed_at = now
        deal.released_at = now
        deal.save()
        payout = release_payout(deal)
        Transaction.objects.filter(pk=deal.transaction_id).update(
            status=Transaction.Status.COMPLETED, payout=deal.payout, completed_at=now
        )
        _system(deal, "released", amount=deal.amount)
        notify(
            deal.seller,
            "money_released",
            {"deal_id": deal.pk, "amount": deal.payout, "bank_name": payout.bank_name, "last4": payout.account_last4},
        )
        sms.send(
            deal.seller,
            "money_released",
            amount=deal.payout,
            title=short_title(deal.listing.title),
            bank=payout.bank_name,
            last4=payout.account_last4,
        )
    return deal


# ---------------------------------------------------------------------------
# Chat


def send_message(deal, user, *, body="", photo=None) -> Message:
    """Text or a photo. The seller can't send either before the chat opens
    (only live videos); nobody can once the deal is closed."""
    now = timezone.now()
    with transaction.atomic():
        deal = _lock(deal)
        role = deal.role_of(user)
        if role is None:
            raise DealError("not_found", "Not found.", status=404)
        if deal.state in Deal.CLOSED:
            raise DealError("closed", "This deal is closed. The chat stays readable.")
        if role == "seller" and deal.state != Deal.State.CHAT_OPEN:
            raise DealError(
                "locked", f"Your chat unlocks after {deal.buyer.first_name} rates your video.", status=403
            )
        if photo is not None:
            try:
                content = process_photo(photo)
            except Exception as exc:  # ValidationError from the photo pipeline
                raise DealError("invalid", " ".join(getattr(exc, "messages", [str(exc)])), status=400) from None
            message = Message(deal=deal, sender=user, kind=Message.Kind.PHOTO)
            message.attachment.save(content.name, content, save=False)
            message.save()
            return message
        body = (body or "").strip()
        if not body:
            raise DealError("invalid", "Write a message.", status=400)
        if len(body) > rules.MESSAGE_MAX:
            raise DealError("invalid", f"Keep it under {rules.MESSAGE_MAX:,} characters.", status=400)
        masked = mask_contacts(body) if deal.state != Deal.State.CHAT_OPEN else body
        return Message.objects.create(
            deal=deal,
            sender=user,
            kind=Message.Kind.TEXT,
            body=body,
            masked_body=masked if masked != body else "",
        )


def mark_read(deal, user, now=None) -> int:
    """The other person's messages are read once this user has loaded them."""
    return (
        Message.objects.filter(deal=deal, read_at__isnull=True, sender__isnull=False)
        .exclude(sender=user)
        .update(read_at=now or timezone.now())
    )


def propose_meetup(deal, user, when, place) -> Meetup:
    now = timezone.now()
    place = " ".join((place or "").split())
    with transaction.atomic():
        deal = _lock(deal)
        if deal.role_of(user) is None:
            raise DealError("not_found", "Not found.", status=404)
        _require(deal, Deal.State.CHAT_OPEN)
        if when <= now:
            raise DealError("invalid", "Pick a time in the future.", status=400)
        if not 2 <= len(place) <= rules.MEETUP_PLACE_MAX:
            raise DealError("invalid", "Say where you’ll meet.", status=400)
        deal.meetups.filter(status=Meetup.Status.PROPOSED).update(status=Meetup.Status.CANCELLED)
        meetup = Meetup.objects.create(deal=deal, proposer=user, when=when, place=place)
        Message.objects.create(deal=deal, sender=user, kind=Message.Kind.MEETUP, data={"meetup_id": meetup.pk})
    return meetup


def confirm_meetup(deal, user, meetup_id) -> Meetup:
    now = timezone.now()
    with transaction.atomic():
        deal = _lock(deal)
        if deal.role_of(user) is None:
            raise DealError("not_found", "Not found.", status=404)
        _require(deal, Deal.State.CHAT_OPEN)
        meetup = deal.meetups.filter(pk=meetup_id, status=Meetup.Status.PROPOSED).first()
        if meetup is None:
            raise DealError("not_proposed", "That meetup isn’t waiting for a reply.")
        if meetup.proposer_id == user.pk:
            raise DealError("own_proposal", "The other person confirms the meetup.")
        deal.meetups.filter(status=Meetup.Status.CONFIRMED).update(status=Meetup.Status.CANCELLED)
        meetup.status = Meetup.Status.CONFIRMED
        meetup.confirmed_at = now
        meetup.save(update_fields=["status", "confirmed_at"])
        # The profile's "in escrow" card shows the meetup time.
        Transaction.objects.filter(pk=deal.transaction_id).update(meetup_at=meetup.when)
    return meetup


def report_problem(deal, user, text) -> DealReport:
    text = (text or "").strip()
    if deal.role_of(user) is None:
        raise DealError("not_found", "Not found.", status=404)
    if not 10 <= len(text) <= 1000:
        raise DealError("invalid", "Tell us what happened (at least 10 characters).", status=400)
    report = DealReport.objects.create(deal=deal, reporter=user, text=text)
    transaction.on_commit(
        lambda: mail_admins(
            f"buysafe: problem reported on deal {deal.pk}",
            f"{user.first_name} {user.last_name} ({deal.role_of(user)}), state {deal.state}:\n\n{text}",
        )
    )
    return report


# ---------------------------------------------------------------------------
# The minute sweep


def sweep(now=None) -> dict:
    """Deadlines (refund missed videos, auto-Good late ratings) and
    reminders, for every active deal."""
    now = now or timezone.now()
    done = {"refunded": 0, "auto_good": 0, "reminders": 0}
    for deal_id in Deal.objects.filter(state__in=Deal.ACTIVE).values_list("pk", flat=True):
        deal = Deal.objects.select_related("listing", "buyer", "seller").get(pk=deal_id)
        due = deal.current_deadline is not None and deal.current_deadline <= now
        try:
            if due and deal.state == Deal.State.AWAITING_VIDEO:
                miss_video_deadline(deal, now)
                done["refunded"] += 1
                continue
            if due and deal.state == Deal.State.VIDEO_TO_RATE:
                auto_good(deal, now)
                done["auto_good"] += 1
                continue
        except DealError:
            continue  # changed since we looked
        with transaction.atomic():
            deal = _lock(deal)
            if deal.state not in Deal.ACTIVE:
                continue
            done["reminders"] += reminders.send_due(deal, now)
            paused = now if deal.current_deadline and in_quiet_hours(now) else None
            if (paused is None) != (deal.deadline_paused_at is None):
                deal.deadline_paused_at = paused
                deal.save(update_fields=["deadline_paused_at"])
    return done


def attention_count(user) -> int:
    """The "Deals & messages" badge: unread messages plus deals waiting on you."""
    from django.db.models import Q

    mine = Deal.objects.filter(Q(buyer=user) | Q(seller=user))
    unread = (
        Message.objects.filter(deal__in=mine, read_at__isnull=True, sender__isnull=False, kind__in=Message.UNREAD_KINDS)
        .exclude(sender=user)
        .count()
    )
    turns = (
        mine.filter(buyer=user, state__in=[Deal.State.VIDEO_TO_RATE, Deal.State.AWAITING_DECISION]).count()
        + mine.filter(seller=user, state=Deal.State.AWAITING_VIDEO).count()
    )
    return unread + turns
