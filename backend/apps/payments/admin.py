from django.contrib import admin

from .models import FeeTransfer, InboundTransfer, ListingHold, PaymentIntent, Payout, PayoutAccount, Refund


@admin.register(PaymentIntent)
class PaymentIntentAdmin(admin.ModelAdmin):
    list_display = ["id", "listing", "buyer", "amount_expected", "status", "virtual_account_number", "expires_at"]
    list_filter = ["status"]
    raw_id_fields = ["listing", "buyer", "offer"]
    search_fields = ["virtual_account_number"]


@admin.register(ListingHold)
class ListingHoldAdmin(admin.ModelAdmin):
    list_display = ["listing", "buyer", "expires_at", "released_at", "end_reason"]
    raw_id_fields = ["listing", "buyer", "intent"]


@admin.register(InboundTransfer)
class InboundTransferAdmin(admin.ModelAdmin):
    list_display = ["provider_ref", "amount", "sender_bank", "sender_account_last4", "outcome", "received_at"]
    list_filter = ["outcome"]
    search_fields = ["provider_ref", "account_number"]
    exclude = ["sender_account"]
    raw_id_fields = ["matched_intent"]


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ["id", "inbound", "amount", "fee", "reason", "status", "attempts", "created_at", "settled_at"]
    list_filter = ["status", "reason"]
    raw_id_fields = ["inbound"]


@admin.register(PayoutAccount)
class PayoutAccountAdmin(admin.ModelAdmin):
    list_display = ["user", "bank_name", "account_last4", "account_name", "verified_at"]
    exclude = ["account_number"]
    raw_id_fields = ["user"]


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ["deal", "amount", "bank_name", "account_last4", "status", "attempts", "sent_at", "settled_at"]
    list_filter = ["status"]
    exclude = ["account_number"]
    raw_id_fields = ["deal"]


@admin.register(FeeTransfer)
class FeeTransferAdmin(admin.ModelAdmin):
    list_display = ["deal", "amount", "status", "attempts", "provider_ref", "sent_at"]
    list_filter = ["status"]
    raw_id_fields = ["deal"]
