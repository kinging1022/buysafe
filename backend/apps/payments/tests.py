import json
from datetime import datetime, timedelta
from decimal import Decimal
from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.db import connection
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.deals.models import Deal
from apps.escrow.models import Transaction
from apps.listings import status as listing_status
from apps.listings.testing import make_listing, make_payout_account, make_user
from apps.notifications.clock import LAGOS
from apps.notifications.models import Notification
from apps.offers.models import Offer
from apps.users.models import PhoneVerification

from . import services
from .models import FeeTransfer, InboundTransfer, ListingHold, PaymentIntent, Payout, PayoutAccount, Refund, TransferStatus
from .names import names_match
from .providers import IncomingTransfer, LedgerLine
from .providers.fake import SIGNATURE_HEADER, FakeTransferProvider, FakeVirtualAccountProvider, sign
from . import reconciliation
from .reconciliation import reconcile


def client_for(user=None):
    client = APIClient()
    if user:
        client.force_login(user)
    return client


class BankCodeTests(TestCase):
    """The sender's bank code from the bank name a payment gives us."""

    BANKS = [
        # Names as Anchor's sandbox list writes them (4 Nov 2026).
        ("ACCESS BANK", "000014"),
        ("ACCESS(DIAMOND) BANK", "000005"),
        ("ACCESS MONEY", "100013"),
        ("GTBANK PLC", "000013"),
        ("OPAY", "100004"),
        ("ROLEZ MICROFINANCE BANK", "090405"),
        ("WEMA BANK", "000017"),
        ("WEMA BANK NIGERIA", "000099"),  # made up: two entries that read the same
        ("FIRST BANK OF NIGERIA", "000016"),
        ("FIRST CITY MONUMENT BANK", "000003"),
        ("KUDA MICROFINANCE BANK", "090267"),
        ("STANBIC IBTC BANK PLC", "000012"),
        ("STERLING BANK", "000001"),
        ("STERLING MICROFINANCE BANK", "090999"),
        ("UNITED BANK FOR AFRICA", "000004"),
    ]

    def code(self, name, **extra):
        from .bank_codes import resolve

        return resolve(name, self.BANKS, **extra)

    def test_the_names_payments_really_send(self):
        for sent, code in [
            ("STANBIC IBTC BANK", "000012"),  # sandbox
            ("Access Bank", "000014"),  # not ACCESS(DIAMOND) BANK
            ("Access (Diamond) Bank", "000005"),
            ("Moniepoint MFB", "090405"),  # listed under its old name, Rolez
            ("GUARANTY TRUST BANK", "000013"),
            ("Opay Digital Services", "100004"),
            ("OPay", "100004"),
            ("GTBank Plc", "000013"),
            ("GTB", "000013"),
            ("UBA", "000004"),
            ("United Bank for Africa Plc", "000004"),
            ("First Bank", "000016"),  # not First City Monument Bank
            ("FCMB", "000003"),
            ("Kuda MFB", "090267"),
            ("Kuda", "090267"),
            ("Sterling Bank", "000001"),  # not Sterling MFB
            ("Sterling MFB", "090999"),
        ]:
            self.assertEqual(self.code(sent), code, sent)

    def test_unknown_banks_wait_for_a_person(self):
        for sent in ["Mystery MFB", "", "Bank PLC"]:
            self.assertEqual(self.code(sent), "", sent)

    def test_look_alikes_are_told_apart_by_who_owns_the_account(self):
        # Two entries read as "WEMA": ask each who owns the sender's account.
        holders = {"000017": "NWOSU ADA CHIOMA", "000099": ""}
        lookup = lambda code, account: holders[code]  # noqa: E731
        extra = dict(sender_account="0123450821", sender_name="ADA NWOSU", lookup=lookup)
        self.assertEqual(self.code("Wema Bank", **extra), "000017")
        self.assertEqual(self.code("Wema Bank"), "")  # no way to ask: a person decides
        holders["000099"] = "ADA NWOSU"  # both say yes: still can't be sure
        self.assertEqual(self.code("Wema Bank", **extra), "")

    def test_same_person(self):
        from .bank_codes import same_person

        self.assertTrue(same_person("ADA NWOSU", "NWOSU ADA CHIOMA"))
        self.assertTrue(same_person("Mr. Tolu Adeyemi", "ADEYEMI TOLU"))
        self.assertFalse(same_person("ADA NWOSU", "ADA OKAFOR"))
        self.assertFalse(same_person("ADA NWOSU", ""))


class NameMatchTests(TestCase):
    def test_real_world_orders(self):
        for bank_name in [
            "ADEYEMI TOLU OLUWASEUN",  # surname first, middle name
            "TOLU ADEYEMI",
            "Adeyemi, Tolu O.",
            "MR TOLU ADEYEMI",
            "OLUWASEUN TOLU ADEYEMI",
            "ADÉYEMI TOLU",  # accents
        ]:
            self.assertTrue(names_match("Tolu", "Adeyemi", bank_name), bank_name)

    def test_rejects_other_people_and_partial_names(self):
        for bank_name in [
            "CHUKWU EMEKA PAUL",
            "ADEYEMI OLUWATOLU",  # "Tolu" inside another name isn't Tolu
            "TOLU OKAFOR",
            "ADEYEMI",
            "",
        ]:
            self.assertFalse(names_match("Tolu", "Adeyemi", bank_name), bank_name)

    def test_titles_hyphens_and_apostrophes(self):
        self.assertTrue(names_match("Dr. Ada", "Nwosu", "NWOSU ADA CHIOMA"))
        self.assertTrue(names_match("Ada", "Nwosu-Bello", "ADA NWOSU BELLO"))
        self.assertTrue(names_match("Sean", "O'Neil", "ONEIL SEAN"))
        self.assertFalse(names_match("", "Adeyemi", "ADEYEMI TOLU"))


class PaymentsTestCase(TestCase):
    def setUp(self):
        cache.clear()
        FakeTransferProvider.reset()
        self.seller = make_user("+2348031234567", first_name="Tolu", last_name="Adeyemi")
        self.buyer = make_user("+2348031111111", first_name="Ada", last_name="Nwosu", avatar_color="sky")
        self.other = make_user("+2348032222222", first_name="Kunle", last_name="Okafor")
        self.listing = make_listing(self.seller, title="Samsung fridge, 2 doors", price=185_000, area="Surulere")
        self.payout_account = make_payout_account(self.seller)
        self.as_buyer = client_for(self.buyer)
        self.as_other = client_for(self.other)

    def pay(self, client=None, listing=None, **body):
        body.setdefault("email", "buyer@example.com")
        return (client or self.as_buyer).post(f"/api/listings/{(listing or self.listing).pk}/pay/", body, format="json")

    def transfer(self, intent, amount, ref="REF-1", sender="0123450821", **extra):
        incoming = IncomingTransfer(
            provider_ref=ref,
            account_number=intent.virtual_account_number,
            amount=Decimal(amount),
            sender_name="ADA NWOSU",
            sender_bank="GTBank",
            sender_bank_code="000013",
            sender_account=sender,
            received_at=timezone.now(),
        )
        with self.captureOnCommitCallbacks(execute=True):
            inbound, _ = services.record_transfer(incoming)
        return inbound

    def accepted_offer(self, buyer, amount=175_000, hours=24):
        now = timezone.now()
        return Offer.objects.create(
            listing=self.listing,
            buyer=buyer,
            amount=amount,
            status=Offer.Status.ACCEPTED,
            expires_at=now + timedelta(hours=48),
            decided_at=now,
            price_held_until=now + timedelta(hours=hours),
        )


