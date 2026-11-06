"""The daily reconciliation: the deposit account's ledger against our records
for one day (Lagos time), three ways. Any difference is emailed to ADMINS
and logged; nothing is fixed automatically.

    in       every credit is an InboundTransfer we recorded, and back
    out      every debit is a Refund, Payout or FeeTransfer we sent, and back
    balance  the account holds exactly what our records say it should

Lines are matched by id, not by day: the ledger is read a little either side
of the day, so a settlement that lands seconds after midnight isn't flagged.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.core.mail import mail_admins
from django.db.models import Sum

from apps.notifications.clock import LAGOS

from . import providers
from .models import FeeTransfer, InboundTransfer, Payout, Refund, TransferStatus

logger = logging.getLogger(__name__)

SLACK = timedelta(hours=2)
OUT_MODELS = (Refund, Payout, FeeTransfer)
LEFT_THE_ACCOUNT = (TransferStatus.SENT, TransferStatus.SUCCESSFUL)


def day_bounds(day: date):
    start = datetime.combine(day, time.min, tzinfo=LAGOS)
    return start, start + timedelta(days=1)


def expected_balance() -> Decimal:
    """Every transfer in, less every refund, payout and fee that has left."""
    received = InboundTransfer.objects.aggregate(total=Sum("amount"))["total"] or Decimal(0)
    sent = sum(
        (Decimal(m.objects.filter(status__in=LEFT_THE_ACCOUNT).aggregate(total=Sum("amount"))["total"] or 0) for m in OUT_MODELS),
        Decimal(0),
    )
    return Decimal(received) - sent


def _ours_out(provider_ref):
    for model in OUT_MODELS:
        obj = model.objects.filter(provider_ref=provider_ref).first()
        if obj:
            return obj
    return None


def reconcile(day: date) -> list:
    """Returns the mismatches as strings (empty when everything agrees)."""
    start, end = day_bounds(day)
    provider = providers.virtual_accounts()
    lines = provider.ledger(start - SLACK, end + SLACK)
    in_day = [line for line in lines if start <= line.at < end]
    credits = {line.payment_ref: line for line in lines if line.direction == "credit" and line.payment_ref}
    debits = {line.transfer_ref: line for line in lines if line.direction == "debit" and line.transfer_ref}
    problems = []

    # In
    for line in in_day:
        if line.direction != "credit":
            continue
        if not line.payment_ref:
            problems.append(f"{line.id}: {line.amount} came in without a payment we can match")
            continue
        ours = InboundTransfer.objects.filter(provider_ref=line.payment_ref).first()
        if ours is None:
            problems.append(f"{line.payment_ref}: in the bank ({line.amount}) but never recorded")
        elif Decimal(line.amount) != ours.amount:
            problems.append(f"{line.payment_ref}: bank says {line.amount} came in, we recorded {ours.amount}")
    for ours in InboundTransfer.objects.filter(received_at__gte=start, received_at__lt=end):
        if ours.provider_ref not in credits:
            problems.append(f"{ours.provider_ref}: recorded ({ours.amount}) but not in the bank")

    # Out
    for line in in_day:
        if line.direction != "debit":
            continue
        if not line.transfer_ref:
            problems.append(f"{line.id}: {line.amount} left without a transfer we can match")
            continue
        ours = _ours_out(line.transfer_ref)
        if ours is None:
            problems.append(f"{line.transfer_ref}: {line.amount} left the account but we never sent it")
        elif Decimal(line.amount) != Decimal(ours.amount):
            problems.append(f"{line.transfer_ref}: bank says {line.amount} left, our {type(ours).__name__} {ours.pk} is {ours.amount}")
    for model in OUT_MODELS:
        for ours in model.objects.filter(status__in=LEFT_THE_ACCOUNT, sent_at__gte=start, sent_at__lt=end).exclude(provider_ref=""):
            if ours.provider_ref not in debits:
                problems.append(f"{ours.provider_ref}: our {model.__name__} {ours.pk} ({ours.amount}) never left the account")

    # Balance
    held, expected = provider.balance(), expected_balance()
    if held != expected:
        problems.append(f"balance: the account holds {held}, our records say {expected} (off by {held - expected})")

    if problems:
        body = "\n".join(problems)
        logger.error("Reconciliation for %s: %s mismatch(es)\n%s", day, len(problems), body)
        mail_admins(f"buysafe reconciliation {day}: {len(problems)} mismatch(es)", body)
    return problems
