"""Encrypted model fields (Fernet, key in settings.FIELD_ENCRYPTION_KEY).

Used for full bank account numbers. Each value encrypts differently every
time, so these fields can't be filtered on: store a last-4 alongside for
display and lookups.
"""

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models


def _fernet():
    key = settings.FIELD_ENCRYPTION_KEY
    if not key:
        raise ImproperlyConfigured("FIELD_ENCRYPTION_KEY is not set.")
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        raise ImproperlyConfigured("Can't decrypt a stored value: wrong FIELD_ENCRYPTION_KEY?") from None


class EncryptedCharField(models.TextField):
    """A string stored encrypted. Reads back as the plain string."""

    def from_db_value(self, value, expression, connection):
        return decrypt(value) if value else value

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        return encrypt(value) if value else value
