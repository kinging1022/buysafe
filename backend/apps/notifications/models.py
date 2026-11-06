from django.conf import settings
from django.db import models
from django.utils import timezone


class NotificationQuerySet(models.QuerySet):
    def visible(self, now=None):
        """Only notifications whose `visible_at` has passed. A delayed one (a
        decline, during its Undo window) appears on its own, with no worker."""
        return self.filter(visible_at__lte=now or timezone.now())


class Notification(models.Model):
    """Something a user is told about in the app (the Notifications page).
    What it says and links to comes from its `kind` (see kinds.py), rendered
    from `data` when read; `data` holds a snapshot (amounts, titles, names),
    never a phone number."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    # A key in kinds.KINDS. Not a DB choice, so adding a kind needs no migration.
    kind = models.CharField(max_length=40)
    data = models.JSONField(default=dict, blank=True)
    # What created it, e.g. "offer:12:declined", so the action can be undone
    # (the notification deleted) before it's seen.
    ref = models.CharField(max_length=60, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    visible_at = models.DateTimeField(default=timezone.now)
    read_at = models.DateTimeField(null=True, blank=True)

    objects = NotificationQuerySet.as_manager()

    class Meta:
        ordering = ["-visible_at", "-id"]
        indexes = [models.Index(fields=["user", "-visible_at"]), models.Index(fields=["user", "read_at"])]

    def __str__(self):
        return f"{self.kind} for {self.user_id}"
