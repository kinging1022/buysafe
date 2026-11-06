"""Automated reminder calls (text read out to the phone).

TODO: confirm the provider's voice API before wiring it. Termii's documented
voice endpoints send OTP codes, not arbitrary messages; don't guess one.
Until then CALL_SERVICE=fake logs the call, and 'termii' raises.
"""

import logging

from django.conf import settings
from django.db import transaction

from apps.users.phone import mask_phone

logger = logging.getLogger(__name__)


class CallError(Exception):
    pass


class FakeCallService:
    placed: list = []

    def call(self, phone, text):
        FakeCallService.placed.append((phone, text))
        logger.info("FakeCallService: call to %s: %s", mask_phone(phone), text)


class TermiiCallService:
    def call(self, phone, text):
        raise CallError("Termii voice calls aren't wired yet: confirm the API first.")


SERVICES = {"fake": FakeCallService, "termii": TermiiCallService}


def place_call(user, text):
    """Best effort, after commit: a failed call is logged, never undoes the step."""
    phone = user.phone

    def go():
        try:
            SERVICES[settings.CALL_SERVICE]().call(phone, text)
        except CallError:
            logger.warning("Call to %s not placed", mask_phone(phone))

    transaction.on_commit(go)
