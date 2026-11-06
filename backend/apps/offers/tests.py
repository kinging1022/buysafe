from datetime import timedelta
from unittest import mock

from django.core.cache import cache
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.escrow.models import Transaction
from apps.listings.models import Listing, ListingView
from apps.listings.testing import make_listing, make_payout_account, make_tx, make_user
from apps.notifications.kinds import render
from apps.notifications.models import Notification

from . import rules
from .models import Offer
from .services import expire_offers

SEND_SMS = "apps.users.services.otp.FakeOtpService.send_sms"
Status = Offer.Status


def client_for(user=None):
    client = APIClient()
    if user:
        client.force_login(user)
    return client


class OfferTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.seller = make_user("+2348031234567", first_name="Tolu", last_name="Adeyemi")
        self.buyer = make_user("+2348031111111", first_name="Ada", last_name="Nwosu", avatar_color="sky")
        self.other = make_user("+2348032222222", first_name="Kunle", last_name="Okafor", avatar_color="lime")
        self.listing = make_listing(self.seller, title="Samsung fridge, 2 doors", price=185_000)
        make_payout_account(self.seller)
        self.as_seller = client_for(self.seller)
        self.as_buyer = client_for(self.buyer)
        self.as_other = client_for(self.other)

    def offer(self, client=None, amount=165_000, note="", listing=None):
        listing = listing or self.listing
        return (client or self.as_buyer).post(
            f"/api/listings/{listing.pk}/offers/", {"amount": amount, "note": note}, format="json"
        )

    def make_offer(self, buyer, amount, **extra):
        extra.setdefault("expires_at", timezone.now() + rules.offer_ttl())
        return Offer.objects.create(listing=self.listing, buyer=buyer, amount=amount, **extra)


class RulesTests(TestCase):
    def test_min_offer_rounds_60_percent_up_to_1000(self):
        self.assertEqual(rules.min_offer(185_000), 111_000)
        self.assertEqual(rules.min_offer(100_000), 60_000)  # exact, no rounding
        self.assertEqual(rules.min_offer(100_001), 61_000)
        self.assertEqual(rules.min_offer(2_000), 2_000)


