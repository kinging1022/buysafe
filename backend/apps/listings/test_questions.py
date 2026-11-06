from datetime import timedelta

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.escrow.models import Transaction
from apps.notifications.models import Notification

from .contact_guard import find_contact
from .models import Listing, ListingQuestion, ListingQuestionEdit
from .testing import make_listing, make_tx, make_user

Status = ListingQuestion.Status


class ContactGuardTests(SimpleTestCase):
    def test_finds_contact_details(self):
        cases = {
            "Call me on 0803 555 1234": "phone",
            "08035551234": "phone",
            "+234 (803) 555-1234": "phone",
            "234-803-555-1234": "phone",
            "803.555.1234": "phone",
            "zero eight zero three five five five one two three four": "phone",
            "0 eight 0 3 555 1234": "phone",
            "0a8b0c3d5e5f5g1h2i3j4": "phone",
            "wa.me/2348035551234": "phone",
            "tolu@gmail.com": "email",
            "tolu at gmail dot com": "email",
            "tolu (at) gmail (dot) com": "email",
            "tolu[at]gmail.com": "email",
            "https://x.co/abc": "link",
            "www.jiji.ng": "link",
            "see toluphones.com": "link",
            "toluphones dot com": "link",
            "shop.com.ng": "link",
            "DM @tolu_sells": "handle",
            "IG @tolu.a": "handle",
        }
        for text, kind in cases.items():
            self.assertEqual(find_contact(text), kind, text)

    def test_leaves_normal_questions_alone(self):
        for text in [
            "Does the freezer still freeze properly?",
            "Is ₦185,000 your last price? I can do 170,000",
            "Can you do 150000 or 160000?",
            "Is it still available at 185000 190000 200000?",
            "I can pick it up at 10am on Sat 4 Oct",
            "Size is 180 x 60 x 65 cm",
            "Model RT38K5032S8, bought 2022",
            "Is it one year old? Does it have two shelves?",
            "Can I come at 5.30pm?",
            "Is it at Surulere or Yaba?",
        ]:
            self.assertIsNone(find_contact(text), text)


class QuestionTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.seller = make_user("+2348031234567", first_name="Tolu", last_name="Adeyemi")
        self.buyer = make_user("+2348031111111", first_name="Ada", last_name="Nwosu")
        self.other = make_user("+2348032222222", first_name="Kunle", last_name="Okafor")
        self.listing = make_listing(self.seller, title="Samsung fridge, 2 doors")
        self.as_seller, self.as_buyer, self.as_other = APIClient(), APIClient(), APIClient()
        self.as_seller.force_login(self.seller)
        self.as_buyer.force_login(self.buyer)
        self.as_other.force_login(self.other)
        self.anon = APIClient()

    def ask(self, text="Does the freezer still freeze properly?", client=None, listing=None):
        return (client or self.as_buyer).post(
            f"/api/listings/{(listing or self.listing).pk}/questions/", {"text": text}, format="json"
        )

    def get(self, client=None):
        return (client or self.anon).get(f"/api/listings/{self.listing.pk}/questions/").json()

    def make_q(self, asker=None, status=Status.PENDING, **extra):
        q = ListingQuestion.objects.create(listing=self.listing, asker=asker or self.buyer, text="Is it cold?", **extra)
        if status == Status.ANSWERED:
            q.answer, q.answered_at, q.status = "Yes.", timezone.now(), status
            q.save()
        elif status != Status.PENDING:
            q.status = status
            q.save()
        return q


