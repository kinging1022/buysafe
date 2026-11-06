"""Finding contact details in text buyers and sellers write before payment
(listing questions and answers; later the deal chat's rules). The one source
of truth: the frontend's useContactGuard() is a first, simpler pass for the
live warning, and this check is the real gate.

    find_contact(text) -> "phone" | "email" | "link" | "handle" | None
    mask_contacts(text) -> text with every contact detail replaced by •••

Beyond the plain patterns it normalises obfuscation: spelled-out digits
("zero eight zero three"), digits split by spaces, dashes, dots, brackets or
single letters ("0a8b0c3"), and "at"/"dot" spellings of emails and domains.
"""

from __future__ import annotations

import re

PHONE = "phone"
EMAIL = "email"
LINK = "link"
HANDLE = "handle"

# Checked in this order; the first kind found is reported.
KINDS = [PHONE, EMAIL, LINK, HANDLE]

_WORD_DIGITS = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
}
_WORD_DIGIT_RE = re.compile(r"\b(" + "|".join(_WORD_DIGITS) + r")\b", re.IGNORECASE)

# A run of digits, allowing separators (space - . ( ) / _ , +) and single
# letters between them. Nigerian numbers: 0 or 234, then 7/8/9 and 0/1, then
# 8 digits (e.g. 0803 555 1234, +234 803 555 1234), or the 10 digits alone.
_DIGIT_RUN_RE = re.compile(r"\+?\d(?:(?:[\s\-.()/_,+]+|(?<=\d)[a-z](?=[\s\-.()/_,+]*\d))*\d)+", re.IGNORECASE)
_NG_PHONE_RE = re.compile(r"(?:234|0)?[789][01]\d{8}")
_PHONE_MAX_DIGITS = 13  # 234 + 10

_TLDS = r"(?:com|ng|net|org|co|io|me|app|info|biz|ly|link|xyz|online|shop|store)"
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", re.IGNORECASE)
# "tolu at gmail dot com", "tolu (at) gmail (dot) com", "tolu[at]gmail.com"
_EMAIL_SPELLED_RE = re.compile(
    r"\b[\w.+-]+\s*(?:\(at\)|\[at\]|\bat\b)\s*[\w-]+\s*(?:\(dot\)|\[dot\]|\bdot\b|\.)\s*" + _TLDS + r"\b",
    re.IGNORECASE,
)
_LINK_RE = re.compile(
    r"https?://|\bwww\s*\.|\b[\w-]+\s*(?:\.|\(dot\)|\[dot\]|\s+dot\s+)\s*" + _TLDS + r"\b(?:\.ng)?",
    re.IGNORECASE,
)
# @handle, not the @ inside an email.
_HANDLE_RE = re.compile(r"(?<![\w.])@[a-z0-9_.]{2,}", re.IGNORECASE)


def _spell_digits(text: str) -> str:
    return _WORD_DIGIT_RE.sub(lambda m: _WORD_DIGITS[m.group(1).lower()], text)


def _has_phone(text: str) -> bool:
    """A phone number made of consecutive digit groups in a run, starting at a
    group boundary. So "0803 555 1234" matches, but a list of prices like
    "185000 190000 200000" doesn't (no number starts where a group starts)."""
    for run in _DIGIT_RUN_RE.finditer(_spell_digits(text)):
        groups = re.findall(r"\d+", run.group(0))
        for start in range(len(groups)):
            digits = ""
            for group in groups[start:]:
                digits += group
                if len(digits) > _PHONE_MAX_DIGITS:
                    break
                if _NG_PHONE_RE.fullmatch(digits):
                    return True
    return False


def find_contact(text: str) -> str | None:
    """The first kind of contact detail in `text`, or None."""
    if not text:
        return None
    if _has_phone(text):
        return PHONE
    if _EMAIL_RE.search(text) or _EMAIL_SPELLED_RE.search(text):
        return EMAIL
    if _LINK_RE.search(text):
        return LINK
    if _HANDLE_RE.search(text):
        return HANDLE
    return None


MASK = "•••"


def _run_is_phone(run: str) -> bool:
    groups = re.findall(r"\d+", run)
    for start in range(len(groups)):
        digits = ""
        for group in groups[start:]:
            digits += group
            if len(digits) > _PHONE_MAX_DIGITS:
                break
            if _NG_PHONE_RE.fullmatch(digits):
                return True
    return False


def mask_contacts(text: str) -> str:
    """`text` with contact details replaced by •••, for the deal chat before
    the seller's video is rated Good. Anything still detectable after the
    pattern pass (spelled-out numbers and the like) loses every digit."""
    if not text or find_contact(text) is None:
        return text
    out = text
    for pattern in (_EMAIL_RE, _EMAIL_SPELLED_RE, _LINK_RE, _HANDLE_RE):
        out = pattern.sub(MASK, out)
    out = _DIGIT_RUN_RE.sub(lambda m: MASK if _run_is_phone(m.group(0)) else m.group(0), out)
    if find_contact(out) is not None:
        out = _WORD_DIGIT_RE.sub("•", out)
        out = re.sub(r"\d", "•", out)
    return out
