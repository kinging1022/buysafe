"""The minute jobs, for dev without Celery beat (or cron in a pinch):
expire payment holds, retry transfers, expire offers, deal deadlines and
reminders.

    manage.py run_sweeps            # once
    manage.py run_sweeps --every 60 # forever
"""

import time

from django.core.management.base import BaseCommand

from apps.deals.services import sweep
from apps.offers.services import expire_offers
from apps.payments.services import expire_holds, retry_transfers


class Command(BaseCommand):
    help = "Run the minute sweeps (payments, offers, deals)."

    def add_arguments(self, parser):
        parser.add_argument("--every", type=int, default=0, help="Repeat every N seconds.")

    def handle(self, *args, **opts):
        while True:
            result = {
                "holds_expired": expire_holds(),
                "transfers_retried": retry_transfers(),
                "offers_expired": expire_offers(),
                **sweep(),
            }
            self.stdout.write(str(result))
            if not opts["every"]:
                break
            time.sleep(opts["every"])
