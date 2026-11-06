import shutil
import struct
import tempfile
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils.functional import empty
from rest_framework.test import APIClient

from apps.escrow.models import Transaction
from apps.listings import status as listing_status
from apps.listings.testing import make_listing, make_payout_account, make_user
from apps.notifications.clock import LAGOS
from apps.notifications.models import Notification
from apps.payments import services as payments
from apps.payments.models import Payout, Refund
from apps.payments.providers import IncomingTransfer
from apps.payments.providers.fake import FakeTransferProvider

from . import services
from .calls import FakeCallService
from .deadlines import awake_time_between, deadline_after, in_quiet_hours
from .models import Deal, LiveVideo, Message, Reminder
from .storage import private_storage

SEND_SMS = "apps.users.services.otp.FakeOtpService.send_sms"
BASE = datetime(2026, 9, 29, 10, 0, tzinfo=LAGOS)  # a Tuesday morning


def at(moment):
    return mock.patch("django.utils.timezone.now", return_value=moment)


def client_for(user):
    client = APIClient()
    client.force_login(user)
    return client


class DeadlineTests(TestCase):
    def lagos(self, day, hour, minute=0):
        return datetime(2026, 9, day, hour, minute, tzinfo=LAGOS)

    def test_daytime_window(self):
        self.assertEqual(deadline_after(self.lagos(29, 10), 4), self.lagos(29, 14))

    def test_clock_pauses_overnight(self):
        # 2h before 22:00, then 2h after 07:00.
        self.assertEqual(deadline_after(self.lagos(29, 20), 4), self.lagos(30, 9))

    def test_starting_in_quiet_hours_waits_for_morning(self):
        self.assertEqual(deadline_after(self.lagos(29, 23, 30), 4), self.lagos(30, 11))
        self.assertEqual(deadline_after(self.lagos(30, 3), 2), self.lagos(30, 9))

    def test_ending_exactly_at_quiet_start(self):
        self.assertEqual(deadline_after(self.lagos(29, 18), 4), self.lagos(29, 22))

    def test_spanning_several_nights(self):
        # 21:00 +26h: 1h tonight, 15h tomorrow, 10h the day after.
        self.assertEqual(deadline_after(self.lagos(28, 21), 26), self.lagos(30, 17))

    def test_awake_time_between(self):
        self.assertEqual(awake_time_between(self.lagos(29, 21), self.lagos(30, 8)), timedelta(hours=2))
        self.assertEqual(awake_time_between(self.lagos(29, 12), self.lagos(29, 11)), timedelta(0))

    def test_quiet_hours_edges(self):
        self.assertTrue(in_quiet_hours(self.lagos(29, 22)))
        self.assertTrue(in_quiet_hours(self.lagos(30, 6, 59)))
        self.assertFalse(in_quiet_hours(self.lagos(30, 7)))
        self.assertFalse(in_quiet_hours(self.lagos(29, 21, 59)))


class DealTestCase(TestCase):
    def setUp(self):
        cache.clear()
        FakeTransferProvider.reset()
        FakeCallService.placed = []
        self.seller = make_user("+2348031234567", first_name="Tolu", last_name="Adeyemi")
        self.buyer = make_user("+2348031111111", first_name="Ada", last_name="Nwosu", avatar_color="sky")
        self.other = make_user("+2348032222222", first_name="Kunle", last_name="Okafor")
        make_payout_account(self.seller)
        self.listing = make_listing(self.seller, title="Samsung fridge, 2 doors", price=185_000, area="Surulere")
        self.as_seller = client_for(self.seller)
        self.as_buyer = client_for(self.buyer)
        self.as_other = client_for(self.other)

    def open_deal(self, when=BASE, listing=None, buyer=None, ref="IN-1"):
        listing = listing or self.listing
        buyer = buyer or self.buyer
        with at(when):
            intent = payments.start_payment(listing, buyer)
            incoming = IncomingTransfer(
                ref, intent.virtual_account_number, Decimal(listing.price), "ADA NWOSU", "GTBank", "000013",
                "0123450821", when,
            )
            with self.captureOnCommitCallbacks(execute=True):
                payments.record_transfer(incoming)
        return Deal.objects.get(pk=intent.pk)

    def video(self, deal, when):
        with at(when):
            return services.add_video(
                deal, self.seller, file_name="deal-videos/x.webm", mime="video/webm", duration=42,
                captured_at=when, container_created_at=None,
            )

    def rate(self, deal, n, verdict, when, chips=(), note=""):
        with at(when):
            return services.rate_video(deal, self.buyer, n, verdict, list(chips), note)

    def sweep(self, when):
        with at(when), self.captureOnCommitCallbacks(execute=True):
            return services.sweep()

    def refreshed(self, deal):
        return Deal.objects.get(pk=deal.pk)


