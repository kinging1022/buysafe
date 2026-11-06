"""The fake provider: dev and tests. Nothing leaves the building.

- Virtual accounts are 99 + the deal ref, zero-padded ("9900000317").
- Webhooks are signed with HMAC-SHA256 of the body using
  PAYMENTS_WEBHOOK_SECRET, in the X-Buysafe-Signature header. Send one with
  `manage.py fake_transfer <account> <amount>`.
- Name enquiry returns settings.FAKE_ACCOUNT_NAME, except numbers ending in
  8 (a stranger's name) and 9 (the bank can't be reached). Tests can set
  exact names in `FakeTransferProvider.directory`.
- Transfers always succeed unless `FakeTransferProvider.fail_next` is set;
  every call is kept in `sent` (fees in `fees`) for tests. A sent transfer's
  status() is successful; a signed {"transfer": ref, "status": "successful" |
  "failed"} webhook reports one.
- The ledger and balance mirror our own records unless tests set
  `ledger_rows` / `balance_now`, so reconciliation agrees by default.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime
from decimal import Decimal

from django.conf import settings
from django.utils.dateparse import parse_datetime

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

SIGNATURE_HEADER = "X-Buysafe-Signature"


def sign(body: bytes) -> str:
    return hmac.new(settings.PAYMENTS_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()


class FakeVirtualAccountProvider(VirtualAccountProvider):
    ledger_rows: list = None  # set in tests; otherwise the ledger mirrors our records
    balance_now = None

    def create(self, deal_ref, amount, expires_at, customer_email=""):
        return VirtualAccount(
            account_number=f"99{int(deal_ref):08d}",
            bank="9 Payment Service Bank",
            account_name=f"buysafe Escrow · Deal {deal_ref}",
        )

    def verify_webhook(self, headers, body):
        given = headers.get(SIGNATURE_HEADER, "")
        return bool(settings.PAYMENTS_WEBHOOK_SECRET) and hmac.compare_digest(given, sign(body))

    def parse_webhook(self, body):
        data = json.loads(body)
        if "transfer" in data:
            ref = str(data["transfer"])
            if data.get("status") == "successful":
                return TransferSucceeded(provider_ref=ref, reference=data.get("reference", ""), session_id="FAKE-SESSION")
            return TransferFailed(provider_ref=ref, reason=data.get("reason", "failed"), reference=data.get("reference", ""))
        return IncomingTransfer(
            provider_ref=str(data["provider_ref"]),
            account_number=str(data["account_number"]),
            amount=Decimal(str(data["amount"])),
            sender_name=data.get("sender_name", ""),
            sender_bank=data.get("sender_bank", ""),
            sender_bank_code=data.get("sender_bank_code", ""),
            sender_account=str(data["sender_account"]),
            received_at=parse_datetime(data["received_at"]) if data.get("received_at") else datetime.now().astimezone(),
            account_ref=data.get("account_ref", ""),
        )

    def ledger(self, start, end):
        if FakeVirtualAccountProvider.ledger_rows is not None:
            return [r for r in FakeVirtualAccountProvider.ledger_rows if start <= r.at < end]
        from apps.payments.models import FeeTransfer, InboundTransfer, Payout, Refund, TransferStatus

        lines = [
            LedgerLine(f"in-{t.provider_ref}", "credit", t.amount, t.received_at, payment_ref=t.provider_ref)
            for t in InboundTransfer.objects.filter(received_at__gte=start, received_at__lt=end)
        ]
        out = [TransferStatus.SENT, TransferStatus.SUCCESSFUL]
        for model in (Refund, Payout, FeeTransfer):
            for t in model.objects.filter(status__in=out, sent_at__gte=start, sent_at__lt=end).exclude(provider_ref=""):
                lines.append(LedgerLine(f"out-{t.provider_ref}", "debit", Decimal(t.amount), t.sent_at, transfer_ref=t.provider_ref))
        return lines

    def balance(self):
        if FakeVirtualAccountProvider.balance_now is not None:
            return Decimal(FakeVirtualAccountProvider.balance_now)
        from apps.payments.reconciliation import expected_balance

        return expected_balance()


class FakeTransferProvider(TransferProvider):
    directory: dict = {}  # {account_number: name}, for tests
    sent: list = []
    fees: list = []
    fail_next = 0  # fail this many sends, then succeed

    def name_enquiry(self, bank_code, account):
        if account in self.directory:
            return self.directory[account]
        if account.endswith("9"):
            raise NameEnquiryError("Bank unreachable (fake).")
        if account.endswith("8"):
            return "CHUKWU EMEKA PAUL"
        return settings.FAKE_ACCOUNT_NAME

    def reference(self, idempotency_key):
        return f"FAKE-{idempotency_key}"

    def status(self, provider_ref):
        return TransferSucceeded(provider_ref=provider_ref, reference=provider_ref, session_id="FAKE-SESSION")

    def collect_fee(self, amount, narration, idempotency_key):
        if FakeTransferProvider.fail_next:
            FakeTransferProvider.fail_next -= 1
            raise ProviderError("Fee transfer failed (fake).")
        ref = self.reference(idempotency_key)
        if not any(f["ref"] == ref for f in FakeTransferProvider.fees):
            FakeTransferProvider.fees.append({"amount": Decimal(amount), "narration": narration, "ref": ref})
        return ref

    def send(self, bank_code, account, amount, narration, idempotency_key):
        if FakeTransferProvider.fail_next:
            FakeTransferProvider.fail_next -= 1
            raise ProviderError("Transfer failed (fake).")
        ref = self.reference(idempotency_key)
        if not any(s["idempotency_key"] == idempotency_key for s in FakeTransferProvider.sent):
            FakeTransferProvider.sent.append(
                {"bank_code": bank_code, "account": account, "amount": Decimal(amount), "narration": narration,
                 "idempotency_key": idempotency_key, "ref": ref}
            )
        return ref

    @classmethod
    def reset(cls):
        cls.directory = {}
        cls.sent = []
        cls.fees = []
        cls.fail_next = 0
        FakeVirtualAccountProvider.ledger_rows = None
        FakeVirtualAccountProvider.balance_now = None