class AskTests(QuestionTestCase):
    def test_ask_creates_pending_and_notifies_owner(self):
        res = self.ask("  Does the freezer still freeze properly?  ")
        self.assertEqual(res.status_code, 201, res.json())
        body = res.json()
        self.assertEqual((body["text"], body["status"], body["is_mine"]), ("Does the freezer still freeze properly?", "pending", True))
        self.assertEqual(body["asker"], {"first_name": "Ada", "last_initial": "N"})
        note = Notification.objects.get(user=self.seller)
        self.assertEqual(note.kind, "question_new")
        item = self.as_seller.get("/api/notifications/").json()["results"][0]
        self.assertEqual(item["title_text"], "Ada N. asked about your Samsung fridge, 2 doors.")
        self.assertEqual((item["label"], item["category"]), ("NEW QUESTION", "offer"))
        self.assertEqual(item["target_url"], f"/listings/{self.listing.pk}#questions")

    def test_length_5_to_280(self):
        self.assertEqual(self.ask("Hi?").json()["code"], "too_short")
        self.assertEqual(self.ask("x" * 281).json()["code"], "too_long")
        self.assertEqual(self.ask("x" * 280).status_code, 201)

    def test_contact_details_refused(self):
        for text in ["Call me on 0803 555 1234", "zero eight zero three five five five one two three four", "tolu at gmail dot com", "www.jiji.ng", "DM @tolu_sells"]:
            res = self.ask(text)
            self.assertEqual((res.status_code, res.json()["code"]), (400, "contact_details"), text)
        self.assertFalse(ListingQuestion.objects.exists())

    def test_three_per_rolling_24h_removed_count(self):
        for i in range(3):
            self.assertEqual(self.ask(f"Question number {i}?").status_code, 201)
        ListingQuestion.objects.filter(text="Question number 0?").update(status=Status.REMOVED)
        res = self.ask("A fourth question?")
        self.assertEqual((res.status_code, res.json()["code"]), (429, "question_limit"))
        self.assertIn("retry_at", res.json())
        meta = self.get(self.as_buyer)["meta"]
        self.assertEqual((meta["can_ask"], meta["reason"], meta["questions_left_today"]), (False, "question_limit", 0))
        # The oldest falls out of the window after 24h.
        ListingQuestion.objects.filter(text="Question number 0?").update(created_at=timezone.now() - timedelta(hours=25))
        self.assertEqual(self.get(self.as_buyer)["meta"]["questions_left_today"], 1)
        self.assertEqual(self.ask("Now a fourth?").status_code, 201)
        # Per listing: another listing has its own 3.
        other_listing = make_listing(self.seller, title="Sofa")
        self.assertEqual(self.ask("About the sofa?", listing=other_listing).status_code, 201)

    def test_not_own_listing_and_not_closed_listing(self):
        res = self.ask(client=self.as_seller)
        self.assertEqual((res.status_code, res.json()["code"]), (403, "own_listing"))
        make_tx(self.listing, self.other, Transaction.Status.HELD)
        res = self.ask()
        self.assertEqual((res.status_code, res.json()["code"]), (409, "not_live"))
        self.assertEqual(self.get(self.as_buyer)["meta"]["reason"], "not_live")

    def test_signed_out_and_unverified_cannot_ask(self):
        self.assertEqual(self.ask(client=self.anon).status_code, 403)
        self.assertEqual(self.get()["meta"]["reason"], "login_required")
        unverified = make_user("+2348036666666")
        unverified.phone_verified = False
        unverified.save()
        client = APIClient()
        client.force_login(unverified)
        self.assertEqual(self.ask(client=client).status_code, 403)

    def test_sold_listing_keeps_public_qa_readable(self):
        answered = self.make_q(status=Status.ANSWERED)
        make_tx(self.listing, self.other, Transaction.Status.COMPLETED)
        body = self.get()
        self.assertEqual([q["id"] for q in body["answered"]], [answered.pk])
        self.assertFalse(body["meta"]["can_ask"])

    def test_pending_listing_is_owner_only(self):
        pending = make_listing(self.seller, approval=Listing.Approval.PENDING)
        self.assertEqual(self.anon.get(f"/api/listings/{pending.pk}/questions/").status_code, 404)
        self.assertEqual(self.as_seller.get(f"/api/listings/{pending.pk}/questions/").status_code, 200)


class VisibilityTests(QuestionTestCase):
    def setUp(self):
        super().setUp()
        self.public = self.make_q(asker=self.other, status=Status.ANSWERED)
        self.mine = self.make_q(asker=self.buyer)
        self.theirs = self.make_q(asker=self.other)
        self.removed = self.make_q(asker=self.buyer, status=Status.REMOVED)

    def ids(self, body):
        return [q["id"] for q in body["pending"]], [q["id"] for q in body["answered"]]

    def test_anonymous_sees_answered_only(self):
        body = self.get()
        self.assertEqual(self.ids(body), ([], [self.public.pk]))
        self.assertEqual(body["meta"]["public_count"], 1)
        self.assertIsNone(body["meta"]["pending_count"])

    def test_asker_sees_own_pending(self):
        body = self.get(self.as_buyer)
        self.assertEqual(self.ids(body), ([self.mine.pk], [self.public.pk]))
        self.assertTrue(body["pending"][0]["is_mine"])
        self.assertFalse(body["answered"][0]["is_mine"])

    def test_other_buyer_sees_only_their_own_pending(self):
        self.assertEqual(self.ids(self.get(self.as_other)), ([self.theirs.pk], [self.public.pk]))

    def test_owner_sees_all_pending_oldest_first(self):
        body = self.get(self.as_seller)
        self.assertEqual(self.ids(body), ([self.mine.pk, self.theirs.pk], [self.public.pk]))
        self.assertEqual(body["meta"]["pending_count"], 2)
        self.assertTrue(body["meta"]["is_owner"])

    def test_no_phone_numbers_in_responses(self):
        for client in (self.anon, self.as_buyer, self.as_seller):
            self.assertNotIn("+234", str(self.get(client)))

    def test_answered_paginates_after_10(self):
        for _ in range(11):
            self.make_q(asker=self.other, status=Status.ANSWERED)
        first = self.get()
        self.assertEqual((len(first["answered"]), first["next_page"]), (10, 2))
        second = self.anon.get(f"/api/listings/{self.listing.pk}/questions/?page=2").json()
        self.assertEqual((len(second["answered"]), second["next_page"]), (2, None))