class StartPaymentTests(PaymentsTestCase):
    def test_creates_hold_intent_and_transfer_details(self):
        res = self.pay()
        self.assertEqual(res.status_code, 201)
        body = res.json()
        self.assertEqual(body["status"], "awaiting")
        self.assertEqual(body["amount"], 185_000)
        self.assertEqual(body["offer"], None)
        self.assertEqual(body["account"]["bank"], "9 Payment Service Bank")
        self.assertEqual(body["account"]["name"], f"buysafe Escrow · Deal {body['id']}")
        self.assertEqual(len(body["account"]["number"]), 10)
        intent = PaymentIntent.objects.get(pk=body["id"])
        self.assertAlmostEqual((intent.expires_at - intent.created_at).total_seconds(), 30 * 60, delta=2)
        self.assertTrue(ListingHold.objects.get(intent=intent).is_active())

    def test_needs_an_email(self):
        res = self.pay(email="")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["code"], "email_required")
        self.assertFalse(PaymentIntent.objects.exists())

    def test_rejects_a_bad_email(self):
        res = self.pay(email="ada@")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["code"], "invalid_email")
        self.assertFalse(PaymentIntent.objects.exists())

    def test_saves_the_email_and_sends_it_to_the_provider(self):
        with mock.patch.object(FakeVirtualAccountProvider, "create", wraps=FakeVirtualAccountProvider().create) as create:
            self.assertEqual(self.pay(email=" ada@example.com ").status_code, 201)
        self.buyer.refresh_from_db()
        self.assertEqual(self.buyer.email, "ada@example.com")
        self.assertEqual(create.call_args.args[3], "ada@example.com")

    def test_a_saved_email_is_enough(self):
        self.buyer.email = "ada@example.com"
        self.buyer.save()
        self.assertEqual(self.pay(email="").status_code, 201)

    def test_idempotent_while_the_hold_lasts(self):
        first = self.pay().json()
        second = self.pay()
        self.assertEqual(second.status_code, 201)
        self.assertEqual(second.json()["id"], first["id"])
        self.assertEqual(PaymentIntent.objects.count(), 1)

    def test_hold_blocks_other_buyers_then_expires(self):
        intent = PaymentIntent.objects.get(pk=self.pay().json()["id"])
        res = self.pay(self.as_other)
        self.assertEqual((res.status_code, res.json()["code"]), (409, "held"))
        viewer = self.as_other.get(f"/api/listings/{self.listing.pk}/").json()["viewer"]
        self.assertEqual((viewer["can_buy"], viewer["buy_reason"]), (False, "held"))
        self.assertEqual((viewer["can_offer"], viewer["offer_reason"]), (False, "held"))
        self.assertIsNotNone(viewer["held_until"])
        mine = self.as_buyer.get(f"/api/listings/{self.listing.pk}/").json()["viewer"]
        self.assertEqual(mine["my_payment"]["id"], intent.pk)

        later = timezone.now() + timedelta(minutes=31)
        with mock.patch("django.utils.timezone.now", return_value=later):
            self.assertEqual(services.expire_holds(), 1)
            intent.refresh_from_db()
            self.assertEqual(intent.status, PaymentIntent.Status.EXPIRED)
            self.assertEqual(intent.hold.end_reason, ListingHold.End.EXPIRED)
            self.assertEqual(self.pay(self.as_other).status_code, 201)

    def test_cancel_releases_the_hold(self):
        intent_id = self.pay().json()["id"]
        res = self.as_buyer.post(f"/api/payments/{intent_id}/cancel/")
        self.assertEqual(res.json()["status"], "cancelled")
        self.assertEqual(self.pay(self.as_other).status_code, 201)
        self.assertEqual(self.as_buyer.post(f"/api/payments/{intent_id}/cancel/").status_code, 409)

    def test_payout_account_required(self):
        PayoutAccount.objects.all().delete()
        res = self.pay()
        self.assertEqual((res.status_code, res.json()["code"]), (409, "no_payout"))
        viewer = self.as_buyer.get(f"/api/listings/{self.listing.pk}/").json()["viewer"]
        self.assertEqual((viewer["can_buy"], viewer["buy_reason"]), (False, "no_payout"))
        owner = client_for(self.seller).get(f"/api/listings/{self.listing.pk}/").json()["owner"]
        self.assertFalse(owner["payout_ready"])

    def test_own_and_not_live_listings(self):
        self.assertEqual(self.pay(client_for(self.seller)).status_code, 403)
        pending = make_listing(self.seller, approval="pending")
        self.assertEqual(self.pay(listing=pending).json()["code"], "not_live")

    def test_accepted_offer_price_while_held(self):
        offer = self.accepted_offer(self.buyer)
        viewer = self.as_buyer.get(f"/api/listings/{self.listing.pk}/").json()["viewer"]
        self.assertEqual(viewer["accepted_offer"]["amount"], 175_000)
        res = self.pay(offer_id=offer.pk)
        self.assertEqual(res.json()["amount"], 175_000)
        self.assertEqual(res.json()["offer"], {"id": offer.pk, "amount": 175_000})

    def test_accepted_offer_price_hold_over_means_full_price(self):
        offer = self.accepted_offer(self.buyer, hours=-1)
        res = self.pay(offer_id=offer.pk)
        self.assertEqual((res.status_code, res.json()["code"]), (409, "offer_not_held"))
        self.assertEqual(self.pay().json()["amount"], 185_000)

    def test_someone_elses_offer_cant_be_used(self):
        offer = self.accepted_offer(self.other)
        self.assertEqual(self.pay(offer_id=offer.pk).json()["code"], "offer_not_held")

    def test_accepted_offer_leaves_the_item_buyable_at_full_price(self):
        self.accepted_offer(self.buyer)
        res = self.pay(self.as_other)
        self.assertEqual((res.status_code, res.json()["amount"]), (201, 185_000))

    def test_intent_is_the_buyers_only(self):
        intent_id = self.pay().json()["id"]
        self.assertEqual(self.as_other.get(f"/api/payments/{intent_id}/").status_code, 404)
        self.assertEqual(self.as_buyer.get(f"/api/payments/{intent_id}/").json()["status"], "awaiting")