class CreateOfferTests(OfferTestCase):
    def test_creates_pending_offer_and_texts_the_seller(self):
        with mock.patch(SEND_SMS) as send, self.captureOnCommitCallbacks(execute=True):
            res = self.offer(amount=165_000, note="  Can pick up Saturday.  ")
        self.assertEqual(res.status_code, 201, res.json())
        body = res.json()
        self.assertEqual((body["amount"], body["status"]), (165_000, "pending"))
        offer = Offer.objects.get()
        self.assertEqual((offer.buyer, offer.note), (self.buyer, "Can pick up Saturday."))
        self.assertAlmostEqual(offer.expires_at - offer.created_at, timedelta(hours=48), delta=timedelta(seconds=5))
        send.assert_called_once_with(self.seller.phone, "New offer ₦165,000 on Samsung fridge, 2 doors")
        notice = Notification.objects.get(user=self.seller, kind="offer_new")
        self.assertEqual(render(notice)["title_text"], "Ada N. offered ₦165,000 for your Samsung fridge.")
        self.assertEqual(render(notice)["target_url"], f"/listings/{self.listing.pk}")

    def test_60_percent_floor(self):
        res = self.offer(amount=110_999)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["code"], "below_minimum")
        self.assertEqual(res.json()["min_amount"], 111_000)
        self.assertEqual(res.json()["detail"], "Offers must be at least ₦111,000 (60% of the asking price).")
        self.assertEqual(self.offer(amount=111_000).status_code, 201)

    def test_must_be_below_the_price(self):
        for amount in (185_000, 200_000):
            res = self.offer(amount=amount)
            self.assertEqual(res.status_code, 400)
            self.assertEqual(res.json()["code"], "not_below_price")
        self.assertEqual(self.offer(amount=184_999).status_code, 201)

    def test_whole_naira_only(self):
        for amount in ("165,000", 165000.5, "165000.5", "", None, -5):
            self.assertEqual(self.offer(amount=amount).status_code, 400, amount)
        self.assertEqual(self.offer(amount="165000").status_code, 201)

    def test_note_max_280(self):
        self.assertEqual(self.offer(note="x" * 281).status_code, 400)
        self.assertEqual(self.offer(note="x" * 280).status_code, 201)

    def test_not_on_your_own_listing(self):
        res = self.offer(client=self.as_seller)
        self.assertEqual((res.status_code, res.json()["code"]), (403, "own_listing"))

    def test_only_live_listings(self):
        pending = make_listing(self.seller, approval=Listing.Approval.PENDING)
        self.assertEqual(self.offer(listing=pending).json()["code"], "not_live")
        escrow = make_listing(self.seller)
        make_tx(escrow, self.other, Transaction.Status.HELD)
        res = self.offer(listing=escrow)
        self.assertEqual((res.status_code, res.json()["code"]), (409, "not_live"))
        deleted = make_listing(self.seller, is_deleted=True)
        self.assertEqual(self.offer(listing=deleted).status_code, 404)

    def test_signed_out_and_unverified_cannot_offer(self):
        self.assertEqual(self.offer(client=client_for()).status_code, 403)
        unverified = make_user("+2348036666666")
        unverified.phone_verified = False
        unverified.save()
        self.assertEqual(self.offer(client=client_for(unverified)).status_code, 403)

    def test_one_open_offer_per_buyer(self):
        self.assertEqual(self.offer().status_code, 201)
        res = self.offer(amount=170_000)
        self.assertEqual((res.status_code, res.json()["code"]), (409, "offer_open"))
        # Another buyer can still offer.
        self.assertEqual(self.offer(client=self.as_other).status_code, 201)

    def test_one_open_offer_is_a_db_constraint(self):
        self.make_offer(self.buyer, 150_000)
        with self.assertRaises(IntegrityError):
            self.make_offer(self.buyer, 160_000)

    def test_can_offer_again_after_withdrawing_or_expiry(self):
        first = self.make_offer(self.buyer, 150_000)
        self.as_buyer.post(f"/api/offers/{first.pk}/withdraw/")
        self.assertEqual(self.offer(amount=160_000).status_code, 201)
        # Past its expiry but not yet swept: still lets the buyer offer again.
        Offer.objects.filter(status=Status.PENDING).update(expires_at=timezone.now() - timedelta(minutes=1))
        self.assertEqual(self.offer(amount=170_000).status_code, 201)
        self.assertEqual(
            sorted(Offer.objects.values_list("status", flat=True)), ["expired", "pending", "withdrawn"]
        )


class WithdrawTests(OfferTestCase):
    def test_buyer_withdraws_pending(self):
        offer = self.make_offer(self.buyer, 165_000)
        res = self.as_buyer.post(f"/api/offers/{offer.pk}/withdraw/")
        self.assertEqual(res.status_code, 200)
        offer.refresh_from_db()
        self.assertEqual(offer.status, Status.WITHDRAWN)
        self.assertIsNotNone(offer.decided_at)

    def test_only_that_buyer(self):
        offer = self.make_offer(self.buyer, 165_000)
        self.assertEqual(self.as_other.post(f"/api/offers/{offer.pk}/withdraw/").status_code, 404)
        self.assertEqual(self.as_seller.post(f"/api/offers/{offer.pk}/withdraw/").status_code, 404)

    def test_illegal_transitions_are_409(self):
        withdrawn = self.make_offer(self.buyer, 165_000, status=Status.WITHDRAWN)
        res = self.as_buyer.post(f"/api/offers/{withdrawn.pk}/withdraw/")
        self.assertEqual((res.status_code, res.json()["code"]), (409, "not_pending"))
        expired = self.make_offer(self.buyer, 160_000, status=Status.EXPIRED)
        self.assertEqual(self.as_buyer.post(f"/api/offers/{expired.pk}/withdraw/").status_code, 409)
        # Past its expiry, not yet swept.
        stale = self.make_offer(self.buyer, 170_000, expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.as_buyer.post(f"/api/offers/{stale.pk}/withdraw/").status_code, 409)


