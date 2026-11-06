"""What the deals list, the deal page and the recording screen read. Every
payload is for one viewer: role-specific money, and the buyer's paying
account is only shown to the buyer. Money is whole naira."""

from __future__ import annotations

from django.utils import timezone

from apps.payments.banks import short_bank_name
from apps.payments.models import PayoutAccount

from . import rules
from .deadlines import awake_time_between, in_quiet_hours
from .models import Deal, LiveVideo, Meetup, Message
from .services import whose_turn


def person(user, role):
    return {
        "first_name": user.first_name,
        "last_initial": user.last_name[:1].upper(),
        "avatar_color": user.avatar_color,
        "verified": user.phone_verified,
        "role": role,
    }


def _photo(listing):
    photo = listing.photos.first()
    return photo.image.url if photo else None


def _timing(deal, now):
    if deal.current_deadline is None:
        return {"deadline": None, "seconds_left": None, "paused": False}
    return {
        "deadline": deal.current_deadline,
        "seconds_left": int(awake_time_between(now, deal.current_deadline).total_seconds()),
        "paused": in_quiet_hours(now),
    }


def _turn(deal, role):
    turn = whose_turn(deal)
    return None if turn is None else ("me" if turn == role else "them")


def video_data(deal, video: LiveVideo):
    return {
        "n": video.n,
        "url": f"/api/deals/{deal.pk}/videos/{video.n}/file/",
        "thumb_url": f"/api/deals/{deal.pk}/videos/{video.n}/thumb/" if video.thumb else None,
        "mime": video.mime,
        "duration": round(video.duration),
        "verdict": video.verdict,
        "overlay_text": video.overlay_text,
        "received_at": video.received_at,
        "rated_at": video.rated_at,
        "instructions": video.instructions or None,
    }


def meetup_data(meetup: Meetup, viewer):
    return {
        "id": meetup.pk,
        "when": meetup.when,
        "place": meetup.place,
        "status": meetup.status,
        "mine": meetup.proposer_id == viewer.pk,
    }


def _current_meetup(deal):
    meetups = [m for m in deal.meetups.all() if m.status != Meetup.Status.CANCELLED]
    confirmed = [m for m in meetups if m.status == Meetup.Status.CONFIRMED]
    return (confirmed or meetups or [None])[0]


def _refund(deal, role):
    if not deal.refund_id:
        return None
    refund = deal.refund
    data = {"reason": refund.reason, "amount": deal.amount, "at": deal.refunded_at}
    if role == "buyer":
        data.update(bank=deal.inbound.sender_bank, last4=deal.inbound.sender_account_last4)
    return data


def _payout_account(deal):
    """Where the seller is (or was) paid: the Payout's snapshot once released."""
    payout = getattr(deal, "payout_transfer", None) if deal.state == Deal.State.RELEASED else None
    if payout is not None:
        return {"bank_name": payout.bank_name, "bank_short": short_bank_name(payout.bank_name), "last4": payout.account_last4}
    account = PayoutAccount.objects.filter(user_id=deal.seller_id).first()
    if account is None:
        return None
    return {"bank_name": account.bank_name, "bank_short": short_bank_name(account.bank_name), "last4": account.account_last4}


def _unread(deal, viewer):
    return sum(
        1
        for m in deal.messages.all()
        if m.read_at is None and m.sender_id and m.sender_id != viewer.pk and m.kind in Message.UNREAD_KINDS
    )


def deal_row(deal: Deal, viewer, now=None) -> dict:
    """One row on the deals list."""
    now = now or timezone.now()
    role = deal.role_of(viewer)
    meetup = _current_meetup(deal)
    row = {
        "id": deal.pk,
        "state": deal.state,
        "role": role,
        "turn": _turn(deal, role),
        "listing": {"id": deal.listing_id, "title": deal.listing.title, "photo": _photo(deal.listing)},
        "other": person(deal.other(viewer), "seller" if role == "buyer" else "buyer"),
        "video_count": deal.video_count,
        "amount": deal.amount,
        **_timing(deal, now),
        "meetup": meetup_data(meetup, viewer) if meetup else None,
        "released_at": deal.released_at,
        "refund": _refund(deal, role),
        "unread": _unread(deal, viewer),
        "created_at": deal.created_at,
    }
    if role == "seller":
        row["payout"] = deal.payout
        row["payout_account"] = _payout_account(deal) if deal.state == Deal.State.RELEASED else None
    return row


