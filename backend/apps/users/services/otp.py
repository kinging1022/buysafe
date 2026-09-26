"""OTP delivery behind a small interface so the provider can be swapped or faked.

    send_otp(phone) -> pin_id
    verify_otp(pin_id, code) -> bool

The code itself is never stored or logged here; only the provider's pin_id is
kept (in PhoneVerification).
"""

import logging
import uuid

import requests
from django.conf import settings
from django.utils.module_loading import import_string

from ..phone import mask_phone

logger = logging.getLogger(__name__)

OTP_LENGTH = 6
OTP_MESSAGE = "Your buysafe code is < 123456 >. It expires in 10 minutes. Never share it."
OTP_PLACEHOLDER = "< 123456 >"


class OtpSendError(Exception):
    """The provider couldn't send the code (network, auth or provider error)."""


class OtpService:
    def send_otp(self, phone: str) -> str:
        raise NotImplementedError

    def verify_otp(self, pin_id: str, code: str) -> bool:
        raise NotImplementedError


class FakeOtpService(OtpService):
    """For DEBUG and tests: every code is 000000. Sends nothing."""

    CODE = "000000"

    def send_otp(self, phone):
        pin_id = f"fake-{uuid.uuid4()}"
        logger.info("FakeOtpService: OTP 'sent' to %s (pin_id=%s)", mask_phone(phone), pin_id)
        return pin_id

    def verify_otp(self, pin_id, code):
        return code == self.CODE


class TermiiOtpService(OtpService):
    """Termii Token API: POST {BASE_URL}/api/sms/otp/send and /api/sms/otp/verify.
    https://developers.termii.com/send-token, https://developers.termii.com/verify-token
    """

    TIMEOUT = 10  # seconds

    def __init__(self):
        self.api_key = settings.TERMII_API_KEY
        self.base_url = settings.TERMII_BASE_URL.rstrip("/")
        self.sender_id = settings.TERMII_SENDER_ID
        self.channel = settings.TERMII_CHANNEL
        if not (self.api_key and self.base_url and self.sender_id):
            raise OtpSendError("Termii is not configured (TERMII_API_KEY/BASE_URL/SENDER_ID).")

    def _post(self, path, payload):
        # Never log `payload`: it carries the API key (and, on verify, the code).
        try:
            response = requests.post(f"{self.base_url}{path}", json=payload, timeout=self.TIMEOUT)
        except requests.RequestException as exc:
            logger.warning("Termii %s request failed: %s", path, type(exc).__name__)
            raise OtpSendError("Could not reach the SMS provider.") from None
        try:
            data = response.json()
        except ValueError:
            data = {}
        return response.status_code, data

    def send_otp(self, phone):
        status, data = self._post(
            "/api/sms/otp/send",
            {
                "api_key": self.api_key,
                "message_type": "NUMERIC",
                "pin_type": "NUMERIC",
                "to": phone.lstrip("+"),  # international format without "+"
                "from": self.sender_id,
                "channel": self.channel,
                "pin_attempts": settings.OTP_MAX_ATTEMPTS,
                "pin_time_to_live": settings.OTP_TTL_MINUTES,
                "pin_length": OTP_LENGTH,
                "pin_placeholder": OTP_PLACEHOLDER,
                "message_text": OTP_MESSAGE,
            },
        )
        pin_id = data.get("pinId") or data.get("pin_id")
        if status != 200 or not pin_id:
            logger.warning("Termii send failed for %s: HTTP %s", mask_phone(phone), status)
            raise OtpSendError("The SMS provider rejected the request.")
        return pin_id

    def verify_otp(self, pin_id, code):
        status, data = self._post(
            "/api/sms/otp/verify",
            {"api_key": self.api_key, "pin_id": pin_id, "pin": code},
        )
        # Documented success: {"verified": "True", ...}. Failure shapes aren't
        # documented, so anything else counts as not verified.
        return status == 200 and str(data.get("verified")).lower() == "true"


SERVICES = {
    "fake": "apps.users.services.otp.FakeOtpService",
    "termii": "apps.users.services.otp.TermiiOtpService",
}


def get_otp_service() -> OtpService:
    name = settings.OTP_SERVICE
    return import_string(SERVICES.get(name, name))()
