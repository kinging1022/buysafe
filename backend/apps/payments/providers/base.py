"""The payment provider interfaces. Services only talk to these; the fake
(fake.py) runs in dev and tests, Anchor (anchor.py) in production.

Amounts are Decimal naira: a transfer can arrive with kobo, and ₦175,000.50
is not ₦175,000. Providers that count in kobo convert at the edge.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


class ProviderError(Exception):
    """The provider refused or couldn't be reached. Safe to retry later."""


class NameEnquiryError(ProviderError):
    """The bank couldn't be reached, or the account doesn't exist."""


@dataclass(frozen=True)
class VirtualAccount:
    account_number: str
    bank: str  # "9 Payment Service Bank"
    account_name: str  # what the sender's bank app shows
    # The provider's own id for this account, if payments are reported
    # against it rather than the account number (Anchor's PayWithTransfer
    # reference).
    provider_ref: str = ""


@dataclass(frozen=True)
class IncomingTransfer:
    """Money that arrived in one of our virtual accounts. Matched to its
    intent by `account_ref` when the provider sends one, else by
    `account_number`."""

    provider_ref: str
    account_number: str  # the virtual account it was paid into ("" if the provider doesn't say)
    amount: Decimal
    sender_name: str
    sender_bank: str
    sender_bank_code: str
    sender_account: str  # full number: refunds go back here ("" if the provider doesn't say)
    received_at: datetime
    account_ref: str = ""  # VirtualAccount.provider_ref
    session_id: str = ""  # the NIP session id: lets a bank trace the transfer


@dataclass(frozen=True)
class TransferFailed:
    """An outgoing transfer (refund or payout) the provider accepted, then
    failed or reversed."""

    provider_ref: str  # what TransferProvider.send returned
    reason: str
    reference: str = ""  # TransferProvider.reference(idempotency_key), for a ref we haven't saved yet


@dataclass(frozen=True)
class TransferSucceeded:
    """An outgoing transfer that reached the other bank: only now is the money
    gone. `reference` finds it when this arrives before send() has returned
    (it can come within a second)."""

    provider_ref: str
    reference: str = ""
    session_id: str = ""  # the NIP session id: lets a bank trace the transfer


@dataclass(frozen=True)
class LedgerLine:
    """One movement on the deposit account, for the daily reconciliation."""

    id: str
    direction: str  # "credit" or "debit"
    amount: Decimal
    at: datetime
    payment_ref: str = ""  # a credit: the IncomingTransfer.provider_ref it settles
    transfer_ref: str = ""  # a debit: what TransferProvider.send / fee returned


class VirtualAccountProvider:
    def create(self, deal_ref: str, amount: int, expires_at: datetime, customer_email: str = "") -> VirtualAccount:
        """A new account number that accepts transfers for one deal."""
        raise NotImplementedError

    def verify_webhook(self, headers, body: bytes) -> bool:
        """True if the webhook really came from the provider."""
        raise NotImplementedError

    def parse_webhook(self, body: bytes) -> IncomingTransfer | TransferFailed | TransferSucceeded | None:
        """None for events we don't act on."""
        raise NotImplementedError

    def ledger(self, start: datetime, end: datetime) -> list:
        """Every LedgerLine on the deposit account from `start` to `end`, for
        the daily reconciliation."""
        raise NotImplementedError

    def balance(self) -> Decimal:
        """The deposit account's balance now."""
        raise NotImplementedError


class TransferProvider:
    def name_enquiry(self, bank_code: str, account: str) -> str:
        """The account holder's name as the bank has it. Raises NameEnquiryError."""
        raise NotImplementedError

    def send(self, bank_code: str, account: str, amount: Decimal, narration: str, idempotency_key: str) -> str:
        """Start an NIP transfer; returns the provider's reference. Sending the
        same idempotency_key twice must never move money twice."""
        raise NotImplementedError

    def reference(self, idempotency_key: str) -> str:
        """The reference send() gives the provider for this key."""
        raise NotImplementedError

    def status(self, provider_ref: str) -> TransferSucceeded | TransferFailed | None:
        """Where a sent transfer is now; None while it's still on its way."""
        raise NotImplementedError

    def collect_fee(self, amount: Decimal, narration: str, idempotency_key: str) -> str:
        """Move our fee from the deposit account to the revenue account (an
        internal transfer, done when it returns). Same idempotency rule as send."""
        raise NotImplementedError