class AnswerTests(QuestionTestCase):
    def setUp(self):
        super().setUp()
        self.q = self.make_q()

    def answer(self, text="Yes, both trays are included.", client=None, method="post"):
        return getattr(client or self.as_seller, method)(f"/api/questions/{self.q.pk}/answer/", {"answer": text}, format="json")

    def test_owner_answers_once_and_asker_is_notified(self):
        res = self.answer()
        self.assertEqual(res.status_code, 200, res.json())
        self.assertEqual((res.json()["status"], res.json()["answer"]), ("answered", "Yes, both trays are included."))
        item = self.as_buyer.get("/api/notifications/").json()["results"][0]
        self.assertEqual(item["title_text"], "Tolu answered your question about the Samsung fridge, 2 doors.")
        self.assertEqual((item["label"], item["category"]), ("ANSWERED", "money"))
        res = self.answer("Another answer.")
        self.assertEqual((res.status_code, res.json()["code"]), (409, "not_pending"))

    def test_only_the_owner(self):
        self.assertEqual(self.answer(client=self.as_buyer).status_code, 404)
        self.assertEqual(self.answer(client=self.as_other).status_code, 404)

    def test_answer_length_and_contacts(self):
        self.assertEqual(self.answer("k").json()["code"], "too_short")
        self.assertEqual(self.answer("x" * 501).json()["code"], "too_long")
        res = self.answer("Call 0803 555 1234")
        self.assertEqual((res.json()["code"], res.json()["kind"]), ("contact_details", "phone"))

    def test_edit_answer_logs_history_and_marks_edited(self):
        self.answer("Yes.")
        res = self.answer("Yes, and the egg rack.", method="patch")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["edited"])
        self.assertEqual(list(ListingQuestionEdit.objects.values_list("previous_answer", flat=True)), ["Yes."])
        self.assertTrue(self.get()["answered"][0]["edited"])
        self.assertEqual(self.answer("my email is tolu@gmail.com", method="patch").json()["code"], "contact_details")

    def test_cannot_edit_unanswered(self):
        self.assertEqual(self.answer(method="patch").json()["code"], "not_answered")


class RemoveTests(QuestionTestCase):
    def setUp(self):
        super().setUp()
        self.q = self.make_q(status=Status.ANSWERED)

    def post(self, action, client=None):
        return (client or self.as_seller).post(f"/api/questions/{self.q.pk}/{action}/")

    def test_remove_hides_everywhere_without_notifying(self):
        before = Notification.objects.count()
        self.assertEqual(self.post("remove").json()["status"], "removed")
        for client in (self.anon, self.as_buyer, self.as_seller):
            body = self.get(client)
            self.assertEqual((body["pending"], body["answered"]), ([], []))
        self.assertEqual(Notification.objects.count(), before)
        self.q.refresh_from_db()
        self.assertEqual(self.q.removed_by, self.seller)

    def test_restore_within_60s_back_to_previous_status(self):
        self.post("remove")
        self.assertEqual(self.post("restore").json()["status"], "answered")
        pending = self.make_q(asker=self.other)
        self.as_seller.post(f"/api/questions/{pending.pk}/remove/")
        self.assertEqual(self.as_seller.post(f"/api/questions/{pending.pk}/restore/").json()["status"], "pending")

    def test_restore_after_60s_is_409(self):
        self.post("remove")
        ListingQuestion.objects.filter(pk=self.q.pk).update(removed_at=timezone.now() - timedelta(seconds=61))
        res = self.post("restore")
        self.assertEqual((res.status_code, res.json()["code"]), (409, "too_late"))

    def test_owner_only_and_no_double_remove(self):
        self.assertEqual(self.post("remove", client=self.as_buyer).status_code, 404)
        self.post("remove")
        self.assertEqual(self.post("remove").json()["code"], "already_removed")
        self.assertEqual(self.as_seller.post(f"/api/questions/{self.make_q().pk}/restore/").json()["code"], "not_removed")