class TransferTests(PaymentsTestCase):
    def start(self, client=None, **body):
        return PaymentIntent.objects.get(pk=self.pay(client, **body).json()["id"])

    def test_exact_amount_opens_the_deal(self):
        offerer = make_user("+2348033333333", first_name="Chioma", last_name="Eze")
        other_offer = Offer.objects.create(
            listing=self.listing, buyer=offerer, amount=150_000, expires_at=timezone.now() + timedelta(hours=40)
        )
        intent = self.start()
        inbound = self.transfer(intent, "185000")
        self.assertEqual(inbound.outcome, InboundTransfer.Outcome.ACCEPTED)
        intent.refresh_from_db()
        self.assertEqual(intent.status, PaymentIntent.Status.RECEIVED)

        deal = Deal.objects.get(pk=intent.pk)  # the deal takes the intent's number
        self.assertEqual((deal.amount, deal.fee, deal.payout), (185_000, 18_500, 166_500))
        self.assertEqual(deal.state, Deal.State.AWAITING_VIDEO)
        self.assertEqual(deal.transaction.status, Transaction.Status.HELD)
        self.assertEqual(listing_status.listing_display_status(self.listing), listing_status.IN_ESCROW)
        self.assertEqual(intent.hold.end_reason, ListingHold.End.PAID)
        other_offer.refresh_from_db()
        self.assertEqual(other_offer.status, Offer.Status.CLOSED)
        self.assertTrue(Notification.objects.filter(user=offerer, kind="offer_closed").exists())
        self.assertFalse(Notification.objects.filter(user=self.buyer, kind="offer_closed").exists())
        self.assertTrue(Notification.objects.filter(user=self.seller, kind="payment_held").exists())
        self.assertEqual(Refund.objects.count(), 0)

        body = self.as_buyer.get(f"/api/payments/{intent.pk}/").json()
        self.assertEqual(body["status"], "received")
        self.assertEqual(body["received"]["bank"], "GTBank")
        self.assertEqual(body["received"]["last4"], "0821")
        self.assertEqual(body["deal_id"], deal.pk)

    def test_accepted_offer_amount_freezes_the_fee_on_that_price(self):
        offer = self.accepted_offer(self.buyer)
        intent = self.start(offer_id=offer.pk)
        self.transfer(intent, "175000")
        deal = Deal.objects.get(pk=intent.pk)
        self.assertEqual((deal.amount, deal.fee, deal.payout), (175_000, 17_500, 157_500))
        offer.refresh_from_db()
        self.assertEqual(offer.status, Offer.Status.ACCEPTED)  # the paid one stays accepted

    @override_settings(REFUND_BANK_FEE=50)
    def test_wrong_amount_refunded_minus_the_fee_to_the_source(self):
        intent = self.start()
        inbound = self.transfer(intent, "170000", sender="0555550821")
        self.assertEqual(inbound.outcome, InboundTransfer.Outcome.REFUND_WRONG_AMOUNT)
        refund = inbound.refunds.get()
        self.assertEqual((refund.amount, refund.fee, refund.reason), (Decimal("169950"), Decimal("50"), "wrong_amount"))
        self.assertEqual(refund.status, TransferStatus.SENT)
        sent = FakeTransferProvider.sent[0]
        self.assertEqual((sent["account"], sent["bank_code"], sent["amount"]), ("0555550821", "000013", Decimal("169950")))
        intent.refresh_from_db()
        self.assertEqual(intent.status, PaymentIntent.Status.REFUNDED)
        self.assertEqual(intent.hold.end_reason, ListingHold.End.REFUNDED)
        self.assertFalse(Deal.objects.exists())
        body = self.as_buyer.get(f"/api/payments/{intent.pk}/").json()
        self.assertEqual(body["refund"]["reason"], "wrong_amount")
        self.assertEqual(body["refund"]["received_amount"], "170000.00")
        # The listing is free again.
        self.assertEqual(self.pay(self.as_other).status_code, 201)

    def test_kobo_is_not_the_exact_amount(self):
        intent = self.start()
        self.assertEqual(self.transfer(intent, "185000.50").outcome, InboundTransfer.Outcome.REFUND_WRONG_AMOUNT)

    @override_settings(REFUND_BANK_FEE=50)
    def test_late_payment_refunded_in_full(self):
        intent = self.start()
        with mock.patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(minutes=31)):
            inbound = self.transfer(intent, "185000")
        self.assertEqual(inbound.outcome, InboundTransfer.Outcome.REFUND_LATE)
        refund = inbound.refunds.get()
        self.assertEqual((refund.amount, refund.fee), (Decimal("185000"), Decimal("0")))
        intent.refresh_from_db()
        self.assertEqual(intent.status, PaymentIntent.Status.REFUNDED)
        self.assertFalse(Deal.objects.exists())

    def test_duplicate_webhook_is_stored_once(self):
        intent = self.start()
        self.transfer(intent, "185000", ref="SAME")
        self.transfer(intent, "185000", ref="SAME")
        self.assertEqual(InboundTransfer.objects.count(), 1)
        self.assertEqual(Deal.objects.count(), 1)
        self.assertEqual(Refund.objects.count(), 0)

    def test_paying_twice_refunds_the_second_in_full(self):
        intent = self.start()
        self.transfer(intent, "185000", ref="ONE")
        second = self.transfer(intent, "185000", ref="TWO")
        self.assertEqual(second.outcome, InboundTransfer.Outcome.REFUND_DUPLICATE)
        self.assertEqual(second.refunds.get().amount, Decimal("185000"))
        self.assertEqual(Deal.objects.count(), 1)

    def test_two_buyers_racing_first_to_pay_gets_it(self):
        # Ada's window runs out; Kunle starts his and pays; Ada's transfer then lands.
        ada = self.start()
        with mock.patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(minutes=31)):
            kunle = self.start(self.as_other)
            self.transfer(kunle, "185000", ref="KUNLE", sender="0999990001")
            late = self.transfer(ada, "185000", ref="ADA", sender="0123450821")
        self.assertEqual(late.outcome, InboundTransfer.Outcome.REFUND_LATE)
        self.assertEqual(late.refunds.get().amount, Decimal("185000"))
        self.assertEqual(list(Deal.objects.values_list("buyer_id", flat=True)), [self.other.pk])
        ada.refresh_from_db()
        self.assertEqual(ada.status, PaymentIntent.Status.REFUNDED)

    def test_second_intent_cant_start_while_paid(self):
        intent = self.start()
        self.transfer(intent, "185000")
        self.assertEqual(self.pay(self.as_other).json()["code"], "not_live")

    def test_unknown_account_refunded(self):
        incoming = IncomingTransfer("X1", "9999999999", Decimal("5000"), "A", "GTBank", "000013", "0123450821", timezone.now())
        with self.captureOnCommitCallbacks(execute=True):
            inbound, _ = services.record_transfer(incoming)
        self.assertEqual(inbound.outcome, InboundTransfer.Outcome.REFUND_UNMATCHED)
        self.assertEqual(FakeTransferProvider.sent[0]["account"], "0123450821")

    def test_sender_account_is_encrypted_at_rest(self):
        intent = self.start()
        inbound = self.transfer(intent, "185000", sender="0123450821")
        with connection.cursor() as cursor:
            cursor.execute("SELECT sender_account FROM payments_inboundtransfer WHERE id = %s", [inbound.pk])
            raw = cursor.fetchone()[0]
        self.assertNotIn("0123450821", raw)
        inbound.refresh_from_db()
        self.assertEqual(inbound.sender_account, "0123450821")

    def test_failed_refund_retries_with_backoff(self):
        intent = self.start()
        FakeTransferProvider.fail_next = 1
        refund = self.transfer(intent, "1000").refunds.get()
        self.assertEqual((refund.status, refund.attempts), (TransferStatus.FAILED, 1))
        self.assertEqual(services.retry_transfers(), 0)  # backoff not over
        with mock.patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(minutes=3)):
            self.assertEqual(services.retry_transfers(), 1)
        refund.refresh_from_db()
        self.assertEqual(refund.status, TransferStatus.SENT)
        self.assertEqual(len(FakeTransferProvider.sent), 1)
        self.assertEqual(FakeTransferProvider.sent[0]["account"], "0123450821")


