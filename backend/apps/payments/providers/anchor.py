"""Anchor (getanchor.co): Pay with Transfer for collections, NIP transfers
for refunds and payouts, and the webhook for both.

    Collect   POST /pay/pay-with-transfer makes a dynamic virtual account for
              one deal (amount in kobo, expires with the hold, max one hour).
              Anchor reports the payment as a `payin.received` event that
              only names the PayIn. We fetch it (GET /pay/payin/{id}
              ?include=Charge), never trusting the webhook body: the PayIn's
              `reference` is what we match on (PaymentIntent.virtual_account_ref)
              and its Charge has the sender, so refunds can go back.
    Send      verify the name, create a counterparty (verifyName), then
              POST /api/v1/transfers from our deposit account
              (ANCHOR_ACCOUNT_ID). The idempotency key is the transfer
              reference, and we look it up first, so a retry after a timeout
              never sends twice.
    Webhook   x-anchor-signature = Base64(hex(HMAC-SHA1(body, ANCHOR_WEBHOOK_SECRET))).
              The event is the whole body ({"id", "type", "relationships"}),
              naming what happened; we fetch the details ourselves.

Sandbox (ANCHOR_COLLECT=nuban): Pay with Transfer only exists in production,
so each deal gets a virtual NUBAN on the deposit account instead. Anchor
reports a payment into one only as the settlement credit on that account
(`transaction.created`); we fetch the transaction, then its Payment. A NUBAN
never expires and takes any amount, so late and wrong transfers land and are
refunded like any other. Never for production.

Not covered by Anchor yet, so not wired:
- the sender's bank comes as a name, not its NIP code; we look the name up in
  Anchor's bank list, and if it doesn't match exactly one bank the refund is
  flagged for staff (Refund status `manual`);
- there's no statement endpoint for the daily reconciliation.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import re
from datetime import timezone as dt_timezone
from decimal import Decimal

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .. import bank_codes
from .base import (
    IncomingTransfer,
    LedgerLine,
    NameEnquiryError,
    ProviderError,
    TransferFailed,
    TransferProvider,
    TransferSucceeded,
    VirtualAccount,
    VirtualAccountProvider,
)

logger = logging.getLogger(__name__)

SIGNATURE_HEADER = "x-anchor-signature"
TIMEOUT = 20  # seconds
MAX_EXPIRY = 3600  # Anchor expires every dynamic account after an hour
BANKS_CACHE_KEY = "anchor:banks:v2"  # [(name, nipCode)]
LEDGER_PAGE = 100
SANDBOX_BVN = "22222222222"  # Anchor's test BVN; a NUBAN needs one


def _kobo(naira) -> int:
    return int(Decimal(naira) * 100)


def _naira(kobo) -> Decimal:
    return Decimal(int(kobo)) / 100


def _reference(key: str) -> str:
    """Anchor references are alphanumeric."""
    return re.sub(r"[^A-Za-z0-9]", "", key)


def _event(body: bytes) -> dict:
    """The event Anchor sent. It comes as the whole body; a {"data": event}
    wrapper is accepted too."""
    doc = json.loads(body)
    if "type" not in doc and isinstance(doc.get("data"), dict):
        return doc["data"]
    return doc


def _when(text):
    """Anchor's timestamps; one without an offset reads as UTC (its
    expiryDate is the exception, Lagos time, and isn't parsed here)."""
    when = parse_datetime(text or "")
    if when is not None and timezone.is_naive(when):
        when = when.replace(tzinfo=dt_timezone.utc)
    return when or timezone.now()


def _error_detail(res) -> str:
    try:
        errors = res.json().get("errors") or []
        return "; ".join(f"{e.get('status')} {e.get('title')}: {e.get('detail')}" for e in errors) or res.text[:200]
    except ValueError:
        return res.text[:200]


class _Client:
    def __init__(self):
        if not settings.ANCHOR_API_KEY:
            raise ProviderError("ANCHOR_API_KEY is not set.")
        self.base = settings.ANCHOR_BASE_URL.rstrip("/")
        self.headers = {"x-anchor-key": settings.ANCHOR_API_KEY, "accept": "application/json"}

    def request(self, method, path, payload=None, missing_ok=False):
        """The parsed body. 404 returns None when `missing_ok`; any other
        4xx/5xx or network failure raises ProviderError."""
        try:
            res = requests.request(method, self.base + path, json=payload, headers=self.headers, timeout=TIMEOUT)
        except requests.RequestException as exc:
            raise ProviderError(f"Anchor unreachable: {exc}") from exc
        if res.status_code == 404 and missing_ok:
            return None
        if res.status_code >= 400:
            raise ProviderError(f"Anchor {method} {path} -> {res.status_code}: {_error_detail(res)}")
        return res.json()


