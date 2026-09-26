import re

from django.core.exceptions import ValidationError

INVALID_PHONE_MESSAGE = "Enter a valid Nigerian mobile number."

_SEPARATORS = re.compile(r"[\s\-().]")


def normalize_ng_phone(raw) -> str:
    """Return a Nigerian mobile number as E.164 (+234XXXXXXXXXX).

    Accepts 0803…, 803…, +234803… and 234803…, with spaces, dashes, dots or
    brackets. The national part must be 10 digits starting with 7, 8 or 9.
    Raises ValidationError otherwise.
    """
    value = _SEPARATORS.sub("", str(raw or ""))
    if value.startswith("+234"):
        national = value[4:]
    elif value.startswith("234") and len(value) == 13:
        national = value[3:]
    elif value.startswith("0") and len(value) == 11:
        national = value[1:]
    else:
        national = value

    if not re.fullmatch(r"[789]\d{9}", national):
        raise ValidationError(INVALID_PHONE_MESSAGE, code="invalid_phone")
    return f"+234{national}"


def mask_phone(e164: str) -> str:
    """+2348031234567 -> '+234 803 ••• 4567'"""
    national = e164[4:]
    return f"+234 {national[:3]} ••• {national[-4:]}"
