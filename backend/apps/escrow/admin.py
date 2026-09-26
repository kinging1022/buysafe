from django.contrib import admin

from .models import Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ["listing", "buyer", "status", "amount", "payout", "meetup_at", "completed_at"]
    list_filter = ["status"]
    raw_id_fields = ["listing", "buyer"]
