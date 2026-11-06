from django.contrib import admin, messages

from . import services
from .models import Deal, DealReport, LiveVideo, Meetup, Message, Reminder


class DealReportInline(admin.TabularInline):
    model = DealReport
    extra = 0
    readonly_fields = ["reporter", "text", "created_at"]


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = ["id", "listing", "buyer", "seller", "amount", "state", "video_count", "current_deadline"]
    list_filter = ["state"]
    raw_id_fields = ["intent", "inbound", "transaction", "listing", "buyer", "seller", "refund"]
    readonly_fields = ["amount", "fee", "payout", "state", "released_ref"]
    inlines = [DealReportInline]
    actions = ["refund_no_show"]

    @admin.action(description="Refund the buyer in full (seller didn’t show up)")
    def refund_no_show(self, request, queryset):
        for deal in queryset:
            try:
                services.refund_no_show(deal, request.user)
            except services.DealError as err:
                self.message_user(request, f"Deal {deal.pk}: {err.detail}", messages.WARNING)
            else:
                self.message_user(request, f"Deal {deal.pk} refunded.")


@admin.register(DealReport)
class DealReportAdmin(admin.ModelAdmin):
    list_display = ["deal", "reporter", "created_at", "resolved_at"]
    raw_id_fields = ["deal", "reporter"]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ["deal", "sender", "kind", "created_at", "read_at"]
    list_filter = ["kind"]
    raw_id_fields = ["deal", "sender"]


admin.site.register(LiveVideo)
admin.site.register(Meetup)
admin.site.register(Reminder)
