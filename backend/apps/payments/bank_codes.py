"""The sender's bank NIP code, worked out from the bank name a payment gives us.

Anchor tells us who sent a transfer and their bank's *name* ("STANBIC IBTC
BANK", "Opay Digital Services", "GTBank Plc"), not its NIP code, which a
refund needs. The code always comes from the provider's own bank list; we
only decide which entry the name means, in steps, and stop at the first
that gives exactly one bank:

    1. the same distinctive words, once both names are cleaned up: case,
       punctuation and filler words (PLC, LIMITED, NIGERIA, BANK...) go;
       short forms (GTB, UBA, FCMB, MFB...) are spelt out. Bracketed
       asides count here, so "Access Bank" is ACCESS BANK, not
       "ACCESS(DIAMOND) BANK";
    2. the same, ignoring bracketed asides ("OPAY ... (OPAY)");
    3. one name's words all inside the other's ("KUDA" in "KUDA MICROFINANCE");
    then, if a step finds more than one: ask each candidate bank who owns
    the sender's account (name enquiry) and keep the one whose answer is
    the sender.

No bank, or more than one even after 3, gives "": the refund then waits for
a person. A wrong guess would send someone's money to the wrong account.
"""

from __future__ import annotations

import logging
import re

from .names import tokens

logger = logging.getLogger(__name__)

# Words that say nothing about which bank it is.
FILLER = {
    "BANK", "BANKS", "PLC", "LIMITED", "LTD", "NIGERIA", "NIG", "NG", "OF", "AND", "THE", "CO", "COMPANY",
    "SERVICES", "SERVICE", "DIGITAL", "GROUP", "HOLDINGS", "INTERNATIONAL",
}

# Short forms people and banks use, spelt out the way bank lists write them.
# Whole words only; applied to both names, so either spelling meets the other.
SHORT_FORMS = [
    (r"\bGT ?BANK\b|\bGTB\b|\bGUARANTY TRUST\b", "GUARANTY TRUST"),
    (r"\bUBA\b", "UNITED BANK FOR AFRICA"),
    (r"\bFCMB\b", "FIRST CITY MONUMENT"),
    (r"\bFBN\b|\bFIRSTBANK\b", "FIRST"),
    (r"\bO ?PAY\b|\bPAYCOM\b", "OPAY"),
    (r"\bPALM ?PAY\b", "PALMPAY"),
    # Anchor's list still has Moniepoint MFB (090405) under its old name.
    (r"\bMONIE ?POINT\b|\bROLEZ\b", "MONIEPOINT"),
    (r"\bECO ?BANK\b", "ECOBANK"),
    (r"\b9 ?PSB\b|\b9 PAYMENT\b|\bNINE PAYMENT\b", "9 PAYMENT"),
    (r"\bMFB\b|\bMFBANK\b|\bMICRO ?FINANCE\b", "MICROFINANCE"),
]

# Name enquiries we'll make to tell a few look-alike banks apart.
MAX_LOOKUPS = 3


def words(bank_name: str, asides=False) -> frozenset:
    """"Opay Digital Services Limited (OPAY)" -> {"OPAY"};
    "Kuda MFB" -> {"KUDA", "MICROFINANCE"}. `asides` keeps what's in brackets:
    "ACCESS(DIAMOND) BANK" -> {"ACCESS", "DIAMOND"}."""
    text = (bank_name or "").upper().replace("&", " AND ")
    if not asides:
        text = re.sub(r"\(.*?\)", " ", text)
    text = " ".join(re.sub(r"[^A-Z0-9 ]", " ", text).split())
    for pattern, spelt_out in SHORT_FORMS:
        text = re.sub(pattern, spelt_out, text)
    return frozenset(w for w in text.split() if w not in FILLER)


def same_person(a: str, b: str) -> bool:
    """Two account names for one person: banks reorder names and add middle
    names, so two shared words is enough ("ADA NWOSU" / "NWOSU ADA CHIOMA")."""
    x, y = set(tokens(a)), set(tokens(b))
    if not x or not y:
        return False
    return x == y or len(x & y) >= 2


def resolve(sender_bank, banks, *, sender_account="", sender_name="", lookup=None) -> str:
    """The NIP code for `sender_bank`, from `banks` [(name, code), ...], or ""
    when we can't be sure. `lookup(code, account) -> account name` is the
    name enquiry ("" if it fails), used only to tell look-alike banks apart."""
    wanted, wanted_all = words(sender_bank), words(sender_bank, asides=True)
    if not wanted:
        return ""
    listed = [(words(name), words(name, asides=True), code) for name, code in banks]
    steps = (
        lambda w, w_all: w_all == wanted_all,  # same words, asides included
        lambda w, w_all: w == wanted,  # same words
        lambda w, w_all: w and (wanted <= w or w <= wanted),  # words inside
    )
    for fits in steps:
        codes = sorted({code for w, w_all, code in listed if fits(w, w_all)})
        if len(codes) == 1:
            return codes[0]
        if len(codes) > 1:
            return _by_account_holder(sender_bank, codes, sender_account, sender_name, lookup)
    logger.warning("Sender bank %r matched no bank", sender_bank)
    return ""


def _by_account_holder(sender_bank, codes, account, sender_name, lookup):
    if not (lookup and account and sender_name) or len(codes) > MAX_LOOKUPS:
        logger.warning("Sender bank %r matched %s banks %s", sender_bank, len(codes), codes)
        return ""
    # lookup returns "" when the account isn't at that bank or it can't be reached.
    holders = [code for code in codes if same_person(lookup(code, account), sender_name)]
    if len(holders) == 1:
        return holders[0]
    logger.warning("Sender bank %r: %s of %s look-alike banks hold the account", sender_bank, len(holders), codes)
    return ""
