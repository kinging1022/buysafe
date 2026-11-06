from django.contrib import admin

from .models import Offer


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = ["listing", "buyer", "amount", "status", "created_at", "expires_at"]
    list_filter = ["status"]
    raw_id_fields = ["listing", "buyer"]
    readonly_fields = ["created_at"]
