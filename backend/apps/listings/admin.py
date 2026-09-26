from django.contrib import admin

from .models import Category, Listing, ListingInterest, ListingPhoto


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "sort_order", "is_active"]
    list_editable = ["sort_order", "is_active"]
    prepopulated_fields = {"slug": ["name"]}


class ListingPhotoInline(admin.TabularInline):
    model = ListingPhoto
    extra = 0


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ["title", "seller", "price", "category", "state", "area", "approval_status", "is_deleted", "created_at"]
    list_filter = ["approval_status", "category", "condition", "state", "is_deleted"]
    search_fields = ["title", "seller__phone", "area"]
    raw_id_fields = ["seller"]
    inlines = [ListingPhotoInline]


@admin.register(ListingInterest)
class ListingInterestAdmin(admin.ModelAdmin):
    list_display = ["listing", "buyer", "created_at"]
    raw_id_fields = ["listing", "buyer"]