class TransitionTests(DealTestCase):
    def test_opens_waiting_for_the_video(self):
        deal = self.open_deal()
        self.assertEqual(deal.state, Deal.State.AWAITING_VIDEO)
        self.assertEqual(deal.current_deadline, BASE + timedelta(hours=4))
        self.assertEqual(deal.messages.get().body, "paid")

    def test_video_then_good_opens_the_chat(self):
        deal = self.open_deal()
        self.video(deal, BASE + timedelta(hours=1))
        deal = self.refreshed(deal)
        self.assertEqual((deal.state, deal.video_count), (Deal.State.VIDEO_TO_RATE, 1))
        self.assertEqual(deal.current_deadline, BASE + timedelta(hours=3))
        self.assertTrue(Notification.objects.filter(user=self.buyer, kind="video_ready").exists())
        self.rate(deal, 1, "good", BASE + timedelta(hours=2))
        deal = self.refreshed(deal)
        self.assertEqual(deal.state, Deal.State.CHAT_OPEN)
        self.assertIsNone(deal.current_deadline)
        self.assertEqual(deal.videos.get().verdict, LiveVideo.Verdict.GOOD)

    def test_bad_asks_for_another_with_a_fresh_4_hours(self):
        deal = self.open_deal()
        self.video(deal, BASE + timedelta(hours=3))  # 1h of the first window left
        self.rate(deal, 1, "bad", BASE + timedelta(hours=3, minutes=30), chips=["Show the back", "Closer"], note="The dent")
        deal = self.refreshed(deal)
        self.assertEqual(deal.state, Deal.State.AWAITING_VIDEO)
        self.assertEqual(deal.current_deadline, BASE + timedelta(hours=7, minutes=30))
        instruction = deal.messages.get(kind=Message.Kind.INSTRUCTION)
        self.assertEqual(instruction.data, {"next_n": 2, "chips": ["Show the back", "Closer"], "note": "The dent"})
        notice = Notification.objects.get(user=self.seller, kind="video_requested")
        self.assertEqual(notice.data["ask"], "Show the back · Closer")
        self.assertEqual(notice.data["n"], 2)

    def test_bad_rejects_unknown_chips_and_long_notes(self):
        deal = self.open_deal()
        self.video(deal, BASE)
        with self.assertRaises(services.DealError):
            self.rate(deal, 1, "bad", BASE, chips=["Dance"])
        with self.assertRaises(services.DealError):
            self.rate(deal, 1, "bad", BASE, note="x" * 201)

    def third_bad(self):
        deal = self.open_deal()
        for n in (1, 2, 3):
            self.video(deal, BASE + timedelta(minutes=10 * n))
            self.rate(deal, n, "bad", BASE + timedelta(minutes=10 * n + 5), chips=["Closer"])
        return self.refreshed(deal)

    def test_third_bad_asks_the_buyer_to_decide(self):
        deal = self.third_bad()
        self.assertEqual((deal.state, deal.video_count), (Deal.State.AWAITING_DECISION, 3))
        self.assertEqual(deal.messages.filter(kind=Message.Kind.INSTRUCTION).count(), 2)

    def test_third_bad_refund_is_full_to_the_paying_account(self):
        deal = self.third_bad()
        with self.captureOnCommitCallbacks(execute=True):
            res = self.as_buyer.post(f"/api/deals/{deal.pk}/after-third-bad/", {"choice": "refund"}, format="json")
        self.assertEqual(res.json()["state"], "refunded")
        deal = self.refreshed(deal)
        refund = deal.refund
        self.assertEqual((refund.reason, refund.amount, refund.fee), ("cancelled_after_3_bad", Decimal("185000"), Decimal("0")))
        self.assertEqual(FakeTransferProvider.sent[-1]["account"], "0123450821")
        self.assertEqual(deal.transaction.status, Transaction.Status.REFUNDED)
        self.assertEqual(listing_status.listing_display_status(self.listing), listing_status.LIVE)
        self.assertEqual(res.json()["refund"]["bank"], "GTBank")

    def test_third_bad_continue_opens_the_chat(self):
        deal = self.third_bad()
        res = self.as_buyer.post(f"/api/deals/{deal.pk}/after-third-bad/", {"choice": "continue"}, format="json")
        self.assertEqual(res.json()["state"], "chat_open")
        self.assertEqual(self.refreshed(deal).buyer_choice_after_3_bad, "continue")

    def test_illegal_transitions_are_409(self):
        deal = self.open_deal()
        url = f"/api/deals/{deal.pk}"
        self.assertEqual(self.as_buyer.post(f"{url}/videos/1/rate/", {"verdict": "good"}, format="json").status_code, 409)
        self.assertEqual(self.as_buyer.post(f"{url}/confirm-receipt/", {"checked": True}, format="json").status_code, 409)
        self.assertEqual(self.as_buyer.post(f"{url}/after-third-bad/", {"choice": "refund"}, format="json").status_code, 409)
        self.assertEqual(self.as_buyer.post(f"{url}/meetups/", {"when": "2030-01-01T10:00:00+01:00", "place": "Shoprite"}, format="json").status_code, 409)
        self.video(deal, BASE)
        # The seller can't rate their own video.
        self.assertEqual(self.as_seller.post(f"{url}/videos/1/rate/", {"verdict": "good"}, format="json").status_code, 403)
        # Only the latest video, once.
        self.rate(deal, 1, "good", BASE)
        self.assertEqual(self.as_buyer.post(f"{url}/videos/1/rate/", {"verdict": "bad"}, format="json").status_code, 409)
        self.assertEqual(self.as_seller.post(f"{url}/videos/", {"action": "init"}, format="json").status_code, 409)

    def chat_open(self):
        deal = self.open_deal()
        self.video(deal, BASE)
        self.rate(deal, 1, "good", BASE)
        return self.refreshed(deal)

    def test_confirm_releases_the_frozen_payout_once(self):
        deal = self.chat_open()
        url = f"/api/deals/{deal.pk}/confirm-receipt/"
        self.assertEqual(self.as_buyer.post(url, {"checked": False}, format="json").status_code, 400)
        self.assertEqual(self.as_seller.post(url, {"checked": True}, format="json").status_code, 403)
        with mock.patch("apps.listings.fees.calculate_fee", side_effect=AssertionError("never recalculated")):
            with self.captureOnCommitCallbacks(execute=True):
                res = self.as_buyer.post(url, {"checked": True}, format="json")
        self.assertEqual(res.json()["state"], "released")
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.as_buyer.post(url, {"checked": True}, format="json").status_code, 409)
        self.assertEqual(Payout.objects.count(), 1)
        self.assertEqual(len(FakeTransferProvider.sent), 1)
        sent = FakeTransferProvider.sent[0]
        self.assertEqual((sent["account"], sent["amount"]), ("0123454521", Decimal("166500")))
        deal = self.refreshed(deal)
        self.assertEqual(deal.transaction.status, Transaction.Status.COMPLETED)
        self.assertEqual(deal.transaction.payout, 166_500)
        self.assertEqual(listing_status.listing_display_status(self.listing), listing_status.SOLD)
        released = Notification.objects.get(user=self.seller, kind="money_released")
        self.assertEqual((released.data["amount"], released.data["last4"]), (166_500, "4521"))
        seller_view = self.as_seller.get(f"/api/deals/{deal.pk}/").json()
        self.assertEqual(seller_view["payout_account"], {"bank_name": "Access Bank", "bank_short": "Access", "last4": "4521"})

    def test_no_show_refund_by_staff(self):
        deal = self.chat_open()
        with self.captureOnCommitCallbacks(execute=True):
            services.refund_no_show(deal, self.other)
        deal = self.refreshed(deal)
        self.assertEqual((deal.state, deal.refund.reason), (Deal.State.REFUNDED, Refund.Reason.NO_SHOW))
        self.assertEqual(FakeTransferProvider.sent[-1]["account"], "0123450821")

    def test_meetup_proposed_then_confirmed_by_the_other_person(self):
        deal = self.chat_open()
        url = f"/api/deals/{deal.pk}/meetups/"
        when = "2030-10-04T10:00:00+01:00"
        body = self.as_seller.post(url, {"when": when, "place": "Shoprite, Surulere"}, format="json").json()
        meetup_id = body["meetup"]["id"]
        self.assertEqual(body["meetup"]["status"], "proposed")
        self.assertEqual(self.as_seller.post(f"{url}{meetup_id}/confirm/").status_code, 409)
        body = self.as_buyer.post(f"{url}{meetup_id}/confirm/").json()
        self.assertEqual(body["meetup"]["status"], "confirmed")


