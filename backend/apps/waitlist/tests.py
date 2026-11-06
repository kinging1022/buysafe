from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .models import WaitlistSignup

URL = reverse('waitlist-signup')


class WaitlistApiTests(TestCase):
    def setUp(self):
        cache.clear()  # throttle history lives in the cache
        self.client = APIClient()

    def post(self, **overrides):
        payload = {'phone': '0803 123 4567', 'state': 'lagos', 'role': 'buy'}
        payload.update(overrides)
        return self.client.post(URL, payload, format='json')

    def test_valid_signup_creates_row(self):
        r = self.post(source='buysafe.ng', utm_source='ig', utm_medium='story', utm_campaign='launch')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {'ok': True})
        s = WaitlistSignup.objects.get()
        self.assertEqual(s.phone, '+2348031234567')
        self.assertEqual((s.state, s.role, s.source), ('lagos', 'buy', 'buysafe.ng'))
        self.assertEqual((s.utm_source, s.utm_medium, s.utm_campaign), ('ig', 'story', 'launch'))
        self.assertIsNone(s.notified_at)

    def test_role_defaults_to_buy(self):
        r = self.client.post(URL, {'phone': '08031234567', 'state': 'lagos'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(WaitlistSignup.objects.get().role, 'buy')

    def test_same_phone_twice_upserts(self):
        r1 = self.post(state='lagos', role='buy', source='first')
        r2 = self.post(phone='+234 803 123 4567', state='kano', role='vendor', source='second')
        self.assertEqual((r1.status_code, r2.status_code), (200, 200))
        self.assertEqual(r1.json(), r2.json())
        s = WaitlistSignup.objects.get()
        self.assertEqual((s.state, s.role), ('kano', 'vendor'))
        self.assertEqual(s.source, 'first')  # original attribution kept

    def test_phone_normalisation(self):
        for raw in ['08031234567', '8031234567', '+2348031234567', '2348031234567',
                    '0803 123 4567', '0803-123-4567', '+234 (803) 123-4567', '+234 0803 123 4567']:
            with self.subTest(raw=raw):
                cache.clear()
                WaitlistSignup.objects.all().delete()
                self.assertEqual(self.post(phone=raw).status_code, 200)
                self.assertEqual(WaitlistSignup.objects.get().phone, '+2348031234567')

    def test_other_valid_prefixes(self):
        for raw, expected in [('07012345678', '+2347012345678'), ('09112345678', '+2349112345678'),
                              ('08101234567', '+2348101234567')]:
            with self.subTest(raw=raw):
                cache.clear()
                self.assertEqual(self.post(phone=raw).status_code, 200)
                self.assertTrue(WaitlistSignup.objects.filter(phone=expected).exists())

    def test_invalid_numbers_rejected(self):
        for raw in ['01 234 5678', '012345678', '0803123456', '080312345678', '6031234567',
                    '06031234567', '08231234567', '', 'not a number']:
            with self.subTest(raw=raw):
                cache.clear()
                r = self.post(phone=raw)
                self.assertEqual(r.status_code, 400)
                self.assertIn('phone', r.json())
        self.assertFalse(WaitlistSignup.objects.exists())

    def test_invalid_state_rejected(self):
        for state in ['Lagos', 'lagos_state', 'Abuja (FCT)', '']:
            with self.subTest(state=state):
                r = self.post(state=state)
                self.assertEqual(r.status_code, 400)
                self.assertIn('state', r.json())
        r = self.client.post(URL, {'phone': '08031234567'}, format='json')
        self.assertIn('state', r.json())
        self.assertFalse(WaitlistSignup.objects.exists())

    def test_invalid_role_rejected(self):
        r = self.post(role='admin')
        self.assertEqual(r.status_code, 400)
        self.assertIn('role', r.json())
        self.assertFalse(WaitlistSignup.objects.exists())

    def test_honeypot_returns_ok_without_saving(self):
        r = self.post(company='Acme Ltd')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {'ok': True})
        self.assertFalse(WaitlistSignup.objects.exists())

    def test_empty_honeypot_is_fine(self):
        self.assertEqual(self.post(company='').status_code, 200)
        self.assertTrue(WaitlistSignup.objects.exists())

    def test_long_attribution_is_truncated(self):
        self.assertEqual(self.post(source='x' * 500, utm_campaign='y' * 500).status_code, 200)
        s = WaitlistSignup.objects.get()
        self.assertEqual((len(s.source), len(s.utm_campaign)), (200, 100))

    def test_throttle_per_minute(self):
        for i in range(5):
            self.assertEqual(self.post(phone=f'080312345{i:02d}').status_code, 200)
        self.assertEqual(self.post(phone='08031234599').status_code, 429)

    def test_throttle_is_per_ip(self):
        for i in range(5):
            self.client.post(URL, {'phone': f'080312345{i:02d}', 'state': 'lagos'}, format='json',
                             REMOTE_ADDR='10.0.0.1')
        blocked = self.client.post(URL, {'phone': '08031234599', 'state': 'lagos'}, format='json',
                                   REMOTE_ADDR='10.0.0.1')
        other = self.client.post(URL, {'phone': '08031234599', 'state': 'lagos'}, format='json',
                                 REMOTE_ADDR='10.0.0.2')
        self.assertEqual((blocked.status_code, other.status_code), (429, 200))

    def test_csrf_not_required(self):
        client = APIClient(enforce_csrf_checks=True)
        r = client.post(URL, {'phone': '08031234567', 'state': 'lagos'}, format='json')
        self.assertEqual(r.status_code, 200)

    def test_fct_key(self):
        self.assertEqual(self.post(state='fct').status_code, 200)
        self.assertEqual(WaitlistSignup.objects.get().get_state_display(), 'Abuja (FCT)')

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get(URL).status_code, 405)