def deal_data(deal: Deal, viewer, now=None) -> dict:
    """The deal page."""
    now = now or timezone.now()
    role = deal.role_of(viewer)
    videos = list(deal.videos.all())
    accepted = next((v for v in videos if v.verdict in (LiveVideo.Verdict.GOOD, LiveVideo.Verdict.AUTO_GOOD)), None)
    last_bad = next((v for v in reversed(videos) if v.verdict == LiveVideo.Verdict.BAD), None)
    meetup = _current_meetup(deal)
    open_chat = deal.state == Deal.State.CHAT_OPEN
    data = {
        "id": deal.pk,
        "state": deal.state,
        "role": role,
        "turn": _turn(deal, role),
        "amount": deal.amount,
        "video_count": deal.video_count,
        "max_videos": rules.MAX_VIDEOS,
        **_timing(deal, now),
        "paid_at": deal.paid_at,
        "chat_opened_at": deal.chat_opened_at,
        "video_accepted_at": accepted.rated_at if accepted else None,
        "confirmed_at": deal.confirmed_at,
        "released_at": deal.released_at,
        "refunded_at": deal.refunded_at,
        "buyer_choice_after_3_bad": deal.buyer_choice_after_3_bad or None,
        "listing": {
            "id": deal.listing_id,
            "title": deal.listing.title,
            "photo": _photo(deal.listing),
            "area": deal.listing.area,
        },
        "me": {"first_name": viewer.first_name, "last_initial": viewer.last_name[:1].upper()},
        "other": person(deal.other(viewer), "seller" if role == "buyer" else "buyer"),
        "buyer_first_name": deal.buyer.first_name,
        "seller_first_name": deal.seller.first_name,
        "videos": [video_data(deal, v) for v in videos],
        # What the buyer asked for after the last Bad (the seller's re-record prompt).
        "requested": last_bad.instructions if last_bad and deal.state == Deal.State.AWAITING_VIDEO else None,
        "meetup": meetup_data(meetup, viewer) if meetup else None,
        "refund": _refund(deal, role),
        "can": {
            "send_text": (role == "buyer" and deal.state in Deal.ACTIVE) or (role == "seller" and open_chat),
            "record": role == "seller" and deal.state == Deal.State.AWAITING_VIDEO,
            "rate": role == "buyer" and deal.state == Deal.State.VIDEO_TO_RATE,
            "decide": role == "buyer" and deal.state == Deal.State.AWAITING_DECISION,
            "confirm": role == "buyer" and open_chat,
            "meetup": open_chat,
        },
        "contacts_masked": deal.state in (Deal.State.AWAITING_VIDEO, Deal.State.VIDEO_TO_RATE, Deal.State.AWAITING_DECISION),
    }
    if role == "buyer":
        data["source"] = {"bank": deal.inbound.sender_bank, "last4": deal.inbound.sender_account_last4}
    else:
        data["fee"] = deal.fee
        data["payout"] = deal.payout
        data["fee_rate_label"] = deal.fee_rate_label
        data["payout_account"] = _payout_account(deal)
    return data


def message_data(message: Message, deal, viewer, videos: dict, meetups: dict) -> dict:
    mine = message.sender_id == viewer.pk
    sender_role = None
    if message.sender_id:
        sender_role = "buyer" if message.sender_id == deal.buyer_id else "seller"
    data = {
        "id": message.pk,
        "kind": message.kind,
        "mine": mine,
        "sender_role": sender_role,
        "created_at": message.created_at,
        "read_at": message.read_at if mine else None,
    }
    if message.kind == Message.Kind.TEXT:
        data["body"] = message.shown_body
    elif message.kind == Message.Kind.SYSTEM:
        data["event"] = message.body
        data["data"] = message.data
    elif message.kind == Message.Kind.PHOTO:
        data["photo_url"] = f"/api/deals/{deal.pk}/messages/{message.pk}/photo/"
    elif message.kind == Message.Kind.LIVE_VIDEO:
        video = videos.get(message.data.get("n"))
        data["video"] = video_data(deal, video) if video else None
    elif message.kind in (Message.Kind.RATING, Message.Kind.INSTRUCTION):
        data["data"] = message.data
    elif message.kind == Message.Kind.MEETUP:
        meetup = meetups.get(message.data.get("meetup_id"))
        data["meetup"] = meetup_data(meetup, viewer) if meetup else None
    return data


def messages_data(deal, viewer) -> list:
    videos = {v.n: v for v in deal.videos.all()}
    meetups = {m.pk: m for m in deal.meetups.all()}
    return [message_data(m, deal, viewer, videos, meetups) for m in deal.messages.all()]