class AnchorVirtualAccountProvider(VirtualAccountProvider):
    def create(self, deal_ref, amount, expires_at, customer_email=""):
        if settings.ANCHOR_COLLECT == "nuban":
            return self._nuban(deal_ref, customer_email)
        seconds = int((expires_at - timezone.now()).total_seconds())
        body = _Client().request(
            "POST",
            "/pay/pay-with-transfer",
            {
                "data": {
                    "type": "PayWithTransfer",
                    "attributes": {
                        "reference": _reference(f"{settings.ANCHOR_REFERENCE_PREFIX}deal{deal_ref}"),
                        "customer": {
                            # What the sender's bank app shows as the account name.
                            "fullName": f"buysafe Escrow Deal {deal_ref}",
                            "email": customer_email or settings.ANCHOR_CUSTOMER_EMAIL,
                        },
                        "expiryTime": max(60, min(seconds, MAX_EXPIRY)),
                        "amount": _kobo(amount),
                        "metadata": {"deal": str(deal_ref)},
                    },
                }
            },
        )
        attrs = body["data"]["attributes"]
        return VirtualAccount(
            account_number=attrs["accountNumber"],
            bank=attrs.get("bank", {}).get("name", ""),
            account_name=attrs.get("accountName", ""),
            provider_ref=attrs["reference"],  # Anchor's "…-anc_va-ref"; PayIns carry it
        )

    def _nuban(self, deal_ref, customer_email):
        """The sandbox stand-in for Pay with Transfer: a virtual NUBAN that
        settles into ANCHOR_ACCOUNT_ID. Every call makes a new number, even
        with the same reference."""
        if "sandbox" not in settings.ANCHOR_BASE_URL:
            raise ProviderError("ANCHOR_COLLECT=nuban is for the sandbox only: a NUBAN never expires.")
        body = _Client().request(
            "POST",
            "/api/v1/virtual-nubans",
            {
                "data": {
                    "type": "VirtualNuban",
                    "attributes": {
                        "virtualAccountDetail": {
                            "name": f"buysafe Escrow Deal {deal_ref}",
                            "bvn": SANDBOX_BVN,
                            "reference": _reference(f"{settings.ANCHOR_REFERENCE_PREFIX}deal{deal_ref}"),
                            "email": customer_email or settings.ANCHOR_CUSTOMER_EMAIL,
                            "description": f"Deal {deal_ref}",
                            "permanent": True,  # Anchor makes them permanent regardless
                        }
                    },
                    "relationships": {
                        "settlementAccount": {"data": {"id": settings.ANCHOR_ACCOUNT_ID, "type": "DepositAccount"}}
                    },
                }
            },
        )
        data = body["data"]
        attrs = data["attributes"]
        return VirtualAccount(
            account_number=attrs["accountNumber"],
            bank=attrs.get("bank", {}).get("name", ""),
            account_name=attrs.get("accountName", ""),
            provider_ref=data["id"],  # "…-anc_acc_num"; its Payments name it
        )

    def verify_webhook(self, headers, body):
        secret = settings.ANCHOR_WEBHOOK_SECRET
        given = headers.get(SIGNATURE_HEADER, "")
        if not secret or not given:
            return False
        digest = hmac.new(secret.encode(), body, hashlib.sha1).hexdigest()
        expected = base64.b64encode(digest.encode()).decode()
        return hmac.compare_digest(given, expected)

    def parse_webhook(self, body):
        event = _event(body)
        kind = event["type"]
        related = event.get("relationships", {})
        if kind == "payin.received":
            return self._payin(related["payIn"]["data"]["id"])
        if kind == "transaction.created":
            return self._settlement(related["transaction"]["data"]["id"])
        if kind in ("nip.transfer.successful", "nip.transfer.failed", "nip.transfer.reversed"):
            transfer = related.get("transfer", {}).get("data", {})
            if not transfer.get("id"):
                logger.error("Anchor %s without a transfer id: %s", kind, event.get("id"))
                return None
            # Fetched like a payment: the event only says which transfer.
            return AnchorTransferProvider().status(transfer["id"])
        return None  # every other event type goes to the same URL; not ours to act on

    def _settlement(self, transaction_id):
        """A ledger line on one of our accounts. Only a settlement credit for a
        virtual NUBAN payment is money in; our own payouts, fees and anything
        else are None."""
        line = _Client().request("GET", f"/api/v1/transactions/{transaction_id}")["data"]
        attrs = line["attributes"]
        payment = line.get("relationships", {}).get("payment", {}).get("data", {})
        if attrs.get("transactionType") != "Settlement" or attrs.get("direction") != "Credit" or not payment.get("id"):
            return None
        return self._payment(payment["id"])

    def _payment(self, payment_id):
        """A transfer into a virtual NUBAN, as Anchor recorded it. Matched to
        its deal by the NUBAN's id (PaymentIntent.virtual_account_ref)."""
        payment = _Client().request("GET", f"/api/v1/payments/{payment_id}")["data"]
        nuban = payment.get("relationships", {}).get("virtualNuban", {}).get("data", {}).get("id")
        if not nuban:
            return None
        attrs = payment["attributes"]
        sender = attrs.get("counterParty") or {}
        if not sender.get("accountNumber"):
            logger.warning("Anchor payment %s came without the sender; its refunds will need a person", payment_id)
        sender_bank = (sender.get("bank") or {}).get("name", "")
        return IncomingTransfer(
            provider_ref=payment["id"],
            account_number="",  # Anchor doesn't repeat it; the intent has it
            account_ref=nuban,
            amount=_naira(attrs["amount"]),
            sender_name=sender.get("accountName", ""),
            sender_bank=sender_bank,
            sender_bank_code=self._bank_code(sender_bank, sender.get("accountNumber", ""), sender.get("accountName", ""))
            if sender_bank
            else "",
            sender_account=sender.get("accountNumber", ""),
            received_at=_when(attrs.get("paidAt") or attrs.get("createdAt")),
            session_id=attrs.get("sessionId", ""),
        )

    def _payin(self, payin_id):
        """The PayIn as Anchor has it, with the sender from its Charge.
        Raises ProviderError if Anchor can't be reached (the webhook then
        answers 503 and Anchor retries)."""
        body = _Client().request("GET", f"/pay/payin/{payin_id}?include=Charge")
        payin = body["data"]
        attrs = payin["attributes"]
        if attrs.get("status") != "COMPLETED":
            return None
        charge = next((i for i in body.get("included", []) if i.get("type") == "Charge"), {})
        sender = charge.get("attributes", {}).get("transferDetails", {})
        if not sender.get("senderAccountNumber"):
            logger.warning("Anchor PayIn %s came without the sender; its refunds will need a person", payin_id)
        sender_bank = sender.get("senderBank", "")
        return IncomingTransfer(
            provider_ref=payin["id"],
            account_number=sender.get("beneficiaryAccountNumber", ""),
            account_ref=attrs["reference"],
            amount=_naira(attrs["amount"]),
            sender_name=sender.get("senderName", ""),
            sender_bank=sender_bank,
            sender_bank_code=self._bank_code(
                sender_bank, sender.get("senderAccountNumber", ""), sender.get("senderName", "")
            )
            if sender_bank
            else "",
            sender_account=sender.get("senderAccountNumber", ""),
            received_at=_when(attrs.get("paidAt") or attrs.get("createdAt")),
            session_id=attrs.get("sessionId") or sender.get("sessionId", ""),
        )

    def _bank_code(self, name, account="", holder=""):
        """The sender's NIP code from Anchor's bank list (see bank_codes), or ""."""
        banks = cache.get(BANKS_CACHE_KEY)
        if banks is None:
            rows = _Client().request("GET", "/api/v1/banks")["data"]
            banks = [(b["attributes"]["name"], b["attributes"]["nipCode"]) for b in rows]
            cache.set(BANKS_CACHE_KEY, banks, 24 * 3600)

        def lookup(code, number):
            try:
                return AnchorTransferProvider().name_enquiry(code, number)
            except ProviderError:
                return ""

        return bank_codes.resolve(name, banks, sender_account=account, sender_name=holder, lookup=lookup)

    def ledger(self, start, end):
        """The deposit account's ledger lines. Anchor filters by whole UTC
        days (from/to, inclusive), so we ask for the days around the window
        and keep what falls inside it."""
        client = _Client()
        first = start.astimezone(dt_timezone.utc).date()
        last = end.astimezone(dt_timezone.utc).date()
        lines, page = [], 0
        while True:
            body = client.request(
                "GET",
                f"/api/v1/transactions?accountId={settings.ANCHOR_ACCOUNT_ID}&from={first}&to={last}"
                f"&size={LEDGER_PAGE}&page={page}",
            )
            for row in body["data"]:
                line = self._line(row)
                if start <= line.at < end:
                    lines.append(line)
            pages = body.get("meta", {}).get("pagination", {}).get("totalPages", 1)
            page += 1
            if page >= pages or not body["data"]:
                return lines

    @staticmethod
    def _line(row):
        attrs = row["attributes"]
        related = row.get("relationships", {})
        return LedgerLine(
            id=row["id"],
            direction=attrs["direction"].lower(),
            amount=_naira(attrs["amount"]),
            at=_when(attrs.get("createdAt")),
            payment_ref=related.get("payment", {}).get("data", {}).get("id", ""),
            transfer_ref=related.get("transfer", {}).get("data", {}).get("id", ""),
        )

    def balance(self):
        body = _Client().request("GET", f"/api/v1/accounts/balance/{settings.ANCHOR_ACCOUNT_ID}")
        return _naira(body["data"]["ledgerBalance"])