class SweepTests(DealTestCase):
    def test_missed_video_deadline_refunds_in_full(self):
        deal = self.open_deal()
        self.sweep(BASE + timedelta(hours=3, minutes=59))
        self.assertEqual(self.refreshed(deal).state, Deal.State.AWAITING_VIDEO)
        result = self.sweep(BASE + timedelta(hours=4))
        self.assertEqual(result["refunded"], 1)
        deal = self.refreshed(deal)
        self.assertEqual((deal.state, deal.refund.reason), (Deal.State.REFUNDED, "seller_missed_video"))
        self.assertEqual((deal.refund.amount, deal.refund.fee), (Decimal("185000"), Decimal("0")))
        self.assertEqual(FakeTransferProvider.sent[-1]["account"], "0123450821")
        self.assertTrue(deal.messages.filter(kind=Message.Kind.SYSTEM, body="video_missed").exists())
        notice = Notification.objects.get(user=self.buyer, kind="deal_refunded")
        self.assertEqual(notice.data["why"], "Tolu didn’t send a video in time.")

    def test_overnight_the_clock_pauses(self):
        evening = BASE.replace(hour=20)
        deal = self.open_deal(when=evening)
        self.assertEqual(deal.current_deadline, (evening + timedelta(days=1)).replace(hour=9))
        self.sweep(evening.replace(hour=23, minute=59))
        deal = self.refreshed(deal)
        self.assertEqual(deal.state, Deal.State.AWAITING_VIDEO)
        self.assertIsNotNone(deal.deadline_paused_at)
        self.sweep((evening + timedelta(days=1)).replace(hour=8))
        self.assertIsNone(self.refreshed(deal).deadline_paused_at)

    def test_no_rating_in_2_hours_counts_as_good(self):
        deal = self.open_deal()
        self.video(deal, BASE + timedelta(hours=1))
        self.sweep(BASE + timedelta(hours=2, minutes=59))
        self.assertEqual(self.refreshed(deal).state, Deal.State.VIDEO_TO_RATE)
        result = self.sweep(BASE + timedelta(hours=3))
        self.assertEqual(result["auto_good"], 1)
        deal = self.refreshed(deal)
        self.assertEqual(deal.state, Deal.State.CHAT_OPEN)
        self.assertEqual(deal.videos.get().verdict, LiveVideo.Verdict.AUTO_GOOD)


