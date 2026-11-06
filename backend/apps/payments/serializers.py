"""What the pay screens and the payout page read. Money is whole naira,
except transfer and refund amounts (strings with kobo, e.g. "170000.00")."""

from .banks import short_bank_name
from .models import InboundTransfer, PaymentIntent, PayoutAccount


def _photo(listing):
    photo = listing.photos.first()
    return photo.image.url if photo else None


def intent_data(intent: PaymentIntent) -> dict:
    listing = intent.listing
    seller = listing.seller
    transfers = list(intent.inbound_transfers.all())
    accepted = next((t for t in transfers if t.outcome == InboundTransfer.Outcome.ACCEPTED), None)
    returned = [t for t in transfers if t.outcome != InboundTransfer.Outcome.ACCEPTED]
    refunded = max(returned, key=lambda t: t.received_at) if returned else None
    refund = refunded.refunds.order_by("-created_at").first() if refunded else None
    return {
        "id": intent.pk,
        "status": intent.status,
        "amount": intent.amount_expected,
        "listing": {
            "id": listing.pk,
            "title": listing.title,
            "price": listing.price,
            "area": listing.area,
            "state": listing.state,
            "photo": _photo(listing),
            "seller": {"first_name": seller.first_name, "last_initial": seller.last_name[:1].upper()},
        },
        "offer": {"id": intent.offer_id, "amount": intent.offer.amount} if intent.offer_id else None,
        "account": {
            "number": intent.virtual_account_number,
            "bank": intent.virtual_account_bank,
            "name": intent.virtual_account_name,
        },
        "created_at": intent.created_at,
        "expires_at": intent.expires_at,
        "received": (
            {"bank": accepted.sender_bank, "last4": accepted.sender_account_last4, "at": accepted.received_at}
            if accepted
            else None
        ),
        "refund": (
            {
                "reason": refund.reason,
                "received_amount": str(refunded.amount),
                "fee": str(refund.fee),
                "amount": str(refund.amount),
                "bank": refunded.sender_bank,
                "last4": refunded.sender_account_last4,
            }
            if refund
            else None
        ),
        # The deal takes the intent's number (Deal 317 = intent 317).
        "deal_id": intent.pk if accepted else None,
    }


def payout_account_data(account: PayoutAccount) -> dict:
    return {
        "bank_code": account.bank_code,
        "bank_name": account.bank_name,
        "bank_short": short_bank_name(account.bank_name),
        "last4": account.account_last4,
        "account_name": account.account_name,
        "verified_at": account.verified_at,
    }
