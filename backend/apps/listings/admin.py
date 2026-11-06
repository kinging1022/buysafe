from django import forms
from django.contrib import admin, messages
from django.utils.html import format_html, format_html_join

from .models import Category, Listing, ListingInterest, ListingPhoto


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "sort_order", "is_active"]
    list_editable = ["sort_order", "is_active"]
    prepopulated_fields = {"slug": ["name"]}


class ListingPhotoInline(admin.TabularInline):
    model = ListingPhoto
    extra = 0
    fields = ["preview", "image", "position"]
    readonly_fields = ["preview"]

    @admin.display(description="Preview")
    def preview(self, photo):
        if not photo.image:
            return "-"
        return format_html('<a href="{0}" target="_blank"><img src="{0}" style="height:120px;border-radius:6px"></a>', photo.image.url)


class ListingAdminForm(forms.ModelForm):
    """Review rules: a rejection needs a reason (the seller sees it); any other
    status clears it."""

    class Meta:
        model = Listing
        fields = "__all__"

    def clean(self):
        data = super().clean()
        if data.get("approval_status") == Listing.Approval.REJECTED:
            if not (data.get("rejection_reason") or "").strip():
                self.add_error("rejection_reason", "Tell the seller why it was rejected. They see this reason.")
        else:
            data["rejection_reason"] = ""
        return data


class ApprovalFilter(admin.SimpleListFilter):
    """Opens on the review queue (pending) instead of every listing."""

    title = "approval status"
    parameter_name = "approval"

    def lookups(self, request, model_admin):
        return [*Listing.Approval.choices, ("all", "All")]

    def queryset(self, request, queryset):
        value = self.value() or Listing.Approval.PENDING
        return queryset if value == "all" else queryset.filter(approval_status=value)

    def choices(self, changelist):
        current = self.value() or Listing.Approval.PENDING
        for value, label in self.lookup_choices:
            yield {
                "selected": current == value,
                "query_string": changelist.get_query_string({self.parameter_name: value}),
                "display": label,
            }


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    form = ListingAdminForm
    list_display = ["cover", "title", "seller", "price", "category", "state", "area", "approval_status", "is_deleted", "created_at"]
    list_display_links = ["cover", "title"]
    list_filter = [ApprovalFilter, "category", "condition", "state", "is_deleted"]
    search_fields = ["title", "seller__phone", "area"]
    raw_id_fields = ["seller"]
    inlines = [ListingPhotoInline]
    actions = ["approve"]
    fieldsets = [
        ("Review", {"fields": ["approval_status", "rejection_reason", "photos_preview"]}),
        ("Listing", {"fields": ["seller", "title", "category", "condition", "description", "price", "state", "area", "is_deleted"]}),
    ]
    readonly_fields = ["photos_preview"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("seller", "category").prefetch_related("photos")

    @admin.display(description="")
    def cover(self, listing):
        photo = next(iter(listing.photos.all()), None)
        if not photo or not photo.image:
            return "-"
        return format_html('<img src="{}" style="height:48px;width:48px;object-fit:cover;border-radius:4px">', photo.image.url)

    @admin.display(description="Photos")
    def photos_preview(self, listing):
        photos = [p for p in listing.photos.all() if p.image] if listing.pk else []
        if not photos:
            return "-"
        return format_html(
            '<div style="display:flex;gap:8px;flex-wrap:wrap">{}</div>',
            format_html_join(
                "",
                '<a href="{0}" target="_blank"><img src="{0}" style="height:160px;border-radius:6px"></a>',
                ((p.image.url,) for p in photos),
            ),
        )

    @admin.action(description="Approve selected listings")
    def approve(self, request, queryset):
        count = queryset.exclude(approval_status=Listing.Approval.APPROVED).update(
            approval_status=Listing.Approval.APPROVED, rejection_reason=""
        )
        self.message_user(
            request,
            f"Approved {count} listing{'' if count == 1 else 's'}. To reject one, open it and give a reason.",
            messages.SUCCESS,
        )


@admin.register(ListingInterest)
class ListingInterestAdmin(admin.ModelAdmin):
    list_display = ["listing", "buyer", "created_at"]
    raw_id_fields = ["listing", "buyer"]