@mock.patch(SEND_SMS)
class ReminderTests(DealTestCase):
    def channels(self, deal, step):
        return sorted(Reminder.objects.filter(deal=deal, step=step).values_list("channel", "n"))

    def test_video_schedule_and_one_call(self, send_sms):
        deal = self.open_deal()
        self.assertEqual(self.channels(deal, "video_1"), [("push", 0), ("sms", 0)])
        self.assertEqual(send_sms.call_count, 1)
        self.assertIn("Record a live video", send_sms.call_args[0][1])
        self.sweep(BASE + timedelta(minutes=29))
        self.assertEqual(FakeCallService.placed, [])
        self.sweep(BASE + timedelta(minutes=30))
        self.sweep(BASE + timedelta(minutes=45))
        self.assertEqual(len(FakeCallService.placed), 1)
        self.assertEqual(FakeCallService.placed[0][0], self.seller.phone)
        self.sweep(BASE + timedelta(hours=3))
        self.assertEqual(self.channels(deal, "video_1"), [("call", 1), ("push", 0), ("push", 2), ("sms", 0), ("sms", 2)])
        self.assertTrue(Notification.objects.filter(user=self.seller, kind="video_reminder").exists())
        self.sweep(BASE + timedelta(hours=3, minutes=30))
        self.assertEqual(Reminder.objects.filter(deal=deal, channel="call").count(), 1)

    def test_quiet_hours_hold_sms_and_calls(self, send_sms):
        night = BASE.replace(hour=22, minute=30)
        deal = self.open_deal(when=night)
        self.assertEqual(self.channels(deal, "video_1"), [("push", 0)])
        self.assertEqual(send_sms.call_count, 0)
        self.sweep(night + timedelta(hours=3))  # 01:30: still quiet
        self.assertEqual(send_sms.call_count, 0)
        self.assertEqual(FakeCallService.placed, [])
        morning = (night + timedelta(days=1)).replace(hour=7, minute=1)
        self.sweep(morning)
        self.assertEqual(self.channels(deal, "video_1"), [("push", 0), ("sms", 0)])
        self.sweep(morning + timedelta(minutes=30))
        self.assertEqual(len(FakeCallService.placed), 1)

    def test_rating_schedule(self, send_sms):
        deal = self.open_deal()
        self.video(deal, BASE)
        self.assertEqual(self.channels(deal, "rate_1"), [("push", 0)])
        self.sweep(BASE + timedelta(minutes=30))
        self.assertEqual(self.channels(deal, "rate_1"), [("push", 0), ("sms", 1)])
        self.sweep(BASE + timedelta(hours=1))
        self.sweep(BASE + timedelta(hours=1, minutes=30))
        self.assertEqual([p for p, _ in FakeCallService.placed].count(self.buyer.phone), 1)

    def test_each_re_record_is_its_own_step(self, send_sms):
        deal = self.open_deal()
        self.video(deal, BASE)
        self.rate(deal, 1, "bad", BASE + timedelta(minutes=5), chips=["Closer"])
        self.assertEqual(self.channels(deal, "video_2"), [("push", 0), ("sms", 0)])
        self.sweep(BASE + timedelta(minutes=40))
        self.assertEqual(Reminder.objects.filter(deal=deal, step="video_2", channel="call").count(), 1)


