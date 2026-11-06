from django.core.management.base import BaseCommand

from apps.offers.services import expire_offers


class Command(BaseCommand):
    help = "Expire pending offers past their 48h. Run every minute (cron)."

    def handle(self, *args, **options):
        self.stdout.write(f"Expired {expire_offers()} offer(s).")