class AnchorTransferProvider(TransferProvider):
    def name_enquiry(self, bank_code, account):
        try:
            body = _Client().request("GET", f"/api/v1/payments/verify-account/{bank_code}/{account}")
        except ProviderError as exc:
            raise NameEnquiryError(str(exc)) from exc
        return body["data"]["attributes"]["accountName"]

    def reference(self, idempotency_key):
        return _reference(f"{settings.ANCHOR_REFERENCE_PREFIX}{idempotency_key}")

    def send(self, bank_code, account, amount, narration, idempotency_key):
        client = _Client()
        reference = self.reference(idempotency_key)
        existing = _already_sent(client, reference)
        if existing:
            return existing

        # Anchor refuses a counterparty without a name; with verifyName it
        # keeps the bank's own anyway.
        name = self.name_enquiry(bank_code, account)
        counterparty = client.request(
            "POST",
            "/api/v1/counterparties",
            {
                "data": {
                    "type": "CounterParty",
                    "attributes": {"bankCode": bank_code, "accountNumber": account, "accountName": name, "verifyName": True},
                }
            },
        )["data"]["id"]
        transfer = client.request(
            "POST",
            "/api/v1/transfers",
            {
                "data": {
                    "type": "NIPTransfer",
                    "attributes": {
                        "amount": _kobo(amount),
                        "currency": "NGN",
                        "reason": narration,
                        "reference": reference,
                    },
                    "relationships": {
                        "account": {"data": {"id": settings.ANCHOR_ACCOUNT_ID, "type": "DepositAccount"}},
                        "counterParty": {"data": {"id": counterparty, "type": "CounterParty"}},
                    },
                }
            },
        )["data"]
        return _accepted(transfer, reference)

    def collect_fee(self, amount, narration, idempotency_key):
        """A book transfer to ANCHOR_REVENUE_ACCOUNT_ID: free, and COMPLETED
        as soon as Anchor answers."""
        if not settings.ANCHOR_REVENUE_ACCOUNT_ID:
            raise ProviderError("ANCHOR_REVENUE_ACCOUNT_ID is not set.")
        client = _Client()
        reference = self.reference(idempotency_key)
        existing = _already_sent(client, reference)
        if existing:
            return existing
        transfer = client.request(
            "POST",
            "/api/v1/transfers",
            {
                "data": {
                    "type": "BookTransfer",
                    "attributes": {"amount": _kobo(amount), "currency": "NGN", "reason": narration, "reference": reference},
                    "relationships": {
                        "account": {"data": {"id": settings.ANCHOR_ACCOUNT_ID, "type": "DepositAccount"}},
                        "destinationAccount": {"data": {"id": settings.ANCHOR_REVENUE_ACCOUNT_ID, "type": "DepositAccount"}},
                    },
                }
            },
        )["data"]
        return _accepted(transfer, reference)

    def status(self, provider_ref):
        transfer = _Client().request("GET", f"/api/v1/transfers/{provider_ref}")["data"]
        attrs = transfer["attributes"]
        state = attrs.get("status", "").upper()
        if state in ("COMPLETED", "SUCCESSFUL"):
            return TransferSucceeded(
                provider_ref=transfer["id"], reference=attrs.get("reference", ""), session_id=attrs.get("sessionId", "")
            )
        if state in ("FAILED", "REVERSED"):
            why = attrs.get("failureReason")
            return TransferFailed(
                provider_ref=transfer["id"],
                reason=f"{state.lower()}: {why}" if why else state.lower(),
                reference=attrs.get("reference", ""),
            )
        return None  # PENDING / PROCESSING: still on its way


def _already_sent(client, reference):
    """The id of a transfer already made with this reference (a retry after a
    timeout), so it's never made twice; None if there isn't one."""
    existing = client.request("GET", f"/api/v1/transfers/by-reference/{reference}", missing_ok=True)
    if not (existing and existing.get("data")):
        return None
    transfer = existing["data"]
    if transfer["attributes"].get("status", "").upper() in ("FAILED", "REVERSED"):
        raise ProviderError(f"Transfer {reference} already failed at Anchor; needs a person.")
    return transfer["id"]


def _accepted(transfer, reference):
    """The new transfer's id, unless Anchor refused it: a refusal still comes
    back 201, e.g. FAILED with failureReason TRANSFER_LIMIT_EXCEEDED."""
    attrs = transfer.get("attributes", {})
    if attrs.get("failureReason") or attrs.get("status", "").upper() in ("FAILED", "REVERSED"):
        raise ProviderError(f"Anchor refused transfer {reference}: {attrs.get('failureReason') or attrs.get('status')}")
    return transfer["id"]
