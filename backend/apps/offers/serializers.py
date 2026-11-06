from rest_framework import serializers

from apps.listings import fees

from .models import Offer
from .rules import NOTE_MAX_LENGTH


def public_name(user):
    """What other users see: first name, last initial, avatar colour. Never a phone."""
    return {"first_name": user.first_name, "last_initial": user.last_name[:1].upper(), "avatar_color": user.avatar_color}


class OfferCreateSerializer(serializers.Serializer):
    amount = serializers.IntegerField(
        min_value=1, error_messages={"invalid": "Enter the amount in whole naira."}
    )
    note = serializers.CharField(max_length=NOTE_MAX_LENGTH, required=False, allow_blank=True, default="")

    def to_internal_value(self, data):
        # Whole naira only: 165000 or "165000", never 165000.5 or "165,000".
        amount = data.get("amount") if hasattr(data, "get") else None
        if isinstance(amount, float) or (isinstance(amount, str) and not amount.strip().isdigit()):
            raise serializers.ValidationError({"amount": ["Enter the amount in whole naira."]})
        values = super().to_internal_value(data)
        values["note"] = values["note"].strip()
        return values


class MyOfferSerializer(serializers.ModelSerializer):
    """The buyer's own open offer, on the listing page. A decline still in its
    Undo window shows as pending: the buyer isn't told until it's final."""

    status = serializers.SerializerMethodField()

    class Meta:
        model = Offer
        fields = ["id", "amount", "status", "created_at", "expires_at"]
        read_only_fields = fields

    def get_status(self, offer):
        status = offer.effective_status()
        return Offer.Status.PENDING if status == Offer.Status.DECLINED else status


class OwnerOfferSerializer(serializers.ModelSerializer):
    """An offer as the listing's owner sees it, with what they'd receive."""

    status = serializers.SerializerMethodField()
    undo_until = serializers.SerializerMethodField()
    buyer = serializers.SerializerMethodField()
    quote = serializers.SerializerMethodField()

    class Meta:
        model = Offer
        fields = [
            "id", "amount", "note", "status", "created_at", "expires_at", "decided_at", "price_held_until", "undo_until",
            "buyer", "quote",
        ]
        read_only_fields = fields

    def get_undo_until(self, offer):
        until = offer.undo_until()
        return serializers.DateTimeField().to_representation(until) if until else None

    def get_status(self, offer):
        return offer.effective_status()

    def get_buyer(self, offer):
        return {**public_name(offer.buyer), "verified": offer.buyer.phone_verified}

    def get_quote(self, offer):
        quote = fees.calculate_fee(offer.amount)
        return {"payout": quote.payout, "rate_label": quote.rate_label}
