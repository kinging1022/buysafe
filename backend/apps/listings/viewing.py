"""Counting who looks at a listing: once per person per day, never the seller."""

import hashlib

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from .models import Listing, ListingView


def _ip_hash(ip, day):
    # Salted with the secret key and the day, so hashes can't be matched
    # across days or reversed with a table of IPs.
    return hashlib.sha256(f"{settings.SECRET_KEY}|{day}|{ip}".encode()).hexdigest()


def record_view(listing, request):
    user = request.user if request.user.is_authenticated else None
    if user and user.pk == listing.seller_id:
        return
    day = timezone.localdate()
    key = {"user": user} if user else {"user": None, "ip_hash": _ip_hash(request.META.get("REMOTE_ADDR", ""), day)}
    try:
        with transaction.atomic():
            ListingView.objects.create(listing=listing, date=day, **key)
            Listing.objects.filter(pk=listing.pk).update(view_count=F("view_count") + 1)
    except IntegrityError:
        pass  # already counted today