class WebhookTests(PaymentsTestCase):
    def post(self, payload, signature=None):
        body = json.dumps(payload).encode()
        headers = {f"HTTP_{SIGNATURE_HEADER.upper().replace('-', '_')}": signature if signature is not None else sign(body)}
        with self.captureOnCommitCallbacks(execute=True):
            return APIClient().post("/api/payments/webhooks/anchor/", body, content_type="application/json", **headers)

    def payload(self, intent, amount="185000", ref="W1"):
        return {
            "provider_ref": ref,
            "account_number": intent.virtual_account_number,
            "amount": amount,
            "sender_name": "ADA NWOSU",
            "sender_bank": "GTBank",
            "sender_bank_code": "000013",
            "sender_account": "0123450821",
            "received_at": timezone.now().isoformat(),
        }

    def test_signature_is_checked(self):
        intent = PaymentIntent.objects.get(pk=self.pay().json()["id"])
        self.assertEqual(self.post(self.payload(intent), signature="nope").status_code, 401)
        self.assertEqual(self.post(self.payload(intent), signature="").status_code, 401)
        self.assertFalse(InboundTransfer.objects.exists())
        res = self.post(self.payload(intent))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["outcome"], "accepted")
        self.assertTrue(self.post(self.payload(intent)).json()["duplicate"])

    def test_no_session_or_csrf_needed(self):
        intent = PaymentIntent.objects.get(pk=self.pay().json()["id"])
        body = json.dumps(self.payload(intent)).encode()
        client = APIClient(enforce_csrf_checks=True)
        res = client.post(
            "/api/payments/webhooks/anchor/", body, content_type="application/json",
            **{f"HTTP_{SIGNATURE_HEADER.upper().replace('-', '_')}": sign(body)},
        )
        self.assertEqual(res.status_code, 200)


class ReconciliationTests(PaymentsTestCase):
    def setUp(self):
        super().setUp()
        intent = PaymentIntent.objects.get(pk=self.pay().json()["id"])
        self.inbound = self.transfer(intent, "185000", ref="OURS")
        self.day = self.inbound.received_at.astimezone(LAGOS).date()
        self.at = self.inbound.received_at

    def test_agrees_with_our_records(self):
        self.assertEqual(reconcile(self.day), [])

    @override_settings(ADMINS=[("Ops", "ops@example.com")])
    def test_money_in_mismatches(self):
        FakeVirtualAccountProvider.ledger_rows = [
            LedgerLine("l1", "credit", Decimal("180000"), self.at, payment_ref="OURS"),  # wrong amount
            LedgerLine("l2", "credit", Decimal("5000"), self.at, payment_ref="MISSING"),  # never recorded
            LedgerLine("l3", "credit", Decimal("700"), self.at),  # can't be tied to a payment
        ]
        FakeVirtualAccountProvider.balance_now = Decimal("185000")
        problems = reconcile(self.day)
        self.assertEqual(len(problems), 3, problems)
        self.assertIn("bank says 180000 came in, we recorded 185000.00", problems[0])
        self.assertIn("MISSING: in the bank", problems[1])
        self.assertEqual(len(mail.outbox), 1)

    def test_money_out_mismatches(self):
        refund = Refund.objects.create(
            inbound=self.inbound, amount=1000, reason=Refund.Reason.LATE, status=TransferStatus.SUCCESSFUL,
            provider_ref="TR-OURS", sent_at=self.at,
        )
        FakeVirtualAccountProvider.ledger_rows = [
            LedgerLine("l1", "credit", Decimal("185000"), self.at, payment_ref="OURS"),
            LedgerLine("l2", "debit", Decimal("2000"), self.at, transfer_ref="TR-STRANGER"),
        ]
        FakeVirtualAccountProvider.balance_now = Decimal("184000")
        problems = reconcile(self.day)
        self.assertEqual(len(problems), 2, problems)
        self.assertIn("TR-STRANGER: 2000 left the account but we never sent it", problems[0])
        self.assertIn(f"our Refund {refund.pk} (1000.00) never left the account", problems[1])

    def test_balance_must_match(self):
        FakeVirtualAccountProvider.balance_now = Decimal("185500")
        problems = reconcile(self.day)
        self.assertEqual(len(problems), 1, problems)
        self.assertRegex(problems[0], r"^balance: the account holds 185500, our records say 185000(\.00)? \(off by 500(\.00)?\)$")

    def test_a_line_just_after_midnight_still_matches(self):
        # Our record is on the day; the bank's line lands a minute into the next.
        late = reconciliation.day_bounds(self.day)[1] + timedelta(minutes=1)
        FakeVirtualAccountProvider.ledger_rows = [LedgerLine("l1", "credit", Decimal("185000"), late, payment_ref="OURS")]
        FakeVirtualAccountProvider.balance_now = Decimal("185000")
        self.assertEqual(reconcile(self.day), [])


class PayoutAccountTests(PaymentsTestCase):
    def setUp(self):
        super().setUp()
        self.as_seller = client_for(self.seller)
        PayoutAccount.objects.all().delete()

    def put(self, **body):
        return self.as_seller.put("/api/me/payout-account/", body, format="json")

    def test_empty(self):
        self.assertEqual(self.as_seller.get("/api/me/payout-account/").json(), {"account": None, "name": "Tolu Adeyemi"})

    def test_lookup_states(self):
        url = "/api/me/payout-account/lookup/"
        match = self.as_seller.post(url, {"bank_code": "000014", "account_number": "0123456780"}, format="json").json()
        self.assertEqual(match, {"account_name": "ADEYEMI TOLU OLUWASEUN", "matches": True})
        mismatch = self.as_seller.post(url, {"bank_code": "000014", "account_number": "3021884518"}, format="json").json()
        self.assertEqual(mismatch, {"account_name": "CHUKWU EMEKA PAUL", "matches": False})
        error = self.as_seller.post(url, {"bank_code": "000014", "account_number": "0123456789"}, format="json")
        self.assertEqual((error.status_code, error.json()["code"]), (502, "lookup_failed"))
        bad = self.as_seller.post(url, {"bank_code": "000014", "account_number": "123"}, format="json")
        self.assertEqual(bad.json()["code"], "invalid_account")

    def test_save_matching_account(self):
        res = self.put(bank_code="000014", account_number="0123454521")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["account"]["last4"], "4521")
        self.assertEqual(res.json()["account"]["bank_short"], "Access")
        account = PayoutAccount.objects.get(user=self.seller)
        self.assertEqual(account.account_number, "0123454521")
        with connection.cursor() as cursor:
            cursor.execute("SELECT account_number FROM payments_payoutaccount WHERE id = %s", [account.pk])
            self.assertNotIn("0123454521", cursor.fetchone()[0])

    def test_mismatch_blocks_saving(self):
        res = self.put(bank_code="000014", account_number="3021884518")
        self.assertEqual((res.status_code, res.json()["code"]), (400, "name_mismatch"))
        self.assertFalse(PayoutAccount.objects.exists())

    def test_changing_needs_the_phone_code(self):
        self.put(bank_code="000014", account_number="0123454521")
        res = self.put(bank_code="000013", account_number="0111110000")
        self.assertEqual((res.status_code, res.json()["code"]), (409, "otp_required"))
        self.assertTrue(PhoneVerification.objects.filter(user=self.seller, purpose="change_payout").exists())
        self.assertEqual(self.put(bank_code="000013", account_number="0111110000", code="123456").status_code, 400)
        self.assertEqual(PayoutAccount.objects.get(user=self.seller).account_last4, "4521")
        res = self.put(bank_code="000013", account_number="0111110000", code="000000")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(PayoutAccount.objects.get(user=self.seller).account_last4, "0000")
        # Saving the same account again needs no code.
        self.assertEqual(self.put(bank_code="000013", account_number="0111110000").status_code, 200)

    def test_banks_list(self):
        banks = self.as_seller.get("/api/payments/banks/").json()
        self.assertIn({"code": "000014", "name": "Access Bank"}, banks)


