"""Shared test fixtures for the listings app."""

from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image

from apps.escrow.models import Transaction
from apps.users.models import User

from .models import Category, Listing


def make_user(phone, **extra):
    extra.setdefault("first_name", "Tolu")
    extra.setdefault("last_name", "Adeyemi")
    return User.objects.create_user(phone, "Safe2buy1", phone_verified=True, **extra)


def category(slug="home-appliances"):
    return Category.objects.get(slug=slug)


def make_listing(seller, approval=Listing.Approval.APPROVED, **extra):
    extra.setdefault("title", "Samsung fridge")
    extra.setdefault("price", 185_000)
    extra.setdefault("condition", Listing.Condition.GOOD)
    extra.setdefault("description", "Works well. Small dent on the left door.")
    extra["category"] = category(extra.pop("category_slug", "home-appliances"))
    return Listing.objects.create(seller=seller, approval_status=approval, **extra)


def make_payout_account(user, bank_code="000014", account_number="0123454521"):
    """A verified payout account (listings can't take payment without one)."""
    from apps.payments.models import PayoutAccount

    return PayoutAccount.objects.create(
        user=user,
        bank_code=bank_code,
        bank_name="Access Bank",
        account_number=account_number,
        account_last4=account_number[-4:],
        account_name=f"{user.last_name.upper()} {user.first_name.upper()}",
        verified_at=timezone.now(),
    )


def make_tx(listing, buyer, status, **extra):
    return Transaction.objects.create(listing=listing, buyer=buyer, status=status, amount=listing.price, **extra)


def image_file(name="photo.jpg", size=(1200, 900), fmt="JPEG", exif=None, color="#c9c2b5"):
    buf = BytesIO()
    kwargs = {"exif": exif} if exif is not None else {}
    Image.new("RGB", size, color).save(buf, fmt, **kwargs)
    content_type = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}[fmt]
    return SimpleUploadedFile(name, buf.getvalue(), content_type=content_type)