class ChatTests(DealTestCase):
    def send(self, client, deal, body):
        return client.post(f"/api/deals/{deal.pk}/messages/", {"body": body}, format="json")

    def test_contacts_masked_before_the_chat_opens(self):
        deal = self.open_deal()
        res = self.send(self.as_buyer, deal, "Call me on 0803 555 1234 or ada@gmail.com")
        self.assertEqual(res.status_code, 201)
        texts = [m for m in self.as_seller.get(f"/api/deals/{deal.pk}/messages/").json()["results"] if m["kind"] == "text"]
        self.assertEqual(len(texts), 1)
        self.assertNotIn("0803", texts[0]["body"])
        self.assertNotIn("gmail", texts[0]["body"])
        self.assertIn("•••", texts[0]["body"])
        self.assertIn("0803", Message.objects.get(kind="text").body)  # kept for moderation

    def test_spelled_out_numbers_are_masked(self):
        deal = self.open_deal()
        self.send(self.as_buyer, deal, "zero eight zero three five five five one two three four")
        body = Message.objects.get(kind="text").shown_body
        self.assertNotIn("eight", body)

    def test_seller_cant_type_or_send_photos_before_the_chat_opens(self):
        deal = self.open_deal()
        res = self.send(self.as_seller, deal, "Hello")
        self.assertEqual((res.status_code, res.json()["code"]), (403, "locked"))
        self.assertEqual(self.as_seller.get(f"/api/deals/{deal.pk}/").json()["can"]["send_text"], False)
        self.assertEqual(self.as_buyer.get(f"/api/deals/{deal.pk}/").json()["can"]["send_text"], True)

    def test_after_good_nothing_is_masked(self):
        deal = self.open_deal()
        self.video(deal, BASE)
        self.rate(deal, 1, "good", BASE)
        self.assertEqual(self.send(self.as_seller, deal, "My number is 0803 555 1234").status_code, 201)
        self.assertEqual(Message.objects.get(kind="text").shown_body, "My number is 0803 555 1234")

    def test_closed_deal_is_read_only(self):
        deal = self.open_deal()
        with self.captureOnCommitCallbacks(execute=True):
            self.sweep(BASE + timedelta(hours=5))
        self.assertEqual(self.send(self.as_buyer, deal, "Hello?").json()["code"], "closed")
        self.assertEqual(self.as_buyer.get(f"/api/deals/{deal.pk}/messages/").status_code, 200)

    def test_read_receipts_and_the_badge(self):
        deal = self.open_deal()
        self.send(self.as_buyer, deal, "Please show the back")
        # Seller: 1 unread + their turn (record the video).
        self.assertEqual(self.as_seller.get("/api/deals/badge/").json(), {"count": 2})
        self.as_seller.get(f"/api/deals/{deal.pk}/messages/")
        self.assertEqual(self.as_seller.get("/api/deals/badge/").json(), {"count": 1})
        mine = self.as_buyer.get(f"/api/deals/{deal.pk}/messages/").json()["results"][-1]
        self.assertTrue(mine["mine"])
        self.assertIsNotNone(mine["read_at"])
        self.assertEqual(self.as_buyer.get("/api/deals/badge/").json(), {"count": 0})

    def test_only_participants(self):
        deal = self.open_deal()
        base = f"/api/deals/{deal.pk}"
        self.assertEqual(self.as_other.get(f"{base}/").status_code, 404)
        self.assertEqual(self.as_other.get(f"{base}/messages/").status_code, 404)
        self.assertEqual(self.send(self.as_other, deal, "hi").status_code, 404)
        self.assertEqual(self.as_other.post(f"{base}/confirm-receipt/", {"checked": True}, format="json").status_code, 404)
        self.assertEqual(self.as_other.post(f"{base}/report/", {"text": "Something is wrong here"}, format="json").status_code, 404)
        self.assertEqual(self.as_other.get("/api/deals/").json()["results"], [])
        self.assertEqual(APIClient().get(f"{base}/").status_code, 403)

    def test_buyer_sees_their_paying_account_seller_sees_the_money(self):
        deal = self.open_deal()
        buyer_view = self.as_buyer.get(f"/api/deals/{deal.pk}/").json()
        self.assertEqual(buyer_view["source"], {"bank": "GTBank", "last4": "0821"})
        self.assertNotIn("payout", buyer_view)
        seller_view = self.as_seller.get(f"/api/deals/{deal.pk}/").json()
        self.assertNotIn("source", seller_view)
        self.assertEqual((seller_view["fee"], seller_view["payout"], seller_view["fee_rate_label"]), (18_500, 166_500, "10%"))
        self.assertEqual(seller_view["turn"], "me")
        self.assertEqual(buyer_view["turn"], "them")

    def test_report_a_problem(self):
        deal = self.open_deal()
        res = self.as_buyer.post(f"/api/deals/{deal.pk}/report/", {"text": "He stopped replying"}, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(deal.reports.get().reporter, self.buyer)


class DealsListTests(DealTestCase):
    def test_tabs_counts_and_your_turn_first(self):
        mine_to_sell = self.open_deal()  # Tolu sells: Tolu's turn (record)
        other_listing = make_listing(self.buyer, title="Standing fan, 18 inch", price=18_000)
        make_payout_account(self.buyer)
        buying = self.open_deal(when=BASE - timedelta(hours=1), listing=other_listing, buyer=self.seller, ref="IN-2")
        body = self.as_seller.get("/api/deals/?tab=active").json()
        self.assertEqual(body["counts"], {"active": 2, "completed": 0, "refunded": 0})
        self.assertEqual([r["id"] for r in body["results"]], [mine_to_sell.pk, buying.pk])
        self.assertEqual(body["results"][0]["turn"], "me")
        self.assertEqual(body["results"][1]["turn"], "them")
        self.assertEqual(body["results"][1]["other"]["first_name"], "Ada")
        self.assertEqual(self.as_seller.get("/api/deals/?tab=completed").json()["results"], [])


def webm_bytes(size=4096):
    return b"\x1a\x45\xdf\xa3" + bytes(size - 4)


def mp4_bytes(created):
    seconds = int((created - datetime(1904, 1, 1, tzinfo=dt_timezone.utc)).total_seconds())
    mvhd = b"mvhd" + b"\x00\x00\x00\x00" + struct.pack(">IIII", seconds, seconds, 1000, 30_000)
    return b"\x00\x00\x00\x18ftypisom" + bytes(12) + b"\x00\x00\x00\x6cmoov\x00\x00\x00\x64" + mvhd + bytes(80)


class VideoUploadTests(DealTestCase):
    def setUp(self):
        super().setUp()
        self.media = tempfile.mkdtemp()
        self.override = override_settings(PRIVATE_MEDIA_ROOT=self.media)
        self.override.enable()
        private_storage._wrapped = empty
        self.deal = self.open_deal()

    def tearDown(self):
        self.override.disable()
        private_storage._wrapped = empty
        shutil.rmtree(self.media, ignore_errors=True)
        super().tearDown()

    def upload(self, data, mime="video/webm", duration=30, captured_at=None, when=BASE):
        url = f"/api/deals/{self.deal.pk}/videos/"
        with at(when):
            init = self.as_seller.post(
                url,
                {"action": "init", "size": len(data), "mime": mime, "duration": duration,
                 "captured_at": (captured_at or when).isoformat()},
                format="json",
            )
            if init.status_code != 201:
                return init
            upload = init.json()
            half = len(data) // 2
            for start, chunk in ((0, data[:half]), (half, data[half:])):
                res = self.as_seller.put(
                    upload["upload_url"], chunk, content_type="application/octet-stream",
                    HTTP_CONTENT_RANGE=f"bytes {start}-{start + len(chunk) - 1}/{len(data)}",
                )
                self.assertEqual(res.status_code, 200, res.content)
            return self.as_seller.post(url, {"action": "complete", "upload_id": upload["upload_id"]}, format="json")

    def test_resumable_upload_then_the_buyer_watches(self):
        res = self.upload(webm_bytes())
        self.assertEqual(res.status_code, 201, res.content)
        self.assertTrue(res.json()["overlay_text"].startswith("RECORDED IN-APP · 29 SEP 10:00 AM · SURULERE"))
        self.assertEqual(Deal.objects.get(pk=self.deal.pk).state, Deal.State.VIDEO_TO_RATE)
        file_url = f"/api/deals/{self.deal.pk}/videos/1/file/"
        ranged = self.as_buyer.get(file_url, HTTP_RANGE="bytes=0-9")
        self.assertEqual(ranged.status_code, 206)
        self.assertEqual(ranged["Content-Range"], "bytes 0-9/4096")
        self.assertEqual(self.as_other.get(file_url).status_code, 404)

    def test_resume_offset_and_wrong_offset(self):
        with at(BASE):
            upload = self.as_seller.post(
                f"/api/deals/{self.deal.pk}/videos/",
                {"action": "init", "size": 100, "mime": "video/webm", "duration": 30, "captured_at": BASE.isoformat()},
                format="json",
            ).json()
            wrong = self.as_seller.put(upload["upload_url"], b"x" * 10, content_type="application/octet-stream",
                                       HTTP_CONTENT_RANGE="bytes 10-19/100")
            self.assertEqual((wrong.status_code, wrong.json()["offset"]), (409, 0))
            self.assertEqual(self.as_seller.get(upload["upload_url"]).json(), {"offset": 0})
            self.assertEqual(self.as_other.get(upload["upload_url"]).status_code, 404)

    def test_rejects_old_recordings(self):
        res = self.upload(webm_bytes(), captured_at=BASE - timedelta(minutes=6))
        self.assertEqual(res.json()["code"], "stale")
        res = self.upload(mp4_bytes(BASE - timedelta(hours=1)), mime="video/mp4")
        self.assertEqual(res.json()["code"], "stale")
        self.assertEqual(Deal.objects.get(pk=self.deal.pk).state, Deal.State.AWAITING_VIDEO)

    def test_accepts_a_fresh_mp4(self):
        res = self.upload(mp4_bytes(BASE - timedelta(seconds=40)), mime="video/mp4")
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(LiveVideo.objects.get().duration, 30)

    def test_length_limits(self):
        self.assertEqual(self.upload(webm_bytes(), duration=12).json()["code"], "too_short")
        self.assertEqual(self.upload(webm_bytes(), duration=75).json()["code"], "too_long")

    def test_not_a_video(self):
        self.assertEqual(self.upload(b"hello" * 100).json()["code"], "invalid")

    def test_only_the_seller(self):
        res = self.as_buyer.post(f"/api/deals/{self.deal.pk}/videos/", {"action": "init"}, format="json")
        self.assertEqual(res.status_code, 409)
