from rest_framework import serializers

from .kinds import render
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    """id, kind, category, label, title_text, target_url, created_at, read_at.
    `created_at` is when it became visible (a decline's, after its Undo window)."""

    created_at = serializers.DateTimeField(source="visible_at")

    class Meta:
        model = Notification
        fields = ["id", "kind", "created_at", "read_at"]
        read_only_fields = fields

    def to_representation(self, notification):
        return {**super().to_representation(notification), **render(notification)}
