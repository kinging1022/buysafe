from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification
from .serializers import NotificationSerializer


class NotificationsPagination(PageNumberPagination):
    page_size = 30


class NotificationsView(ListAPIView):
    """GET /api/notifications/?page= : the signed-in user's notifications, newest first."""

    serializer_class = NotificationSerializer
    pagination_class = NotificationsPagination

    def get_queryset(self):
        return Notification.objects.visible().filter(user=self.request.user)


class UnreadCountView(APIView):
    """GET /api/notifications/unread-count/ -> {count}. Polled every 30s by the header."""

    def get(self, request):
        count = Notification.objects.visible().filter(user=request.user, read_at__isnull=True).count()
        return Response({"count": count})


class MarkReadView(APIView):
    """POST /api/notifications/{id}/read/"""

    def post(self, request, pk):
        notification = get_object_or_404(Notification.objects.visible(), pk=pk, user=request.user)
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at"])
        return Response(NotificationSerializer(notification).data)


class MarkAllReadView(APIView):
    """POST /api/notifications/read-all/ -> {count} marked."""

    def post(self, request):
        count = (
            Notification.objects.visible()
            .filter(user=request.user, read_at__isnull=True)
            .update(read_at=timezone.now())
        )
        return Response({"count": count})