class PayoutReleaseTests(PaymentsTestCase):
    def test_release_once_to_the_payout_account(self):
        intent = PaymentIntent.objects.get(pk=self.pay().json()["id"])
        self.transfer(intent, "185000")
        deal = Deal.objects.get(pk=intent.pk)
        with self.captureOnCommitCallbacks(execute=True):
            first = services.release_payout(deal)
            second = services.release_payout(deal)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Payout.objects.count(), 1)
        self.assertEqual(len(FakeTransferProvider.sent), 1)
        sent = FakeTransferProvider.sent[0]
        self.assertEqual((sent["account"], sent["amount"]), ("0123454521", Decimal("166500")))
        deal.refresh_from_db()
        self.assertEqual(deal.released_ref, f"FAKE-payout-deal-{deal.pk}")


class SettlementTests(PaymentsTestCase):
    """Sent isn't settled: a refund or payout is SUCCESSFUL only once the
    provider says it arrived, and our fee moves only after the payout does."""

    def released(self):
        intent = PaymentIntent.objects.get(pk=self.pay().json()["id"])
        self.transfer(intent, "185000")
        deal = Deal.objects.get(pk=intent.pk)
        with self.captureOnCommitCallbacks(execute=True):
            payout = services.release_payout(deal)
        payout.refresh_from_db()
        return deal, payout

    def webhook(self, **payload):
        body = json.dumps(payload).encode()
        with self.captureOnCommitCallbacks(execute=True):
            res = APIClient().post(
                "/api/payments/webhooks/anchor/", body, content_type="application/json",
                **{f"HTTP_{SIGNATURE_HEADER.upper().replace('-', '_')}": sign(body)},
            )
        self.assertEqual(res.status_code, 200, res.content)

    def test_the_fee_waits_for_the_payout_to_arrive(self):
        deal, payout = self.released()
        self.assertEqual(payout.status, TransferStatus.SENT)
        self.assertFalse(FeeTransfer.objects.exists())

        self.webhook(transfer=payout.provider_ref, status="successful")
        payout.refresh_from_db()
        self.assertEqual(payout.status, TransferStatus.SUCCESSFUL)
        self.assertIsNotNone(payout.settled_at)
        self.assertEqual(payout.session_id, "FAKE-SESSION")
        fee = FeeTransfer.objects.get(deal=deal)
        self.assertEqual((fee.status, fee.amount, fee.provider_ref), (TransferStatus.SUCCESSFUL, deal.fee, f"FAKE-fee-deal-{deal.pk}"))
        self.assertEqual(FakeTransferProvider.fees[0]["amount"], Decimal(deal.fee))

        # Told twice: nothing moves again.
        self.webhook(transfer=payout.provider_ref, status="successful")
        self.assertEqual((FeeTransfer.objects.count(), len(FakeTransferProvider.fees)), (1, 1))

    def test_success_that_beats_send_back(self):
        # The event arrives while send() is still talking to the provider:
        # found by our reference, and send() then doesn't move it back to SENT.
        intent = PaymentIntent.objects.get(pk=self.pay().json()["id"])
        self.transfer(intent, "185000")
        deal = Deal.objects.get(pk=intent.pk)
        payout = services.release_payout(deal)  # not committed: still PENDING, no provider ref
        self.webhook(transfer="ANCHOR-ID-1", status="successful", reference=f"FAKE-payout-deal-{deal.pk}")
        payout.refresh_from_db()
        self.assertEqual((payout.status, payout.provider_ref), (TransferStatus.SUCCESSFUL, "ANCHOR-ID-1"))
        payout = services.send_payout(payout.pk)
        self.assertEqual(payout.status, TransferStatus.SUCCESSFUL)

    def test_a_failed_fee_is_retried(self):
        deal, payout = self.released()
        FakeTransferProvider.fail_next = 1
        self.webhook(transfer=payout.provider_ref, status="successful")
        fee = FeeTransfer.objects.get(deal=deal)
        self.assertEqual((fee.status, fee.attempts), (TransferStatus.FAILED, 1))
        services.retry_transfers(now=timezone.now() + timedelta(hours=1))
        fee.refresh_from_db()
        self.assertEqual(fee.status, TransferStatus.SUCCESSFUL)

    def test_a_quiet_transfer_is_looked_up(self):
        # No webhook came: the sweep asks the provider after 10 minutes.
        deal, payout = self.released()
        services.retry_transfers(now=timezone.now() + timedelta(minutes=5))
        payout.refresh_from_db()
        self.assertEqual(payout.status, TransferStatus.SENT)
        with self.captureOnCommitCallbacks(execute=True):
            services.retry_transfers(now=timezone.now() + timedelta(minutes=11))
        payout.refresh_from_db()
        self.assertEqual(payout.status, TransferStatus.SUCCESSFUL)
        self.assertTrue(FeeTransfer.objects.filter(deal=deal, status=TransferStatus.SUCCESSFUL).exists())

    @override_settings(ADMINS=[("Ops", "ops@example.com")])
    def test_failed_after_sending_alerts_staff_and_takes_no_fee(self):
        deal, payout = self.released()
        self.webhook(transfer=payout.provider_ref, status="failed", reason="reversed: BENEFICIARY_BANK_ERROR")
        payout.refresh_from_db()
        self.assertEqual((payout.status, payout.last_error), (TransferStatus.GAVE_UP, "reversed: BENEFICIARY_BANK_ERROR"))
        self.assertFalse(FeeTransfer.objects.exists())
        self.assertEqual(len(mail.outbox), 1)


ANCHOR = dict(
    PAYMENTS_PROVIDER="anchor", ANCHOR_API_KEY="key", ANCHOR_WEBHOOK_SECRET="whsec", ANCHOR_ACCOUNT_ID="acc-1",
    ANCHOR_CUSTOMER_EMAIL="payments@example.com", ANCHOR_COLLECT="paywithtransfer", ANCHOR_REVENUE_ACCOUNT_ID="rev-1",
)


def anchor_response(status, body):
    res = mock.Mock(status_code=status, text=json.dumps(body))
    res.json.return_value = body
    return res


def anchor_sign(body, secret="whsec"):
    import base64
    import hashlib
    import hmac

    return base64.b64encode(hmac.new(secret.encode(), body, hashlib.sha1).hexdigest().encode()).decode()


