"""Short-lived tokens issued after a password-reset code is verified.

The token is signed (TimestampSigner) and expires after 10 minutes. It also
carries an HMAC of the user's current password hash, so it stops working as
soon as the password changes: it can be used once, and a password change by
any other route cancels it too.
"""

from django.core import signing
from django.utils.crypto import constant_time_compare, salted_hmac

from ..models import User

SALT = "buysafe.password-reset"
MAX_AGE = 10 * 60  # seconds


def _fingerprint(user):
    return salted_hmac(SALT, user.password).hexdigest()[:32]


def make_reset_token(user) -> str:
    return signing.TimestampSigner(salt=SALT).sign_object({"u": user.pk, "p": _fingerprint(user)})


def user_for_reset_token(token):
    """The user the token was issued for, or None if it's invalid, expired or used."""
    try:
        data = signing.TimestampSigner(salt=SALT).unsign_object(token, max_age=MAX_AGE)
    except (signing.BadSignature, TypeError, ValueError):  # SignatureExpired is a BadSignature
        return None
    user = User.objects.filter(pk=data.get("u"), is_active=True, phone_verified=True).first()
    if user is None or not constant_time_compare(data.get("p", ""), _fingerprint(user)):
        return None
    return user