class ExpiryTests(OfferTestCase):
    def test_sweep_expires_due_offers_and_texts_the_buyer(self):
        due = self.make_offer(self.buyer, 165_000, expires_at=timezone.now() - timedelta(seconds=1))
        fresh = self.make_offer(self.other, 150_000)
        with mock.patch(SEND_SMS) as send, self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(expire_offers(), 1)
        due.refresh_from_db()
        fresh.refresh_from_db()
        self.assertEqual((due.status, fresh.status), (Status.EXPIRED, Status.PENDING))
        self.assertIsNotNone(due.decided_at)
        send.assert_called_once_with(
            self.buyer.phone, "Your offer ₦165,000 on Samsung fridge, 2 doors expired without a reply."
        )
        # Running again does nothing.
        self.assertEqual(expire_offers(), 0)


class OwnerOffersListTests(OfferTestCase):
    def test_owner_only(self):
        self.assertEqual(self.as_buyer.get(f"/api/listings/{self.listing.pk}/offers/").status_code, 404)
        self.assertEqual(client_for().get(f"/api/listings/{self.listing.pk}/offers/").status_code, 403)

    def test_open_highest_first_then_closed_with_quotes(self):
        now = timezone.now()
        chioma = make_user("+2348033333333", first_name="Chioma", last_name="Eze", avatar_color="coral")
        self.make_offer(chioma, 140_000)
        self.make_offer(self.buyer, 175_000, note="Can pick up Saturday.")
        self.make_offer(self.other, 165_000)
        dan = make_user("+2348034444444", first_name="Dan", last_name="Obi")
        self.make_offer(dan, 180_000, status=Status.WITHDRAWN, decided_at=now - timedelta(days=1))
        old = make_user("+2348035555555", first_name="Old", last_name="Offer")
        self.make_offer(old, 180_000, status=Status.EXPIRED, decided_at=now - timedelta(days=8))

        body = self.as_seller.get(f"/api/listings/{self.listing.pk}/offers/").json()
        self.assertEqual((body["count"], body["best"]), (3, 175_000))
        self.assertEqual(
            [(o["amount"], o["status"]) for o in body["results"]],
            [(175_000, "pending"), (165_000, "pending"), (140_000, "pending"), (180_000, "withdrawn")],
        )
        top = body["results"][0]
        self.assertEqual(top["quote"], {"payout": 157_500, "rate_label": "10%"})
        self.assertEqual(
            top["buyer"], {"first_name": "Ada", "last_initial": "N", "avatar_color": "sky", "verified": True}
        )
        self.assertEqual(top["note"], "Can pick up Saturday.")
        self.assertNotIn("+234", str(body))

    def test_no_offers(self):
        body = self.as_seller.get(f"/api/listings/{self.listing.pk}/offers/").json()
        self.assertEqual(body, {"count": 0, "best": None, "results": []})


