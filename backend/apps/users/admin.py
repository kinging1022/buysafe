from django.contrib import admin

from .models import PhoneVerification, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ["phone", "first_name", "last_name", "phone_verified", "is_active", "date_joined"]
    list_filter = ["phone_verified", "is_active", "is_staff"]
    search_fields = ["phone", "first_name", "last_name"]
    exclude = ["password"]


@admin.register(PhoneVerification)
class PhoneVerificationAdmin(admin.ModelAdmin):
    list_display = ["phone", "created_at", "expires_at", "attempts", "used"]
    readonly_fields = ["user", "phone", "pin_id", "created_at", "expires_at", "attempts", "used"]
