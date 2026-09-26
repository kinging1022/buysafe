from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.storage import default_storage
from django.db import transaction
from rest_framework import serializers

from apps.users.states import NG_STATES

from . import fees
from . import status as listing_status
from .models import MAX_PHOTOS, MIN_PHOTOS, Category, Listing, ListingPhoto
from .photos import process_photo


class MyListingSerializer(serializers.ModelSerializer):
    """A listing on the seller's own profile. Expects a queryset from
    status.with_card_details(). Money is whole naira."""

    first_image_url = serializers.SerializerMethodField()
    display_status = serializers.CharField()
    interest_count = serializers.IntegerField()
    meetup_at = serializers.DateTimeField(allow_null=True)
    payout = serializers.IntegerField(allow_null=True)
    sold_at = serializers.DateTimeField(allow_null=True)

    class Meta:
        model = Listing
        fields = [
            "id",
            "title",
            "price",
            "area",
            "created_at",
            "first_image_url",
            "display_status",
            "rejection_reason",
            "interest_count",
            "meetup_at",
            "payout",
            "sold_at",
        ]
        read_only_fields = fields

    def get_first_image_url(self, listing):
        return default_storage.url(listing.first_image) if listing.first_image else None

    def to_representation(self, listing):
        data = super().to_representation(listing)
        shown = data["display_status"]
        # Each detail only applies to one status.
        if shown != listing_status.REJECTED:
            data["rejection_reason"] = ""
        if shown != listing_status.IN_ESCROW:
            data["meetup_at"] = None
        if shown != listing_status.SOLD:
            data["payout"] = None
            data["sold_at"] = None
        return data


# ---------------------------------------------------------------------------
# Public browse


class PublicListingSerializer(serializers.ModelSerializer):
    """A live listing as anyone sees it. Never the seller's phone or address."""

    cover_url = serializers.SerializerMethodField()
    seller = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = ["id", "title", "price", "condition", "area", "state", "created_at", "cover_url", "seller"]
        read_only_fields = fields

    def get_cover_url(self, listing):
        return default_storage.url(listing.cover) if listing.cover else None

    def get_seller(self, listing):
        seller = listing.seller
        return {
            "first_name": seller.first_name,
            "last_initial": seller.last_name[:1].upper(),
            "avatar_color": seller.avatar_color,
        }


class CategorySerializer(serializers.ModelSerializer):
    label = serializers.CharField(source="name")

    class Meta:
        model = Category
        fields = ["slug", "label"]


# ---------------------------------------------------------------------------
# Post an item / edit


def _clean_text(value):
    return " ".join(value.split())


