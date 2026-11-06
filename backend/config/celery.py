"""Celery app. Tasks live in each app's tasks.py; the schedule is
CELERY_BEAT_SCHEDULE in settings."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
