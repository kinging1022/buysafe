from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.escrow.models import Transaction

from .models import Listing, ListingInterest, ListingPhoto
from .status import listing_display_status
from .testing import make_listing as _make_listing
from .testing import make_tx as _make_tx
from .testing import make_user

Approval = Listing.Approval
TxStatus = Transaction.Status


class ListingFixtures:
    def make_user(self, phone):
        return make_user(phone)

    def make_listing(self, seller, approval=Approval.APPROVED, **extra):
        return _make_listing(seller, approval, **extra)

    def make_tx(self, listing, status, **extra):
        return _make_tx(listing, self.buyer, status, **extra)


class DisplayStatusTests(ListingFixtures, TestCase):
    def setUp(self):
        self.seller = self.make_user("+2348031234567")
        self.buyer = self.make_user("+2348031111111")

    def status_of(self, listing):
        return listing_display_status(listing)

    def test_deleted_is_excluded(self):
        listing = self.make_listing(self.seller, is_deleted=True)
        self.make_tx(listing, TxStatus.COMPLETED)
        self.assertIsNone(self.status_of(listing))

    def test_completed_transaction_is_sold(self):
        # Sold wins over everything else, even a rejected approval.
        listing = self.make_listing(self.seller, Approval.REJECTED)
        self.make_tx(listing, TxStatus.HELD)
        self.make_tx(listing, TxStatus.COMPLETED)
        self.assertEqual(self.status_of(listing), "sold")

    def test_held_transaction_is_in_escrow(self):
        listing = self.make_listing(self.seller, Approval.REJECTED)
        self.make_tx(listing, TxStatus.HELD)
        self.assertEqual(self.status_of(listing), "in_escrow")

    def test_inactive_transactions_are_ignored(self):
        listing = self.make_listing(self.seller)
        for status in (TxStatus.PENDING_PAYMENT, TxStatus.REFUNDED, TxStatus.CANCELLED):
            self.make_tx(listing, status)
        self.assertEqual(self.status_of(listing), "live")

    def test_rejected(self):
        self.assertEqual(self.status_of(self.make_listing(self.seller, Approval.REJECTED)), "rejected")

    def test_pending(self):
        self.assertEqual(self.status_of(self.make_listing(self.seller, Approval.PENDING)), "pending")

    def test_approved_is_live(self):
        self.assertEqual(self.status_of(self.make_listing(self.seller, Approval.APPROVED)), "live")

    def test_new_listing_defaults_to_pending(self):
        listing = _make_listing(self.seller, Approval.PENDING, title="Fan", price=18_000)
        self.assertEqual(self.status_of(listing), "pending")


class MyListingsApiTests(ListingFixtures, TestCase):
    def setUp(self):
        cache.clear()
        self.seller = self.make_user("+2348031234567")
        self.buyer = self.make_user("+2348031111111")
        self.client = APIClient()
        self.client.force_login(self.seller)

        now = timezone.now()
        self.live = self.make_listing(self.seller, title="Fridge", area="Surulere")
        ListingInterest.objects.create(listing=self.live, buyer=self.buyer)
        ListingInterest.objects.create(listing=self.live, buyer=self.make_user("+2348032222222"))
        ListingPhoto.objects.create(listing=self.live, image="listings/2026/09/b.jpg", position=1)
        ListingPhoto.objects.create(listing=self.live, image="listings/2026/09/a.jpg", position=0)

        self.escrow = self.make_listing(self.seller, title="iPhone 12")
        self.make_tx(self.escrow, TxStatus.HELD, meetup_at=now + timedelta(days=1))

        self.pending = self.make_listing(self.seller, Approval.PENDING, title="Laptop")
        self.rejected = self.make_listing(
            self.seller, Approval.REJECTED, title="Generator", rejection_reason="Photos too dark to check condition."
        )
        self.sold = self.make_listing(self.seller, title="Air fryer")
        self.make_tx(self.sold, TxStatus.COMPLETED, payout=42_750, completed_at=now)

        self.make_listing(self.seller, title="Deleted", is_deleted=True)
        self.make_listing(self.buyer, title="Someone else’s")

    def get(self, path):
        res = self.client.get(path)
        self.assertEqual(res.status_code, 200)
        return res.json()

    def by_title(self, body):
        return {item["title"]: item for item in body["results"]}

    def test_all_tab(self):
        body = self.get("/api/me/listings/")
        self.assertEqual(body["count"], 5)
        items = self.by_title(body)
        self.assertEqual(
            {title: item["display_status"] for title, item in items.items()},
            {"Fridge": "live", "iPhone 12": "in_escrow", "Laptop": "pending", "Generator": "rejected",
             "Air fryer": "sold"},
        )
        # Newest first.
        self.assertEqual([i["title"] for i in body["results"]][0], "Air fryer")

    def test_active_tab(self):
        body = self.get("/api/me/listings/?tab=active")
        self.assertEqual({i["title"] for i in body["results"]}, {"Fridge", "iPhone 12"})

    def test_card_details(self):
        items = self.by_title(self.get("/api/me/listings/"))
        fridge, phone, generator, fryer = items["Fridge"], items["iPhone 12"], items["Generator"], items["Air fryer"]

        self.assertEqual(fridge["interest_count"], 2)
        self.assertEqual(fridge["first_image_url"], "/media/listings/2026/09/a.jpg")
        self.assertEqual(fridge["area"], "Surulere")
        self.assertEqual(fridge["price"], 185_000)
        self.assertIsNone(phone["first_image_url"])
        self.assertIsNotNone(phone["meetup_at"])
        self.assertEqual(generator["rejection_reason"], "Photos too dark to check condition.")
        self.assertEqual(fryer["payout"], 42_750)
        self.assertIsNotNone(fryer["sold_at"])
        # Details only appear on the status they belong to.
        self.assertIsNone(fridge["payout"])
        self.assertIsNone(fridge["meetup_at"])

    def test_counts(self):
        self.assertEqual(self.get("/api/me/listing-stats/"), {"live": 1, "in_escrow": 1, "sold": 1, "all": 5})

    def test_pagination_is_12(self):
        for n in range(10):
            self.make_listing(self.seller, title=f"Extra {n}")
        first = self.get("/api/me/listings/")
        self.assertEqual((first["count"], len(first["results"])), (15, 12))
        self.assertIsNotNone(first["next"])
        second = self.get("/api/me/listings/?page=2")
        self.assertEqual(len(second["results"]), 3)

    def test_no_n_plus_one(self):
        for n in range(10):
            listing = self.make_listing(self.seller, title=f"Extra {n}")
            ListingInterest.objects.create(listing=listing, buyer=self.buyer)
        # Session + user lookups, then count and page: the same for any page size.
        with self.assertNumQueries(4):
            self.client.get("/api/me/listings/")
        with self.assertNumQueries(3):
            self.client.get("/api/me/listing-stats/")

    def test_requires_login(self):
        self.assertEqual(APIClient().get("/api/me/listings/").status_code, 403)
        self.assertEqual(APIClient().get("/api/me/listing-stats/").status_code, 403)
