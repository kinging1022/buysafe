"""Every kind of in-app notification: its category (the row's colour), its
type label, what it says and where it links. Adding a kind is one entry
here (no migration). `data` is what the sender stored; text never includes
a phone number or a reason for a decline."""

from dataclasses import dataclass
from typing import Callable

from apps.listings.fees import naira

from .clock import clock, short_title


class Category:
    """How the notifications panel colours a row's type label: amber, red,
    green or grey. (A kind picks the colour family; "money" is the green one.)"""

    OFFER = "offer"  # amber: offers
    ACTION = "action"  # red: action needed, deadlines
    MONEY = "money"  # green: money held, paid out
    INFO = "info"  # grey: everything else (e.g. meetup)


@dataclass(frozen=True)
class Kind:
    category: str
    label: str  # the mono type label, e.g. "NEW OFFER"
    text: Callable[[dict], str]
    link: Callable[[dict], str]


KINDS = {
    # To the seller when a buyer makes an offer.
    "offer_new": Kind(
        category=Category.OFFER,
        label="NEW OFFER",
        text=lambda d: f"{d['buyer_name']} offered {naira(d['amount'])} for your {short_title(d['listing_title'])}.",
        link=lambda d: f"/listings/{d['listing_id']}",
    ),
    # To the buyer, 60s after the seller declines (after the Undo window).
    "offer_declined": Kind(
        category=Category.OFFER,
        label="NOT ACCEPTED",
        text=lambda d: (
            f"{d['seller_first_name']} didn’t accept your {naira(d['amount'])} offer on {d['listing_title']}. "
            "You can send a higher offer or Buy now."
        ),
        link=lambda d: f"/listings/{d['listing_id']}",
    ),
    # To the seller when a buyer asks a public question.
    "question_new": Kind(
        category=Category.OFFER,
        label="NEW QUESTION",
        text=lambda d: f"{d['asker_name']} asked about your {d['listing_title']}.",
        link=lambda d: f"/listings/{d['listing_id']}#questions",
    ),
    # --- Payments and deals (design/nav-and-notifications-update) ---
    # To the buyer when the seller accepts their offer.
    "offer_accepted": Kind(
        category=Category.OFFER,
        label="OFFER ACCEPTED · PAY NOW",
        text=lambda d: (
            f"{d['seller_first_name']} accepted {naira(d['amount'])}. First to pay gets it. "
            f"Price held until {clock(d['held_until'])}."
        ),
        link=lambda d: f"/listings/{d['listing_id']}",
    ),
    # To other buyers with an offer on the item when someone pays for it.
    "offer_closed": Kind(
        category=Category.INFO,
        label="NO LONGER AVAILABLE",
        text=lambda d: f"Someone else paid for the {short_title(d['listing_title'])}. Your offer has closed.",
        link=lambda d: f"/listings/{d['listing_id']}",
    ),
    # To the seller when the buyer's transfer is matched.
    "payment_held": Kind(
        category=Category.ACTION,
        label="PAYMENT HELD · RECORD VIDEO",
        text=lambda d: (
            f"{d['buyer_first_name']} paid {naira(d['amount'])} for your {short_title(d['listing_title'])}. "
            "Record a live video within 4 hours."
        ),
        link=lambda d: f"/deals/{d['deal_id']}",
    ),
    # To the seller: "1 hour left" on the video (reminder). TODO: copy to confirm.
    "video_reminder": Kind(
        category=Category.ACTION,
        label="ACTION NEEDED",
        text=lambda d: f"1 hour left to send the live video of your {short_title(d['listing_title'])}.",
        link=lambda d: f"/deals/{d['deal_id']}",
    ),
    # To the buyer when a live video arrives (and its 30-minute reminder).
    "video_ready": Kind(
        category=Category.ACTION,
        label="ACTION NEEDED",
        text=lambda d: (
            f"{d['seller_first_name']} sent a live video of the {short_title(d['listing_title'])}. "
            "Rate it within 2 hours."
        ),
        link=lambda d: f"/deals/{d['deal_id']}",
    ),
    # To the seller when the buyer rates a video Bad.
    "video_requested": Kind(
        category=Category.ACTION,
        label="ANOTHER VIDEO REQUESTED",
        text=lambda d: f"{d['buyer_first_name']} asked for video {d['n']} of 3: “{d['ask']}.”",
        link=lambda d: f"/deals/{d['deal_id']}",
    ),
    # To the buyer after the meetup, until they confirm. TODO: copy to confirm.
    "confirm_reminder": Kind(
        category=Category.ACTION,
        label="ACTION NEEDED",
        text=lambda d: (
            f"Got the {short_title(d['listing_title'])}? Confirm it in the deal to release the money, "
            "or report a problem."
        ),
        link=lambda d: f"/deals/{d['deal_id']}",
    ),
    # To the seller when the buyer confirms.
    "money_released": Kind(
        category=Category.MONEY,
        label="MONEY RELEASED",
        text=lambda d: f"{naira(d['amount'])} sent to your {d['bank_name']} account ····{d['last4']}.",
        link=lambda d: f"/deals/{d['deal_id']}",
    ),
    # To the buyer when a deal is refunded.
    "deal_refunded": Kind(
        category=Category.MONEY,
        label="REFUNDED",
        text=lambda d: f"{naira(d['amount'])} is back in your {d['bank_name']} account. {d.get('why', '')}".strip(),
        link=lambda d: f"/deals/{d['deal_id']}",
    ),
    # To the asker when the seller answers. Green, like the answer's rule.
    "question_answered": Kind(
        category=Category.MONEY,
        label="ANSWERED",
        text=lambda d: f"{d['seller_first_name']} answered your question about the {d['listing_title']}.",
        link=lambda d: f"/listings/{d['listing_id']}#questions",
    ),
}


def render(notification) -> dict:
    kind = KINDS[notification.kind]
    return {
        "category": kind.category,
        "label": kind.label,
        "title_text": kind.text(notification.data),
        "target_url": kind.link(notification.data),
    }
