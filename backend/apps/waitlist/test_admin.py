import csv
import io

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import WaitlistSignup

CHANGELIST = reverse('admin:waitlist_waitlistsignup_changelist')


class WaitlistAdminTests(TestCase):
    def setUp(self):
        admin = get_user_model().objects.create_superuser(
            '+2348000000001', 'Safe2buy1', first_name='Ada', last_name='Obi'
        )
        self.client.force_login(admin)
        self.a = WaitlistSignup.objects.create(phone='+2348031234567', state='lagos', role='buy',
                                               utm_source='ig')
        self.b = WaitlistSignup.objects.create(phone='+2347012345678', state='lagos', role='vendor',
                                               notified_at=timezone.now())
        self.c = WaitlistSignup.objects.create(phone='+2349012345678', state='kano', role='sell')

    def test_export_csv_action(self):
        r = self.client.post(CHANGELIST, {
            'action': 'export_csv',
            '_selected_action': [self.a.pk, self.c.pk],
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'text/csv')
        self.assertIn('attachment; filename="waitlist-', r['Content-Disposition'])
        rows = list(csv.reader(io.StringIO(r.content.decode())))
        self.assertEqual(rows[0][:4], ['phone', 'state', 'role', 'source'])
        self.assertEqual([row[0] for row in rows[1:]], ['+2348031234567', '+2349012345678'])
        self.assertEqual(rows[1][4], 'ig')

    def test_changelist_shows_counts_by_state(self):
        r = self.client.get(CHANGELIST)
        self.assertEqual(r.status_code, 200)
        counts = {row['label']: row['n'] for row in r.context['state_counts']}
        self.assertEqual(counts, {'Lagos': 2, 'Kano': 1})
        self.assertContains(r, 'Signups by state')

    def test_counts_follow_filters(self):
        r = self.client.get(CHANGELIST, {'role': 'vendor'})
        self.assertEqual({row['state']: row['n'] for row in r.context['state_counts']}, {'lagos': 1})

    def test_notified_filter(self):
        r = self.client.get(CHANGELIST, {'notified': 'yes'})
        self.assertEqual(list(r.context['cl'].queryset), [self.b])
        r = self.client.get(CHANGELIST, {'notified': 'no'})
        self.assertEqual(set(r.context['cl'].queryset), {self.a, self.c})

    def test_search_accepts_local_format(self):
        r = self.client.get(CHANGELIST, {'q': '0803 123 4567'})
        self.assertEqual(list(r.context['cl'].queryset), [self.a])
