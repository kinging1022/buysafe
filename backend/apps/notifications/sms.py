"""Every plain SMS buysafe sends, in one place (in-app notifications are
kinds.py). Sent through the same provider
as OTPs (apps.users.services.otp). Messages never include a phone number.

SMS is best effort: a provider failure is logged and never undoes the action
that triggered it. Call send() inside the request's transaction; the message
goes out only after it commits.
"""

import logging

from django.db import transaction

from apps.listings.fees import naira

from .clock import clock
from apps.users.phone import mask_phone
from apps.users.services.otp import OtpSendError, get_otp_service

logger = logging.getLogger(__name__)

TEMPLATES = {
    # To the seller.
    "offer_new": "New offer {amount} on {title}",
    # To the buyer.
    "offer_expired": "Your offer {amount} on {title} expired without a reply.",
    # --- Payments and deals. TODO: SMS wording to confirm (not in the designs). ---
    # To the buyer.
    "offer_accepted": "{seller} accepted {amount} for {title}. First to pay gets it. Price held until {until}.",
    "video_ready": "{seller} sent a live video of the {title}. Rate it in the buysafe app within 2 hours.",
    # To the seller.
    "payment_held": "{buyer} paid {amount} for your {title}. Record a live video in the buysafe app within 4 hours.",
    "video_reminder": "1 hour left to send the live video of your {title} on buysafe, or the buyer is refunded.",
    "video_requested": "{buyer} asked for video {n} of 3 of your {title}. Record it in the buysafe app within 4 hours.",
    "money_released": "{amount} for your {title} is on its way to your {bank} account ····{last4}.",
}


def render(key, **context):
    if "amount" in context:
        context["amount"] = naira(context["amount"])
    if "until" in context:
        context["until"] = clock(context["until"])
    return TEMPLATES[key].format(**context)


def _deliver(phone, text):
    try:
        get_otp_service().send_sms(phone, text)
    except OtpSendError:
        logger.warning("SMS to %s not sent", mask_phone(phone))


def send(user, key, **context):
    text = render(key, **context)
    phone = user.phone
    transaction.on_commit(lambda: _deliver(phone, text))
