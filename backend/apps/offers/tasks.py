from celery import shared_task

from . import services


@shared_task
def expire_offers():
    return services.expire_offers()