class ListingWriteSerializer(serializers.ModelSerializer):
    """Create (all fields + 3–5 photos) and edit (any fields; photos via
    photo_order). Every photo is processed during validation, so nothing is
    saved unless the whole submission is valid."""

    category = serializers.SlugRelatedField(slug_field="slug", queryset=Category.objects.filter(is_active=True))
    state = serializers.ChoiceField(choices=NG_STATES)
    price = serializers.IntegerField(
        min_value=fees.MIN_PRICE,
        max_value=fees.MAX_PRICE,
        error_messages={
            "min_value": f"Minimum price is {fees.naira(fees.MIN_PRICE)}.",
            "max_value": f"Maximum price is {fees.naira(fees.MAX_PRICE)}.",
            "invalid": "Enter the price in whole naira.",
        },
    )
    # Create: the photos, cover first.
    photos = serializers.ListField(child=serializers.FileField(), required=False, write_only=True)
    # Edit: the final order as tokens, "p<id>" for a kept photo or "n<index>"
    # for the index-th file in new_photos. Photos left out are removed.
    photo_order = serializers.ListField(child=serializers.CharField(), required=False, write_only=True)
    new_photos = serializers.ListField(child=serializers.FileField(), required=False, write_only=True)

    class Meta:
        model = Listing
        fields = ["title", "category", "condition", "description", "price", "state", "area", "photos", "photo_order", "new_photos"]

    def validate_title(self, value):
        value = _clean_text(value)
        if not 5 <= len(value) <= 120:
            raise serializers.ValidationError("Title must be 5–120 characters.")
        return value

    def validate_description(self, value):
        value = value.strip()
        if not 20 <= len(value) <= 1000:
            raise serializers.ValidationError("Description must be 20–1,000 characters.")
        return value

    def validate_area(self, value):
        value = _clean_text(value)
        if not 2 <= len(value) <= 60:
            raise serializers.ValidationError("Enter the area or town (2–60 characters).")
        return value

    def _process(self, files):
        processed, errors = [], []
        for upload in files:
            try:
                processed.append(process_photo(upload))
            except DjangoValidationError as exc:
                errors.extend(exc.messages)
        if errors:
            raise serializers.ValidationError({"photos": sorted(set(errors))})
        return processed

    def _check_count(self, count):
        if count < MIN_PHOTOS:
            raise serializers.ValidationError({"photos": [f"Add at least {MIN_PHOTOS} photos."]})
        if count > MAX_PHOTOS:
            raise serializers.ValidationError({"photos": [f"You can add up to {MAX_PHOTOS} photos."]})

    def validate(self, attrs):
        if self.instance is None:
            files = attrs.pop("photos", [])
            self._check_count(len(files))
            attrs["photos"] = self._process(files)
            return attrs

        new_files = attrs.pop("new_photos", [])
        order = attrs.pop("photo_order", None)
        attrs.pop("photos", None)
        if order is None:
            if new_files:
                raise serializers.ValidationError({"photo_order": ["Send photo_order with new photos."]})
            return attrs
        existing = {p.pk: p for p in self.instance.photos.all()}
        plan = []
        for token in order:
            kind, ref = token[:1], token[1:]
            if kind == "p" and ref.isdigit() and int(ref) in existing:
                plan.append(("keep", existing[int(ref)]))
            elif kind == "n" and ref.isdigit() and int(ref) < len(new_files):
                plan.append(("new", int(ref)))
            else:
                raise serializers.ValidationError({"photos": ["Something went wrong with the photos. Try again."]})
        self._check_count(len(plan))
        processed = self._process(new_files)
        attrs["photo_plan"] = [(kind, ref if kind == "keep" else processed[ref]) for kind, ref in plan]
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        photos = validated_data.pop("photos")
        listing = Listing.objects.create(**validated_data)
        for position, content in enumerate(photos):
            ListingPhoto.objects.create(listing=listing, image=content, position=position)
        return listing

    @transaction.atomic
    def update(self, listing, validated_data):
        plan = validated_data.pop("photo_plan", None)
        for field, value in validated_data.items():
            setattr(listing, field, value)
        # Any edit goes back to review; a resubmitted rejection loses its old reason.
        listing.approval_status = Listing.Approval.PENDING
        listing.rejection_reason = ""
        listing.save()
        if plan is not None:
            kept = {photo.pk for kind, photo in plan if kind == "keep"}
            for photo in listing.photos.exclude(pk__in=kept):
                # Remove the file only once the new state is committed.
                transaction.on_commit(lambda name=photo.image.name: default_storage.delete(name))
                photo.delete()
            for position, (kind, item) in enumerate(plan):
                if kind == "keep":
                    item.position = position
                    item.save(update_fields=["position"])
                else:
                    ListingPhoto.objects.create(listing=listing, image=item, position=position)
        return listing


class OwnerListingSerializer(serializers.ModelSerializer):
    """The owner's own listing, to prefill the edit form."""

    category = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    photos = serializers.SerializerMethodField()
    display_status = serializers.SerializerMethodField()
    fee = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = [
            "id",
            "title",
            "category",
            "condition",
            "description",
            "price",
            "state",
            "area",
            "approval_status",
            "rejection_reason",
            "display_status",
            "photos",
            "fee",
            "created_at",
        ]
        read_only_fields = fields

    def get_photos(self, listing):
        return [{"id": p.pk, "url": p.image.url, "position": p.position} for p in listing.photos.all()]

    def get_display_status(self, listing):
        return listing_status.listing_display_status(listing)

    def get_fee(self, listing):
        return fees.calculate_fee(listing.price).as_dict()
