from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.listings.testing import make_user

from .models import Notification
from .services import cancel, notify

DATA = {"amount": 140_000, "listing_id": 1, "listing_title": "Samsung fridge", "seller_first_name": "Tolu"}


class NotificationApiTests(TestCase):
    def setUp(self):
        self.user = make_user("+2348031111111")
        self.other = make_user("+2348032222222")
        self.client = APIClient()
        self.client.force_login(self.user)

    def test_list_newest_first_only_mine_and_visible(self):
        older = notify(self.user, "offer_declined", DATA)
        Notification.objects.filter(pk=older.pk).update(visible_at=timezone.now() - timedelta(hours=1))
        newer = notify(self.user, "offer_declined", {**DATA, "amount": 150_000})
        notify(self.user, "offer_declined", DATA, delay=timedelta(seconds=60))  # not yet
        notify(self.other, "offer_declined", DATA)
        results = self.client.get("/api/notifications/").json()["results"]
        self.assertEqual([r["id"] for r in results], [newer.pk, older.pk])
        self.assertEqual(
            set(results[0]),
            {"id", "kind", "category", "label", "title_text", "target_url", "created_at", "read_at"},
        )
        self.assertEqual((results[0]["category"], results[0]["label"]), ("offer", "NOT ACCEPTED"))
        self.assertNotIn("+234", str(results))

    def test_unread_count_mark_read_and_read_all(self):
        a = notify(self.user, "offer_declined", DATA)
        notify(self.user, "offer_declined", DATA)
        self.assertEqual(self.client.get("/api/notifications/unread-count/").json(), {"count": 2})
        self.assertIsNotNone(self.client.post(f"/api/notifications/{a.pk}/read/").json()["read_at"])
        self.assertEqual(self.client.get("/api/notifications/unread-count/").json(), {"count": 1})
        self.assertEqual(self.client.post("/api/notifications/read-all/").json(), {"count": 1})
        self.assertEqual(self.client.get("/api/notifications/unread-count/").json(), {"count": 0})

    def test_cannot_read_someone_elses_or_a_hidden_one(self):
        theirs = notify(self.other, "offer_declined", DATA)
        hidden = notify(self.user, "offer_declined", DATA, delay=timedelta(seconds=60))
        self.assertEqual(self.client.post(f"/api/notifications/{theirs.pk}/read/").status_code, 404)
        self.assertEqual(self.client.post(f"/api/notifications/{hidden.pk}/read/").status_code, 404)

    def test_signed_in_only(self):
        self.assertEqual(APIClient().get("/api/notifications/unread-count/").status_code, 403)

    def test_cancel_only_removes_unseen(self):
        notify(self.user, "offer_declined", DATA, ref="x", delay=timedelta(seconds=60))
        self.assertEqual(cancel("x"), 1)
        notify(self.user, "offer_declined", DATA, ref="y")
        self.assertEqual(cancel("y"), 0)

    def test_unknown_kind_is_rejected(self):
        with self.assertRaises(ValueError):
            notify(self.user, "nope", {})


class KindRegistryTests(TestCase):
    def test_every_kind_has_a_known_category(self):
        from .kinds import KINDS, Category

        categories = {Category.OFFER, Category.ACTION, Category.MONEY, Category.INFO}
        for key, kind in KINDS.items():
            self.assertIn(kind.category, categories, key)
            self.assertTrue(kind.label.isupper(), key)