@override_settings(**ANCHOR)
class AnchorTests(PaymentsTestCase):
    def start(self):
        pwt = {
            "data": {
                "id": "1771-anc_pwt",
                "type": "PayWithTransfer",
                "attributes": {
                    "reference": "1771-anc_va-ref",
                    "amount": 18_500_000,
                    "bank": {"provider": "ninepsb", "name": "9 Payment Service Bank"},
                    "accountName": "buysafe Escrow Deal 1",
                    "accountNumber": "0095000015",
                    "status": "ACTIVE",
                },
            }
        }
        with mock.patch("requests.request", return_value=anchor_response(200, pwt)) as req:
            res = self.pay()
        self.assertEqual(res.status_code, 201, res.content)
        return PaymentIntent.objects.get(pk=res.json()["id"]), req

    def payin_event(self):
        # All Anchor sends: which PayIn. The rest is fetched.
        return {
            "data": {
                "id": "ev-1-anc_py_et",
                "type": "payin.received",
                "attributes": {"createdAt": "2026-02-17T09:18:27.747"},
                "relationships": {"payIn": {"data": {"id": "py-1-anc_py", "type": "PayIn"}}},
            }
        }

    def payin(self, amount_kobo=18_500_000, ref="1771-anc_va-ref", sender_bank="Opay Digital Services"):
        return {
            "data": {
                "id": "py-1-anc_py",
                "type": "PayIn",
                "attributes": {
                    "reference": ref, "amount": amount_kobo, "paidAt": "2026-02-17T09:18:28",
                    "currency": "NGN", "sessionId": "100004260200001800152564915996", "status": "COMPLETED",
                },
            },
            "included": [
                {
                    "id": "ch-1-anc_chrg",
                    "type": "Charge",
                    "attributes": {
                        "transferDetails": {
                            "beneficiaryAccountNumber": "0095000015",
                            "senderBank": sender_bank,
                            "senderAccountNumber": "8169999999",
                            "senderName": "ADA NWOSU",
                        },
                        "chargeStatus": "success",
                    },
                }
            ],
        }

    BANKS = {
        "data": [
            {"id": "b1", "type": "Bank", "attributes": {"nipCode": "100004", "name": "OPAY DIGITAL SERVICES LIMITED (OPAY)"}},
            {"id": "b2", "type": "Bank", "attributes": {"nipCode": "000014", "name": "ACCESS BANK"}},
        ]
    }

    def post(self, payload, signature=None, replies=()):
        body = json.dumps(payload).encode()
        replies = [anchor_response(200, r) if isinstance(r, dict) else r for r in replies]
        with mock.patch("requests.request", side_effect=replies) as req:
            with self.captureOnCommitCallbacks(execute=True):
                res = APIClient().post(
                    "/api/payments/webhooks/anchor/", body, content_type="application/json",
                    HTTP_X_ANCHOR_SIGNATURE=signature if signature is not None else anchor_sign(body),
                )
        self.calls = req.call_args_list
        return res

    def test_creates_a_dynamic_account_in_kobo(self):
        intent, req = self.start()
        sent = req.call_args.kwargs["json"]["data"]["attributes"]
        self.assertEqual(sent["amount"], 18_500_000)
        self.assertEqual(sent["reference"], f"bsdeal{intent.pk}")
        self.assertEqual(sent["customer"]["email"], "buyer@example.com")
        self.assertLessEqual(sent["expiryTime"], 3600)
        self.assertEqual(req.call_args.kwargs["headers"]["x-anchor-key"], "key")
        self.assertEqual(
            (intent.virtual_account_number, intent.virtual_account_bank, intent.virtual_account_ref),
            ("0095000015", "9 Payment Service Bank", "1771-anc_va-ref"),
        )

    def test_anchor_error_means_try_again(self):
        error = {"errors": [{"title": "Bad request", "status": "400", "detail": "bad provider"}]}
        with mock.patch("requests.request", return_value=anchor_response(400, error)):
            res = self.pay()
        self.assertEqual(res.status_code, 503)
        self.assertEqual(res.json()["code"], "provider_unavailable")

    def test_payin_opens_the_deal(self):
        intent, _ = self.start()
        self.assertEqual(self.post(self.payin_event(), signature="nope").status_code, 401)
        res = self.post(self.payin_event(), replies=[self.payin(), self.BANKS])
        self.assertEqual(res.json()["outcome"], "accepted")
        self.assertTrue(self.calls[0].args[1].endswith("/pay/payin/py-1-anc_py?include=Charge"))
        inbound = InboundTransfer.objects.get()
        self.assertEqual((inbound.provider_ref, inbound.amount), ("py-1-anc_py", Decimal("185000")))
        self.assertEqual(inbound.account_number, "0095000015")
        self.assertEqual(
            (inbound.sender_name, inbound.sender_bank_code, inbound.sender_account, inbound.session_id),
            ("ADA NWOSU", "100004", "8169999999", "100004260200001800152564915996"),
        )
        self.assertTrue(Deal.objects.filter(pk=intent.pk).exists())
        # Banks are cached: the repeat only fetches the PayIn.
        self.assertTrue(self.post(self.payin_event(), replies=[self.payin()]).json()["duplicate"])

    def test_wrong_amount_is_refunded_to_the_sender(self):
        self.start()
        refund_replies = [
            anchor_response(404, {"errors": [{"status": "404", "title": "Not found"}]}),
            {"data": {"attributes": {"accountName": "ADA NWOSU"}}},
            {"data": {"id": "cp-2-anc_cp", "type": "CounterParty"}},
            {"data": {"id": "tr-2-anc_trsf", "attributes": {"status": "PENDING"}}},
        ]
        res = self.post(self.payin_event(), replies=[self.payin(amount_kobo=18_000_000), self.BANKS, *refund_replies])
        self.assertEqual(res.json()["outcome"], "refund_wrong_amount")
        refund = Refund.objects.get()
        self.assertEqual((refund.status, refund.provider_ref), (TransferStatus.SENT, "tr-2-anc_trsf"))
        self.assertTrue(self.calls[3].args[1].endswith("/api/v1/payments/verify-account/100004/8169999999"))
        counterparty = self.calls[4].kwargs["json"]["data"]["attributes"]
        self.assertEqual(
            (counterparty["bankCode"], counterparty["accountNumber"], counterparty["accountName"]),
            ("100004", "8169999999", "ADA NWOSU"),
        )
        self.assertEqual(self.calls[5].kwargs["json"]["data"]["attributes"]["amount"], 18_000_000)

    def test_anchor_down_means_retry_later(self):
        self.start()
        res = self.post(self.payin_event(), replies=[anchor_response(500, {"errors": []})])
        self.assertEqual(res.status_code, 503)
        self.assertFalse(InboundTransfer.objects.exists())

    @override_settings(ADMINS=[("Ops", "ops@example.com")])
    def test_unknown_sender_bank_needs_a_person(self):
        self.start()
        res = self.post(self.payin_event(), replies=[self.payin(amount_kobo=18_000_000, sender_bank="Mystery MFB"), self.BANKS])
        self.assertEqual(res.json()["outcome"], "refund_wrong_amount")
        refund = Refund.objects.get()
        self.assertEqual(refund.status, TransferStatus.MANUAL)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(services.retry_transfers(now=timezone.now() + timedelta(hours=1)), 0)

    def test_other_events_are_ignored(self):
        self.start()
        other = {"data": {"id": "e", "type": "account.opened", "attributes": {}}}
        self.assertEqual(self.post(other).json()["status"], "ignored")
        self.assertFalse(InboundTransfer.objects.exists())

    def test_payout_checks_the_reference_then_sends(self):
        intent, _ = self.start()
        self.post(self.payin_event(), replies=[self.payin(), self.BANKS])
        deal = Deal.objects.get(pk=intent.pk)
        replies = [
            anchor_response(404, {"errors": [{"status": "404", "title": "Not found"}]}),
            anchor_response(200, {"data": {"attributes": {"accountName": "ADEYEMI TOLU OLUWASEUN"}}}),
            anchor_response(200, {"data": {"id": "cp-1-anc_cp", "type": "CounterParty"}}),
            anchor_response(200, {"data": {"id": "tr-1-anc_trsf", "attributes": {"status": "PENDING"}}}),
        ]
        with mock.patch("requests.request", side_effect=replies) as req:
            with self.captureOnCommitCallbacks(execute=True):
                payout = services.release_payout(deal)
        payout.refresh_from_db()
        self.assertEqual((payout.status, payout.provider_ref), (TransferStatus.SENT, "tr-1-anc_trsf"))
        lookup, _, _, send = req.call_args_list
        self.assertTrue(lookup.args[1].endswith(f"/api/v1/transfers/by-reference/bspayoutdeal{deal.pk}"))
        attrs = send.kwargs["json"]["data"]
        self.assertEqual(attrs["attributes"]["amount"], 16_650_000)
        self.assertEqual(attrs["relationships"]["account"]["data"]["id"], "acc-1")

        # A retry finds the reference and never sends again.
        payout.status = TransferStatus.FAILED
        payout.save()
        found = anchor_response(200, {"data": {"id": "tr-1-anc_trsf", "attributes": {"status": "PENDING"}}})
        with mock.patch("requests.request", return_value=found) as req:
            services.send_payout(payout.pk)
        self.assertEqual(req.call_count, 1)

    @override_settings(ADMINS=[("Ops", "ops@example.com")])
    def test_failed_transfer_event_alerts_staff(self):
        intent, _ = self.start()
        self.post(self.payin_event(), replies=[self.payin(), self.BANKS])
        deal = Deal.objects.get(pk=intent.pk)
        payout = Payout.objects.create(
            deal=deal, amount=166_500, bank_code="000014", bank_name="Access Bank", account_number="0123454521",
            account_last4="4521", account_name="TOLU ADEYEMI", idempotency_key="k", status=TransferStatus.SENT,
            provider_ref="tr-9-anc_trsf",
        )
        event = {
            "data": {
                "id": "e2", "type": "nip.transfer.failed", "attributes": {},
                "relationships": {"transfer": {"data": {"id": "tr-9-anc_trsf", "type": "NIP_TRANSFER"}}},
            }
        }
        failed = {"data": {"id": "tr-9-anc_trsf", "attributes": {"status": "FAILED", "reference": "bspayoutdeal1"}}}
        self.assertEqual(self.post(event, replies=[failed]).status_code, 200)
        self.assertTrue(self.calls[0].args[1].endswith("/api/v1/transfers/tr-9-anc_trsf"))
        payout.refresh_from_db()
        self.assertEqual(payout.status, TransferStatus.GAVE_UP)
        self.assertEqual(len(mail.outbox), 1)

    def test_events_come_without_a_data_wrapper(self):
        # The shape Anchor really sends (sandbox, 2026-10-18).
        intent, _ = self.start()
        self.post(self.payin_event(), replies=[self.payin(), self.BANKS])
        payout = Payout.objects.create(
            deal=Deal.objects.get(pk=intent.pk), amount=166_500, bank_code="000014", bank_name="Access Bank",
            account_number="0123454521", account_last4="4521", account_name="TOLU ADEYEMI", idempotency_key="k",
            status=TransferStatus.SENT, provider_ref="tr-9-anc_trsf",
        )
        event = {
            "id": "e3-anc_et_ts", "type": "nip.transfer.failed",
            "attributes": {"createdAt": "2026-10-18T18:51:53.870903731", "failureReason": "TRANSFER_LIMIT_EXCEEDED"},
            "relationships": {"transfer": {"data": {"id": "tr-9-anc_trsf", "type": "NIP_TRANSFER"}}},
        }
        failed = {"data": {"id": "tr-9-anc_trsf", "attributes": {"status": "FAILED", "failureReason": "TRANSFER_LIMIT_EXCEEDED"}}}
        self.assertEqual(self.post(event, replies=[failed]).status_code, 200)
        payout.refresh_from_db()
        self.assertEqual(payout.status, TransferStatus.GAVE_UP)
        self.assertEqual(payout.last_error, "failed: TRANSFER_LIMIT_EXCEEDED")

    def test_a_refused_transfer_is_not_sent(self):
        refused = {"data": {"id": "tr-3-anc_trsf", "attributes": {"status": "FAILED", "failureReason": "TRANSFER_LIMIT_EXCEEDED"}}}
        replies = [
            anchor_response(404, {"errors": [{"status": "404", "title": "Not found"}]}),
            anchor_response(200, {"data": {"attributes": {"accountName": "TOLU ADEYEMI"}}}),
            anchor_response(200, {"data": {"id": "cp-3-anc_cp", "type": "CounterParty"}}),
            anchor_response(201, refused),
        ]
        from .providers import ProviderError, transfers

        with mock.patch("requests.request", side_effect=replies):
            with self.assertRaisesRegex(ProviderError, "TRANSFER_LIMIT_EXCEEDED"):
                transfers().send("000014", "0123454521", Decimal("100"), "test", "key-3")


    def test_payout_arrived_then_the_fee_moves(self):
        intent, _ = self.start()
        self.post(self.payin_event(), replies=[self.payin(), self.BANKS])
        deal = Deal.objects.get(pk=intent.pk)
        payout = Payout.objects.create(
            deal=deal, amount=deal.payout, bank_code="000014", bank_name="Access Bank", account_number="0123454521",
            account_last4="4521", account_name="TOLU ADEYEMI", idempotency_key=f"payout-deal-{deal.pk}",
            status=TransferStatus.SENT, provider_ref="tr-1-anc_trsf", sent_at=timezone.now(),
        )
        event = {
            "id": "e4-anc_et_ts", "type": "nip.transfer.successful", "attributes": {"sessionId": "1232323232323232323"},
            "relationships": {"transfer": {"data": {"id": "tr-1-anc_trsf", "type": "NIP_TRANSFER"}}},
        }
        completed = {"data": {"id": "tr-1-anc_trsf", "attributes": {
            "status": "COMPLETED", "reference": f"bspayoutdeal{deal.pk}", "sessionId": "1232323232323232323"}}}
        fee_replies = [
            anchor_response(404, {"errors": [{"status": "404", "title": "Not found"}]}),
            {"data": {"id": "tr-2-anc_trsf", "type": "BOOK_TRANSFER", "attributes": {"status": "COMPLETED"}}},
        ]
        self.assertEqual(self.post(event, replies=[completed, *fee_replies]).status_code, 200)
        payout.refresh_from_db()
        self.assertEqual((payout.status, payout.session_id), (TransferStatus.SUCCESSFUL, "1232323232323232323"))
        book = self.calls[2].kwargs["json"]["data"]
        self.assertEqual(book["type"], "BookTransfer")
        self.assertEqual(book["attributes"]["amount"], deal.fee * 100)
        self.assertEqual(book["attributes"]["reference"], f"bsfeedeal{deal.pk}")
        self.assertEqual(book["relationships"]["destinationAccount"]["data"]["id"], "rev-1")
        fee = FeeTransfer.objects.get(deal=deal)
        self.assertEqual((fee.status, fee.provider_ref), (TransferStatus.SUCCESSFUL, "tr-2-anc_trsf"))

    def test_ledger_and_balance(self):
        from .providers.anchor import AnchorVirtualAccountProvider

        def row(i, kind, direction, kobo, related):
            return {"id": f"t{i}-anc_txn", "attributes": {"transactionType": kind, "direction": direction, "amount": kobo,
                    "createdAt": "2026-10-19T12:21:16"}, "relationships": related}

        page0 = {"data": [row(1, "Settlement", "Credit", 17_500_000, {"payment": {"data": {"id": "pay-1-anc_py"}}})],
                 "meta": {"pagination": {"totalPages": 2}}}
        page1 = {"data": [row(2, "NIPTransfer", "Debit", 250_000, {"transfer": {"data": {"id": "tr-1-anc_trsf"}}}),
                          {**row(3, "Settlement", "Credit", 1, {}), "attributes": {"direction": "Credit", "amount": 1,
                           "createdAt": "2026-10-21T00:00:00"}}],
                 "meta": {"pagination": {"totalPages": 2}}}
        start = datetime(2026, 10, 19, tzinfo=LAGOS)
        with mock.patch("requests.request", side_effect=[anchor_response(200, page0), anchor_response(200, page1)]) as req:
            lines = AnchorVirtualAccountProvider().ledger(start, start + timedelta(days=1))
        self.assertIn("accountId=acc-1&from=2026-10-18&to=2026-10-19", req.call_args_list[0].args[1])
        self.assertEqual(
            [(l.direction, l.amount, l.payment_ref, l.transfer_ref) for l in lines],
            [("credit", Decimal("175000"), "pay-1-anc_py", ""), ("debit", Decimal("2500"), "", "tr-1-anc_trsf")],
        )
        balance = {"data": {"availableBalance": 1, "ledgerBalance": 212129950, "hold": 0, "pending": 0}}
        with mock.patch("requests.request", return_value=anchor_response(200, balance)):
            self.assertEqual(AnchorVirtualAccountProvider().balance(), Decimal("2121299.50"))