class ListingDetailTests(OfferTestCase):
    def detail(self, client, listing=None):
        return client.get(f"/api/listings/{(listing or self.listing).pk}/")

    def test_public_fields(self):
        make_tx(make_listing(self.seller), self.other, Transaction.Status.COMPLETED)
        body = self.detail(client_for()).json()
        self.assertEqual(body["title"], "Samsung fridge, 2 doors")
        self.assertEqual(body["display_status"], "live")
        self.assertEqual(body["category"], {"slug": "home-appliances", "label": "Home appliances"})
        self.assertEqual(
            body["offer_rules"],
            {
                "min_amount": 111_000,
                "min_percent": 60,
                "max_amount": 184_999,
                "last_declined_amount": None,
                "max_offers": 3,
            },
        )
        self.assertEqual(body["seller"]["first_name"], "Tolu")
        self.assertEqual(body["seller"]["last_initial"], "A")
        self.assertEqual(body["seller"]["sold_count"], 1)
        self.assertNotIn("owner", body)

    def test_viewer_signed_out(self):
        viewer = self.detail(client_for()).json()["viewer"]
        self.assertEqual(
            viewer,
            {
                "is_owner": False,
                "my_open_offer": None,
                "declined_amount": None,
                "accepted_offer": None,
                "can_offer": True,
                "offer_reason": None,
                "can_buy": True,
                "buy_reason": None,
                "held_until": None,
                "my_payment": None,
            },
        )

    def test_viewer_owner(self):
        body = self.detail(self.as_seller).json()
        self.assertTrue(body["viewer"]["is_owner"])
        self.assertEqual((body["viewer"]["can_offer"], body["viewer"]["offer_reason"]), (False, "own_listing"))
        self.assertEqual((body["viewer"]["can_buy"], body["viewer"]["buy_reason"]), (False, "own_listing"))
        self.assertEqual(body["owner"]["fee"]["payout"], 166_500)
        self.assertEqual(body["owner"]["category"], "home-appliances")
        self.assertIn("view_count", body["owner"])

    def test_viewer_buyer_with_open_offer_and_other_buyer(self):
        offer = self.make_offer(self.buyer, 165_000)
        mine = self.detail(self.as_buyer).json()["viewer"]
        self.assertEqual(mine["my_open_offer"]["id"], offer.pk)
        self.assertEqual(mine["my_open_offer"]["amount"], 165_000)
        self.assertEqual((mine["can_offer"], mine["offer_reason"], mine["can_buy"]), (False, "offer_open", True))
        theirs = self.detail(self.as_other).json()["viewer"]
        self.assertIsNone(theirs["my_open_offer"])
        self.assertTrue(theirs["can_offer"])

    def test_not_live_listing(self):
        escrow = make_listing(self.seller)
        make_tx(escrow, self.other, Transaction.Status.HELD)
        viewer = self.detail(self.as_buyer, escrow).json()["viewer"]
        self.assertEqual((viewer["can_offer"], viewer["offer_reason"]), (False, "not_live"))
        self.assertEqual((viewer["can_buy"], viewer["buy_reason"]), (False, "not_live"))

    def test_pending_and_rejected_are_owner_only(self):
        for approval in (Listing.Approval.PENDING, Listing.Approval.REJECTED):
            listing = make_listing(self.seller, approval=approval)
            self.assertEqual(self.detail(self.as_buyer, listing).status_code, 404)
            self.assertEqual(self.detail(client_for(), listing).status_code, 404)
            self.assertEqual(self.detail(self.as_seller, listing).status_code, 200)

    def test_views_counted_once_per_person_per_day_not_the_owner(self):
        self.detail(self.as_buyer)
        self.detail(self.as_buyer)
        self.detail(self.as_other)
        self.detail(client_for())
        self.detail(client_for())  # same IP (test client), counted once
        self.detail(self.as_seller)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.view_count, 3)
        self.assertEqual(ListingView.objects.count(), 3)
        self.assertEqual(self.detail(self.as_seller).json()["owner"]["view_count"], 3)

    def test_phone_never_in_any_response(self):
        self.make_offer(self.buyer, 165_000)
        responses = [
            self.detail(client_for()),
            self.detail(self.as_buyer),
            self.detail(self.as_seller),
            self.as_seller.get(f"/api/listings/{self.listing.pk}/offers/"),
            self.offer(client=self.as_other),
        ]
        for res in responses:
            for user in (self.seller, self.buyer, self.other):
                self.assertNotIn(user.phone, res.content.decode())
                self.assertNotIn(user.phone[4:], res.content.decode())


