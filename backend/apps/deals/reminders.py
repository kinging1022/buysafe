"""Reminders for whoever the deal is waiting on (rules.py has the schedule).

Each goes out once: a Reminder row per (deal, step, channel, n) is created
before sending, and the unique constraint stops repeats. SMS and calls wait
out quiet hours (22:00–07:00 Lagos); in-app notifications don't make a
sound, so they go at once. Steps are timed in awake time, like deadlines.
"""

from __future__ import annotations

from django.db import IntegrityError, transaction

from apps.notifications import sms
from apps.notifications.clock import short_title
from apps.notifications.services import notify

from . import rules
from .calls import place_call
from .deadlines import awake_time_between, in_quiet_hours
from .models import Deal, Meetup, Reminder


def ask_text(instructions: dict) -> str:
    """"Show the back · Closer" (or the note when no chip was picked)."""
    chips = instructions.get("chips") or []
    return " · ".join(chips) if chips else instructions.get("note", "")


def _step(deal):
    """(step name, schedule) for what the deal is waiting on, or (None, [])."""
    if deal.state == Deal.State.AWAITING_VIDEO:
        return f"video_{deal.video_count + 1}", rules.VIDEO_REMINDERS
    if deal.state == Deal.State.VIDEO_TO_RATE:
        return f"rate_{deal.video_count}", rules.RATE_REMINDERS
    return None, []


def _claim(deal, step, channel, n) -> bool:
    try:
        with transaction.atomic():
            Reminder.objects.create(deal=deal, step=step, channel=channel, n=n)
        return True
    except IntegrityError:
        return False


def _data(deal, **extra):
    return {
        "deal_id": deal.pk,
        "listing_id": deal.listing_id,
        "listing_title": deal.listing.title,
        "amount": deal.amount,
        "buyer_first_name": deal.buyer.first_name,
        "seller_first_name": deal.seller.first_name,
        **extra,
    }


def _deliver(deal, step, channel, n):
    title = short_title(deal.listing.title)
    buyer, seller = deal.buyer, deal.seller
    if step.startswith("video_"):
        video_n = deal.video_count + 1
        if n == 0 and video_n == 1:
            if channel == "push":
                notify(seller, "payment_held", _data(deal), ref=f"deal:{deal.pk}:{step}")
            else:
                sms.send(seller, "payment_held", buyer=buyer.first_name, amount=deal.amount, title=title)
        elif n == 0:
            previous = deal.videos.filter(n=video_n - 1).first()
            ask = ask_text(previous.instructions if previous else {})
            if channel == "push":
                notify(seller, "video_requested", _data(deal, n=video_n, ask=ask), ref=f"deal:{deal.pk}:{step}")
            else:
                sms.send(seller, "video_requested", buyer=buyer.first_name, n=video_n, title=title)
        elif channel == "call":
            place_call(
                seller,
                f"This is buysafe. {buyer.first_name} has paid for your {title}. "
                "Open the buysafe app and record the live video now, or the deal will be cancelled.",
            )
        elif channel == "push":
            notify(seller, "video_reminder", _data(deal), ref=f"deal:{deal.pk}:{step}:{n}")
        else:
            sms.send(seller, "video_reminder", title=title)
    elif step.startswith("rate_"):
        if channel == "push":
            notify(buyer, "video_ready", _data(deal), ref=f"deal:{deal.pk}:{step}")
        elif channel == "sms":
            sms.send(buyer, "video_ready", seller=seller.first_name, title=title)
        else:
            place_call(
                buyer,
                f"This is buysafe. {seller.first_name} sent a live video of the {title}. "
                "Open the buysafe app and rate it. If you don't, it counts as good.",
            )
    elif step == "confirm":
        notify(buyer, "confirm_reminder", _data(deal), ref=f"deal:{deal.pk}:confirm")


def send_due(deal: Deal, now) -> int:
    """Send whatever is due for the deal's current step. Returns how many."""
    sent = 0
    quiet = in_quiet_hours(now)
    step, schedule = _step(deal)
    if step and deal.step_started_at:
        elapsed = awake_time_between(deal.step_started_at, now)
        for n, (offset, channels) in enumerate(schedule):
            if elapsed < offset:
                continue
            for channel in channels:
                if channel != "push" and quiet:
                    continue
                if _claim(deal, step, channel, n):
                    _deliver(deal, step, channel, n)
                    sent += 1
    elif deal.state == Deal.State.CHAT_OPEN:
        meetup = deal.meetups.filter(status=Meetup.Status.CONFIRMED).first()
        if meetup and now >= meetup.when + rules.CONFIRM_REMINDER_AFTER and _claim(deal, "confirm", "push", 0):
            _deliver(deal, "confirm", "push", 0)
            sent += 1
    return sent
