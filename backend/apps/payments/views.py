import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.listings.models import Listing
from apps.users.models import PhoneVerification
from apps.users.services.otp import OtpSendError
from apps.users.services.verification import latest_active_verification, send_limit_retry_after, issue_code
from apps.users.views import check_code, otp_send_failed

from . import providers, services
from .banks import BANKS
from .models import PaymentIntent, PayoutAccount
from .serializers import intent_data, payout_account_data

logger = logging.getLogger(__name__)


def error_response(err: services.PaymentError):
    return Response(err.as_dict(), status=err.status)


def _intent_queryset():
    return PaymentIntent.objects.select_related("listing__seller", "offer").prefetch_related(
        "listing__photos", "inbound_transfers__refunds"
    )


class ListingPayView(APIView):
    """POST /api/listings/{id}/pay/ {email?, offer_id?}: start paying. Creates the
    30-minute hold and the transfer details; asking again while the hold lasts
    returns the same ones. The buyer needs an email (Anchor puts one on every
    virtual account): sent here, it's saved to their profile."""

    def post(self, request, pk):
        listing = get_object_or_404(Listing, pk=pk, is_deleted=False)
        offer_id = request.data.get("offer_id")
        if offer_id is not None and not str(offer_id).isdigit():
            return Response({"code": "invalid", "detail": "Invalid offer."}, status=400)
        email = str(request.data.get("email") or "").strip()
        if email:
            try:
                validate_email(email)
            except ValidationError:
                return Response({"code": "invalid_email", "detail": "Enter a valid email address."}, status=400)
            if email != request.user.email:
                request.user.email = email
                request.user.save(update_fields=["email"])
        elif not request.user.email:
            return Response({"code": "email_required", "detail": "Add your email to continue."}, status=400)
        try:
            intent = services.start_payment(listing, request.user, int(offer_id) if offer_id is not None else None)
        except services.PaymentError as err:
            return error_response(err)
        return Response(intent_data(_intent_queryset().get(pk=intent.pk)), status=status.HTTP_201_CREATED)


class PaymentIntentView(APIView):
    """GET /api/payments/{id}/ (the buyer): polled every 5s by the pay screen.
    Expiry is checked here too, so the screen doesn't wait for the sweep."""

    def get(self, request, pk):
        intent = get_object_or_404(PaymentIntent, pk=pk, buyer=request.user)
        if intent.status == PaymentIntent.Status.AWAITING:
            services.expire_holds()
        return Response(intent_data(_intent_queryset().get(pk=intent.pk)))


class PaymentCancelView(APIView):
    """POST /api/payments/{id}/cancel/: release the hold."""

    def post(self, request, pk):
        intent = get_object_or_404(PaymentIntent, pk=pk, buyer=request.user)
        try:
            services.cancel_payment(intent, request.user)
        except services.PaymentError as err:
            return error_response(err)
        return Response(intent_data(_intent_queryset().get(pk=intent.pk)))


class TransferWebhookView(APIView):
    """POST /api/payments/webhooks/anchor/: the provider tells us money
    arrived, or that a refund/payout arrived or failed. Signature first; then stored once
    per provider reference. Events we don't act on get a 200."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        provider = providers.virtual_accounts()
        body = request.body
        if settings.DEBUG:  # dev: see every event's shape (terminal + webhooks.dev.log)
            text = body.decode(errors="replace")
            logger.info("Transfer webhook received: %s", text[:5000])
            with open(settings.BASE_DIR / "webhooks.dev.log", "a") as log:
                log.write(f"{timezone.now().isoformat()} {text}\n")
        if not provider.verify_webhook(request.headers, body):
            logger.warning("Transfer webhook with a bad signature")
            return Response({"detail": "Bad signature."}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            incoming = provider.parse_webhook(body)
        except providers.ProviderError:
            # Couldn't fetch the details: a 5xx makes the provider retry.
            logger.exception("Transfer webhook: provider unreachable")
            return Response({"detail": "Try again."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except (KeyError, ValueError, TypeError):
            logger.exception("Transfer webhook we couldn't read")
            return Response({"detail": "Unreadable."}, status=status.HTTP_400_BAD_REQUEST)
        if incoming is None:
            return Response({"status": "ignored"})
        if isinstance(incoming, providers.TransferFailed):
            services.transfer_failed(incoming)
            return Response({"status": "ok"})
        if isinstance(incoming, providers.TransferSucceeded):
            services.transfer_succeeded(incoming)
            return Response({"status": "ok"})
        inbound, created = services.record_transfer(incoming)
        return Response({"status": "ok", "outcome": inbound.outcome, "duplicate": not created})


class BanksView(APIView):
    """GET /api/payments/banks/: the payout form's bank list."""

    def get(self, request):
        return Response([{"code": code, "name": name} for code, name in BANKS])


class PayoutAccountView(APIView):
    """GET /api/me/payout-account/ -> {account|null, name}.
    PUT {bank_code, account_number, code?}: the name is looked up again and
    must match. Replacing an existing account needs a code sent to the phone:
    without `code` the reply is 409 otp_required and the code is sent."""

    def get(self, request):
        account = PayoutAccount.objects.filter(user=request.user).first()
        user = request.user
        return Response(
            {"account": payout_account_data(account) if account else None, "name": f"{user.first_name} {user.last_name}"}
        )

    def put(self, request):
        user = request.user
        bank_code = str(request.data.get("bank_code", ""))
        account_number = str(request.data.get("account_number", ""))
        code = str(request.data.get("code", "") or "")
        try:
            result = services.look_up_account(user, bank_code, account_number)
        except services.PaymentError as err:
            return error_response(err)
        if not result["matches"]:
            return Response(
                {"code": "name_mismatch", "detail": "This account isn’t in your name.", "account_name": result["account_name"]},
                status=400,
            )

        purpose = PhoneVerification.Purpose.CHANGE_PAYOUT
        verification = None
        if services.is_change(user, bank_code, account_number):
            if not code:
                wait = send_limit_retry_after(user.phone)
                if not wait:
                    try:
                        issue_code(user, purpose)
                    except OtpSendError:
                        return otp_send_failed()
                return Response(
                    {"code": "otp_required", "detail": "Enter the code we sent to your phone.", "resend_available_in": wait},
                    status=409,
                )
            verification = latest_active_verification(user.phone, purpose)
            if verification is not None and verification.user_id != user.pk:
                verification = None
            error = check_code(verification, code)
            if error:
                return error

        with transaction.atomic():
            try:
                account = services.save_payout_account(user, bank_code, account_number)
            except services.PaymentError as err:
                return error_response(err)
            if verification is not None:
                verification.used = True
                verification.save(update_fields=["used"])
        return Response({"account": payout_account_data(account), "name": f"{user.first_name} {user.last_name}"})


class PayoutLookupView(APIView):
    """POST /api/me/payout-account/lookup/ {bank_code, account_number}
    -> {account_name, matches}. Throttled: every call is a bank enquiry."""

    throttle_scope = "payout_lookup"

    def post(self, request):
        try:
            result = services.look_up_account(
                request.user, str(request.data.get("bank_code", "")), str(request.data.get("account_number", ""))
            )
        except services.PaymentError as err:
            return error_response(err)
        return Response(result)
