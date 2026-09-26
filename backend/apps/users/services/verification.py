"""Issuing phone-verification codes, with a per-phone cooldown and hourly cap.

Send limits are tracked in the cache by phone number (not by user), so the
resend endpoint behaves identically for numbers that have no account.
In production the cache must be shared between processes (e.g. Redis).
"""

import time
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from ..models import PhoneVerification
from .otp import get_otp_service

HOUR = 3600


def _last_key(phone):
    return f"otp:last-send:{phone}"


def _count_key(phone):
    return f"otp:hour-count:{phone}"


def cooldown_remaining(phone) -> int:
    """Seconds until another code may be sent to this phone (0 if allowed now)."""
    last = cache.get(_last_key(phone))
    if last is None:
        return 0
    return max(0, int(last + settings.OTP_RESEND_COOLDOWN - time.time() + 0.999))


def hourly_retry_after(phone) -> int:
    """Seconds until the hourly cap resets, or 0 if under the cap."""
    window = cache.get(_count_key(phone))
    if not window or window["count"] < settings.OTP_MAX_SENDS_PER_HOUR:
        return 0
    return max(1, int(window["start"] + HOUR - time.time()))


def record_send(phone):
    now = time.time()
    cache.set(_last_key(phone), now, settings.OTP_RESEND_COOLDOWN)
    window = cache.get(_count_key(phone))
    if not window or now - window["start"] >= HOUR:
        window = {"start": now, "count": 0}
    window["count"] += 1
    cache.set(_count_key(phone), window, int(window["start"] + HOUR - now) + 1)


def send_limit_retry_after(phone) -> int:
    """0 if a code may be sent now, else seconds to wait (cooldown or hourly cap)."""
    return max(cooldown_remaining(phone), hourly_retry_after(phone))


def issue_code(user, purpose=PhoneVerification.Purpose.SIGNUP) -> PhoneVerification:
    """Send a fresh code to the user's phone for one flow and record it. Earlier
    codes for that flow stop working. Raises OtpSendError if the provider fails."""
    pin_id = get_otp_service().send_otp(user.phone)
    PhoneVerification.objects.filter(user=user, purpose=purpose, used=False).update(used=True)
    verification = PhoneVerification.objects.create(
        user=user,
        phone=user.phone,
        purpose=purpose,
        pin_id=pin_id,
        expires_at=timezone.now() + timedelta(minutes=settings.OTP_TTL_MINUTES),
    )
    record_send(user.phone)
    return verification


def send_code_if_allowed(user, purpose=PhoneVerification.Purpose.SIGNUP) -> int:
    """Send a code unless a limit applies. Returns resend_available_in (seconds).
    Used by register/login and password reset, where an active cooldown just
    means the previous code is still valid."""
    wait = send_limit_retry_after(user.phone)
    if wait:
        return wait
    issue_code(user, purpose)
    return settings.OTP_RESEND_COOLDOWN


def latest_active_verification(phone, purpose=PhoneVerification.Purpose.SIGNUP):
    return (
        PhoneVerification.objects.filter(phone=phone, purpose=purpose, used=False).select_related("user").first()
    )
