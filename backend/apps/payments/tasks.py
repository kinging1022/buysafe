from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from . import reconciliation, services
from .reconciliation import LAGOS


@shared_task
def expire_holds():
    return services.expire_holds()


@shared_task
def retry_transfers():
    return services.retry_transfers()


@shared_task(autoretry_for=(ConnectionError,), retry_backoff=True, max_retries=5)
def send_refund(refund_id):
    services.send_refund(refund_id)


@shared_task(autoretry_for=(ConnectionError,), retry_backoff=True, max_retries=5)
def send_payout(payout_id):
    services.send_payout(payout_id)


@shared_task(autoretry_for=(ConnectionError,), retry_backoff=True, max_retries=5)
def send_fee(fee_id):
    services.send_fee(fee_id)


@shared_task
def reconcile():
    """Yesterday, Lagos time."""
    yesterday = (timezone.now().astimezone(LAGOS) - timedelta(days=1)).date()
    return reconciliation.reconcile(yesterday)