class DeclineTests(OfferTestCase):
    def setUp(self):
        super().setUp()
        self.offer_obj = self.make_offer(self.buyer, 140_000)

    def decline(self, client=None, offer=None):
        return (client or self.as_seller).post(f"/api/offers/{(offer or self.offer_obj).pk}/decline/")

    def undo(self, client=None):
        return (client or self.as_seller).post(f"/api/offers/{self.offer_obj.pk}/undo-decline/")

    def pass_undo_window(self):
        past = timezone.now() - timedelta(seconds=61)
        Offer.objects.filter(pk=self.offer_obj.pk).update(decided_at=past)
        Notification.objects.filter(ref=f"offer:{self.offer_obj.pk}:declined").update(visible_at=past)

    def unread(self, client=None):
        return (client or self.as_buyer).get("/api/notifications/unread-count/").json()["count"]

    def test_owner_declines_and_buyer_is_told_after_60s(self):
        res = self.decline()
        self.assertEqual(res.status_code, 200, res.json())
        self.assertEqual(res.json()["status"], "declined")
        self.assertIsNotNone(res.json()["undo_until"])
        self.offer_obj.refresh_from_db()
        self.assertEqual(self.offer_obj.status, Status.DECLINED)
        # Not yet: the Undo window is still open.
        self.assertEqual(self.unread(), 0)
        self.assertEqual(self.as_buyer.get("/api/notifications/").json()["results"], [])
        self.pass_undo_window()
        self.assertEqual(self.unread(), 1)
        item = self.as_buyer.get("/api/notifications/").json()["results"][0]
        self.assertEqual(
            item["title_text"],
            "Tolu didn’t accept your ₦140,000 offer on Samsung fridge, 2 doors. You can send a higher offer or Buy now.",
        )
        self.assertEqual(
            (item["kind"], item["category"], item["target_url"], item["read_at"]),
            ("offer_declined", "offer", f"/listings/{self.listing.pk}", None),
        )

    def test_decline_sends_no_sms(self):
        with mock.patch(SEND_SMS) as send, self.captureOnCommitCallbacks(execute=True):
            self.decline()
        send.assert_not_called()

    def test_only_the_owner_can_decline(self):
        self.assertEqual(self.decline(client=self.as_buyer).status_code, 404)
        self.assertEqual(self.decline(client=self.as_other).status_code, 404)

    def test_illegal_declines_are_409(self):
        self.decline()
        res = self.decline()
        self.assertEqual((res.status_code, res.json()["code"]), (409, "not_pending"))
        withdrawn = self.make_offer(self.other, 150_000, status=Status.WITHDRAWN)
        self.assertEqual(self.decline(offer=withdrawn).status_code, 409)
        stale = self.make_offer(make_user("+2348036666666"), 150_000, expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.decline(offer=stale).status_code, 409)

    def test_undo_within_60s_restores_and_cancels_the_notification(self):
        self.decline()
        res = self.undo()
        self.assertEqual(res.status_code, 200, res.json())
        self.offer_obj.refresh_from_db()
        self.assertEqual((self.offer_obj.status, self.offer_obj.decided_at), (Status.PENDING, None))
        self.assertFalse(Notification.objects.exists())
        self.pass_undo_window()
        self.assertEqual(self.unread(), 0)

    def test_undo_after_60s_is_409(self):
        self.decline()
        self.pass_undo_window()
        res = self.undo()
        self.assertEqual((res.status_code, res.json()["code"]), (409, "too_late"))
        self.offer_obj.refresh_from_db()
        self.assertEqual(self.offer_obj.status, Status.DECLINED)
        self.assertEqual(self.unread(), 1)

    def test_undo_needs_a_decline_and_the_owner(self):
        self.assertEqual(self.undo().json()["code"], "not_declined")
        self.decline()
        self.assertEqual(self.undo(client=self.as_buyer).status_code, 404)

    def test_buyer_sees_waiting_during_undo_window(self):
        self.decline()
        viewer = self.as_buyer.get(f"/api/listings/{self.listing.pk}/").json()["viewer"]
        self.assertEqual(viewer["my_open_offer"]["status"], "pending")
        self.assertEqual((viewer["can_offer"], viewer["offer_reason"], viewer["declined_amount"]), (False, "offer_open", None))
        self.assertEqual(self.offer(amount=150_000).json()["code"], "offer_open")

    def test_withdrawing_during_undo_window_cancels_the_decline_notice(self):
        self.decline()
        res = self.as_buyer.post(f"/api/offers/{self.offer_obj.pk}/withdraw/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "withdrawn")
        self.assertFalse(Notification.objects.exists())

    def test_after_decline_buyer_can_offer_higher_only(self):
        self.decline()
        self.pass_undo_window()
        body = self.as_buyer.get(f"/api/listings/{self.listing.pk}/").json()
        self.assertIsNone(body["viewer"]["my_open_offer"])
        self.assertEqual((body["viewer"]["can_offer"], body["viewer"]["declined_amount"]), (True, 140_000))
        self.assertEqual(body["offer_rules"]["min_amount"], 111_000)
        self.assertEqual(body["offer_rules"]["last_declined_amount"], 140_000)
        res = self.offer(amount=140_000)
        self.assertEqual((res.status_code, res.json()["code"]), (400, "not_above_declined"))
        self.assertEqual(res.json()["detail"], "Your new offer must be more than ₦140,000.")
        self.assertEqual(self.offer(amount=145_000).status_code, 201)
        # The notice goes once there's a newer offer.
        self.assertIsNone(self.as_buyer.get(f"/api/listings/{self.listing.pk}/").json()["viewer"]["declined_amount"])
        # Only this buyer's floor moves.
        self.assertIsNone(self.as_other.get(f"/api/listings/{self.listing.pk}/").json()["offer_rules"]["last_declined_amount"])

    def test_three_offers_per_buyer_per_listing(self):
        self.decline()
        self.pass_undo_window()
        second = self.offer(amount=150_000).json()
        self.as_buyer.post(f"/api/offers/{second['id']}/withdraw/")
        self.assertEqual(self.offer(amount=155_000).status_code, 201)
        Offer.objects.filter(buyer=self.buyer, status=Status.PENDING).update(status=Status.WITHDRAWN)
        res = self.offer(amount=160_000)
        self.assertEqual((res.status_code, res.json()["code"]), (409, "offer_limit"))
        viewer = self.as_buyer.get(f"/api/listings/{self.listing.pk}/").json()["viewer"]
        self.assertEqual((viewer["can_offer"], viewer["offer_reason"], viewer["can_buy"]), (False, "offer_limit", True))

    def test_owner_list_shows_decline_at_the_bottom_until_undo_window_ends(self):
        self.make_offer(self.other, 175_000)
        self.decline()
        body = self.as_seller.get(f"/api/listings/{self.listing.pk}/offers/").json()
        self.assertEqual(body["count"], 1)
        self.assertEqual([(o["amount"], o["status"]) for o in body["results"]], [(175_000, "pending"), (140_000, "declined")])
        self.assertIsNotNone(body["results"][1]["undo_until"])
        self.pass_undo_window()
        body = self.as_seller.get(f"/api/listings/{self.listing.pk}/offers/").json()
        self.assertEqual([o["amount"] for o in body["results"]], [175_000])

    def test_sweep_leaves_declines_alone(self):
        self.decline()
        Offer.objects.filter(pk=self.offer_obj.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
        self.assertEqual(expire_offers(), 0)


class AcceptOfferTests(OfferTestCase):
    def accept(self, offer, client=None):
        return (client or self.as_seller).post(f"/api/offers/{offer.pk}/accept/")

    def test_accept_holds_the_price_and_tells_the_buyer(self):
        offer = self.make_offer(self.buyer, 175_000)
        with mock.patch(SEND_SMS) as send_sms, self.captureOnCommitCallbacks(execute=True):
            res = self.accept(offer)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "accepted")
        offer.refresh_from_db()
        held_for = offer.price_held_until - offer.decided_at
        self.assertEqual(held_for, timedelta(hours=24))
        notice = Notification.objects.get(user=self.buyer, kind="offer_accepted")
        self.assertIn("First to pay gets it", notice_text(notice))
        self.assertIn("accepted ₦175,000", send_sms.call_args[0][1])
        # The item stays live: first to pay gets it.
        self.assertEqual(Listing.objects.get(pk=self.listing.pk).approval_status, "approved")
        viewer = self.as_other.get(f"/api/listings/{self.listing.pk}/").json()["viewer"]
        self.assertTrue(viewer["can_buy"])
        mine = self.as_buyer.get(f"/api/listings/{self.listing.pk}/").json()["viewer"]
        self.assertEqual(mine["accepted_offer"]["amount"], 175_000)
        self.assertEqual((mine["can_offer"], mine["offer_reason"]), (False, "offer_accepted"))

    def test_owner_list_puts_accepted_first(self):
        accepted = self.make_offer(self.buyer, 150_000)
        self.make_offer(self.other, 170_000)
        self.accept(accepted)
        results = self.as_seller.get(f"/api/listings/{self.listing.pk}/offers/").json()["results"]
        self.assertEqual(results[0]["id"], accepted.pk)
        self.assertIsNotNone(results[0]["price_held_until"])

    def test_only_the_owner_and_only_pending(self):
        offer = self.make_offer(self.buyer, 175_000)
        self.assertEqual(self.accept(offer, self.as_other).status_code, 404)
        offer.status = Status.WITHDRAWN
        offer.save()
        self.assertEqual(self.accept(offer).status_code, 409)


def notice_text(notification):
    from apps.notifications.kinds import render

    return render(notification)["title_text"]
