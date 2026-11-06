"""Pretend a bank transfer arrived (the fake provider's signed webhook).

    manage.py fake_transfer 9900000317 175000
    manage.py fake_transfer 9900000317 170000 --bank GTBank --from 0123450821
"""

import json
import uuid

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.test import Client
from django.utils import timezone

from apps.payments.providers.fake import SIGNATURE_HEADER, sign


class Command(BaseCommand):
    help = "Send a signed fake transfer webhook (PAYMENTS_PROVIDER=fake only)."

    def add_arguments(self, parser):
        parser.add_argument("account_number")
        parser.add_argument("amount")
        parser.add_argument("--bank", default="GTBank")
        parser.add_argument("--bank-code", default="000013")
        parser.add_argument("--from", dest="sender", default="0123450821")
        parser.add_argument("--name", default="ADA NWOSU")
        parser.add_argument("--ref", default="")

    def handle(self, *args, **opts):
        if settings.PAYMENTS_PROVIDER != "fake":
            raise CommandError("Only for the fake provider.")
        body = json.dumps(
            {
                "provider_ref": opts["ref"] or f"FAKE-IN-{uuid.uuid4().hex[:12]}",
                "account_number": opts["account_number"],
                "amount": opts["amount"],
                "sender_name": opts["name"],
                "sender_bank": opts["bank"],
                "sender_bank_code": opts["bank_code"],
                "sender_account": opts["sender"],
                "received_at": timezone.now().isoformat(),
            }
        ).encode()
        client = Client(**{f"HTTP_{SIGNATURE_HEADER.upper().replace('-', '_')}": sign(body)})
        res = client.post("/api/payments/webhooks/anchor/", body, content_type="application/json", SERVER_NAME="localhost")
        self.stdout.write(f"{res.status_code} {res.content.decode()}")
