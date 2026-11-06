from django.urls import path

from .views import MarkAllReadView, MarkReadView, NotificationsView, UnreadCountView

# Mounted at /api/notifications/.
urlpatterns = [
    path("", NotificationsView.as_view(), name="notifications"),
    path("unread-count/", UnreadCountView.as_view(), name="notifications-unread-count"),
    path("read-all/", MarkAllReadView.as_view(), name="notifications-read-all"),
    path("<int:pk>/read/", MarkReadView.as_view(), name="notification-read"),
]
