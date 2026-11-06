from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["user", "kind", "visible_at", "read_at"]
    list_filter = ["kind"]
    raw_id_fields = ["user"]
    search_fields = ["ref"]
