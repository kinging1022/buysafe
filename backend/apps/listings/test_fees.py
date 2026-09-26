import json

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from .fees import MIN_PRICE, calculate_fee
from .management.commands import export_fee_schedule
from .testing import make_user


class CalculateFeeTests(SimpleTestCase):
    def check(self, price, fee, payout, tier):
        q = calculate_fee(price)
        self.assertEqual((q.fee, q.payout, q.tier_key), (fee, payout, tier), f"₦{price}")
        self.assertEqual(q.fee + q.payout, price)

    def test_minimum_is_2000(self):
        self.assertEqual(MIN_PRICE, 2_000)

    def test_boundaries(self):
        self.check(2_000, 1_500, 500, "flat")
        self.check(9_999, 1_500, 8_499, "flat")
        self.check(10_000, 1_500, 8_500, "pct15")  # exactly ₦10,000 -> 15%
        self.check(19_999, 3_000, 16_999, "pct15")  # 2,999.85 rounds to 3,000
        self.check(20_000, 2_000, 18_000, "pct10")  # exactly ₦20,000 -> 10%
        self.check(50_000_000, 5_000_000, 45_000_000, "pct10")

    def test_rounding_to_nearest_naira(self):
        self.assertEqual(calculate_fee(10_003).fee, 1_500)  # 1,500.45 -> 1,500
        self.assertEqual(calculate_fee(10_010).fee, 1_502)  # 1,501.5 -> 1,502 (half up)
        self.assertEqual(calculate_fee(20_005).fee, 2_001)  # 2,000.5 -> 2,001

    def test_rate_labels(self):
        self.assertEqual(calculate_fee(8_000).rate_label, "flat fee")
        self.assertEqual(calculate_fee(19_500).rate_label, "15%")
        self.assertEqual(calculate_fee(185_000).rate_label, "10%")

    def test_flat_tip(self):
        self.assertEqual(
            calculate_fee(8_000).tip, "Items under ₦10,000 have a flat ₦1,500 fee. That’s 19% of this price."
        )

    def test_next_tier_tip(self):
        self.assertEqual(
            calculate_fee(19_500).tip,
            "At ₦20,000 the fee drops to 10%, so you’d receive ₦18,000 (₦1,425 more than now).",
        )
        self.assertIsNotNone(calculate_fee(17_000).tip)

    def test_no_tip(self):
        self.assertIsNone(calculate_fee(16_999).tip)  # below the tip threshold
        self.assertIsNone(calculate_fee(10_000).tip)
        for price in (20_000, 25_000, 185_000):
            self.assertIsNone(calculate_fee(price).tip, price)


class FeeEndpointTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.client.force_login(make_user("+2348031234567"))

    def test_quote(self):
        res = self.client.get("/api/listings/fee-quote/?price=19500")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            res.json(),
            {
                "price": 19_500,
                "fee": 2_925,
                "payout": 16_575,
                "tier_key": "pct15",
                "rate_label": "15%",
                "tip": "At ₦20,000 the fee drops to 10%, so you’d receive ₦18,000 (₦1,425 more than now).",
            },
        )

    def test_invalid_prices(self):
        below = self.client.get("/api/listings/fee-quote/?price=1999").json()
        self.assertEqual((below["code"], below["tier_key"]), ("below_minimum", "flat"))
        self.assertEqual(
            self.client.get("/api/listings/fee-quote/?price=1999").json()["detail"], "Minimum price is ₦2,000."
        )
        self.assertEqual(self.client.get("/api/listings/fee-quote/?price=50000001").json()["code"], "above_maximum")
        for bad in ("", "abc", "12.5", "-3"):
            self.assertEqual(self.client.get(f"/api/listings/fee-quote/?price={bad}").status_code, 400, bad)

    def test_quote_requires_login_schedule_is_public(self):
        anon = APIClient()
        self.assertEqual(anon.get("/api/listings/fee-quote/?price=5000").status_code, 403)
        body = anon.get("/api/listings/fee-schedule/").json()
        self.assertEqual([t["label"] for t in body["tiers"]], ["Under ₦10,000", "₦10,000 – ₦19,999", "₦20,000 and above"])
        self.assertEqual(body["min_price"], 2_000)

    def test_quote_is_throttled_per_user(self):
        codes = [self.client.get("/api/listings/fee-quote/?price=5000").status_code for _ in range(61)]
        self.assertEqual(codes.count(200), 60)
        self.assertEqual(codes[-1], 429)


class LandingFeeFileTests(SimpleTestCase):
    def test_generated_file_matches_backend(self):
        """If this fails, run `python manage.py export_fee_schedule` and commit the file."""
        current = export_fee_schedule.OUTPUT.read_text(encoding="utf-8")
        self.assertEqual(json.loads(current), json.loads(export_fee_schedule.render()))
