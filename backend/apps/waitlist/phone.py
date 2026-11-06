import re

NG_MOBILE_RE = re.compile(r'^[789][01]\d{8}$')


def normalize_waitlist_phone(value):
    """Return a Nigerian mobile number as E.164 (+234XXXXXXXXXX), or None.

    Mirrors the pre-launch form (frontend/src/components/prelaunch/waitlist.js):
    strip non-digits, then a leading 234, then a leading 0, and require
    [789][01] plus 8 digits. Stricter than apps.users.phone, which accepts any
    second digit.
    """
    digits = re.sub(r'\D', '', str(value or ''))
    if digits.startswith('234'):
        digits = digits[3:]
    if digits.startswith('0'):
        digits = digits[1:]
    if not NG_MOBILE_RE.match(digits):
        return None
    return '+234' + digits