NUBAN_SANDBOX = dict(ANCHOR, ANCHOR_COLLECT="nuban", ANCHOR_BASE_URL="https://api.sandbox.getanchor.co")


@override_settings(**NUBAN_SANDBOX)
class AnchorSandboxTests(PaymentsTestCase):
    """ANCHOR_COLLECT=nuban: a virtual NUBAN per deal, paid via the settlement
    credit Anchor reports as transaction.created. Payloads as the sandbox sent
    them (2026-10-18)."""

    NUBAN = "179234180328027-anc_acc_num"

    def start(self):
        nuban = {
            "data": {
                "id": self.NUBAN, "type": "VirtualNuban",
                "attributes": {
                    "accountNumber": "4046023956", "accountName": "buysafe Escrow Deal 1", "status": "ACTIVE",
                    "bank": {"id": "b-anc_bk", "name": "PROVIDUS BANK", "nipCode": "000023"}, "permanent": True,
                },
            }
        }
        with mock.patch("requests.request", return_value=anchor_response(201, nuban)) as req:
            res = self.pay()
        self.assertEqual(res.status_code, 201, res.content)
        return PaymentIntent.objects.get(pk=res.json()["id"]), req

    def event(self, txn="txn-1-anc_txn"):
        return {
            "id": "e1-anc_et_ts", "type": "transaction.created", "attributes": {"createdAt": "2026-10-18T18:52:15.75"},
            "relationships": {
                "account": {"data": {"id": "acc-1", "type": "DepositAccount"}},
                "transaction": {"data": {"id": txn, "type": "NIPTransaction"}},
            },
        }

    def settlement(self, kind="Settlement", direction="Credit"):
        return {
            "data": {
                "id": "txn-1-anc_txn", "type": "NIPTransaction",
                "attributes": {"transactionType": kind, "direction": direction, "amount": 18_500_000},
                "relationships": {"payment": {"data": {"id": "pay-1-anc_py", "type": "Payment"}}},
            }
        }

    def payment(self, kobo=18_500_000, nuban=None):
        return {
            "data": {
                "id": "pay-1-anc_py", "type": "Payment",
                "attributes": {
                    "amount": kobo, "paidAt": "2026-10-18T16:43:36", "type": "BankTransfer",
                    "counterParty": {"accountNumber": "0123450821", "accountName": "ADA NWOSU", "bank": {"name": "STANBIC IBTC BANK"}},
                },
                "relationships": {"virtualNuban": {"data": {"id": nuban or self.NUBAN, "type": "VirtualNuban"}}},
            }
        }

    BANKS = {"data": [{"id": "b3", "type": "Bank", "attributes": {"nipCode": "000012", "name": "STANBIC IBTC BANK PLC"}}]}

    post = AnchorTests.post

    def test_each_deal_gets_a_nuban_on_the_deposit_account(self):
        intent, req = self.start()
        self.assertTrue(req.call_args.args[1].endswith("/api/v1/virtual-nubans"))
        sent = req.call_args.kwargs["json"]["data"]
        self.assertEqual(sent["relationships"]["settlementAccount"]["data"]["id"], "acc-1")
        self.assertEqual(sent["attributes"]["virtualAccountDetail"]["email"], "buyer@example.com")
        self.assertEqual(
            (intent.virtual_account_number, intent.virtual_account_bank, intent.virtual_account_ref),
            ("4046023956", "PROVIDUS BANK", self.NUBAN),
        )

    @override_settings(ANCHOR_BASE_URL="https://api.getanchor.co")
    def test_never_against_production(self):
        with mock.patch("requests.request") as req:
            self.assertEqual(self.pay().status_code, 503)
        req.assert_not_called()

    def test_settlement_credit_opens_the_deal(self):
        intent, _ = self.start()
        res = self.post(self.event(), replies=[self.settlement(), self.payment(), self.BANKS])
        self.assertEqual(res.json()["outcome"], "accepted", res.content)
        self.assertTrue(self.calls[0].args[1].endswith("/api/v1/transactions/txn-1-anc_txn"))
        self.assertTrue(self.calls[1].args[1].endswith("/api/v1/payments/pay-1-anc_py"))
        inbound = InboundTransfer.objects.get()
        self.assertEqual((inbound.provider_ref, inbound.amount, inbound.account_number), ("pay-1-anc_py", Decimal("185000"), "4046023956"))
        self.assertEqual((inbound.sender_name, inbound.sender_bank_code, inbound.sender_account), ("ADA NWOSU", "000012", "0123450821"))
        self.assertTrue(Deal.objects.filter(pk=intent.pk).exists())
        # Delivered again (AtLeastOnce): stored once.
        self.assertTrue(self.post(self.event(), replies=[self.settlement(), self.payment()]).json()["duplicate"])

    def test_our_own_debits_are_ignored(self):
        self.start()
        res = self.post(self.event(), replies=[self.settlement(kind="NIPTransfer", direction="Debit")])
        self.assertEqual(res.json()["status"], "ignored")
        self.assertFalse(InboundTransfer.objects.exists())

    def test_wrong_amount_into_a_nuban_is_refunded(self):
        self.start()
        refund = [
            anchor_response(404, {"errors": [{"status": "404", "title": "Not found"}]}),
            {"data": {"attributes": {"accountName": "ADA NWOSU"}}},
            {"data": {"id": "cp-1-anc_cp", "type": "CounterParty"}},
            {"data": {"id": "tr-1-anc_trsf", "attributes": {"status": "PENDING"}}},
        ]
        res = self.post(self.event(), replies=[self.settlement(), self.payment(kobo=17_000_000), self.BANKS, *refund])
        self.assertEqual(res.json()["outcome"], "refund_wrong_amount")
        self.assertEqual(Refund.objects.get().status, TransferStatus.SENT)
