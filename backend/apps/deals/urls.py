from django.urls import path

from .views import (
    ConfirmReceiptView,
    DealBadgeView,
    DealDetailView,
    DealMessagesView,
    DealsView,
    DealVideosView,
    DecideView,
    MeetupConfirmView,
    MeetupsView,
    PhotoFileView,
    RateVideoView,
    ReportView,
    VideoFileView,
    VideoUploadChunkView,
)

# Mounted at /api/deals/.
urlpatterns = [
    path("", DealsView.as_view(), name="deals"),
    path("badge/", DealBadgeView.as_view(), name="deals-badge"),
    path("uploads/<str:token>/", VideoUploadChunkView.as_view(), name="deal-video-upload"),
    path("<int:pk>/", DealDetailView.as_view(), name="deal"),
    path("<int:pk>/messages/", DealMessagesView.as_view(), name="deal-messages"),
    path("<int:pk>/messages/<int:mid>/photo/", PhotoFileView.as_view(), name="deal-message-photo"),
    path("<int:pk>/videos/", DealVideosView.as_view(), name="deal-videos"),
    path("<int:pk>/videos/<int:n>/file/", VideoFileView.as_view(), name="deal-video-file"),
    path("<int:pk>/videos/<int:n>/thumb/", VideoFileView.as_view(), {"part": "thumb"}, name="deal-video-thumb"),
    path("<int:pk>/videos/<int:n>/rate/", RateVideoView.as_view(), name="deal-video-rate"),
    path("<int:pk>/after-third-bad/", DecideView.as_view(), name="deal-decide"),
    path("<int:pk>/meetups/", MeetupsView.as_view(), name="deal-meetups"),
    path("<int:pk>/meetups/<int:mid>/confirm/", MeetupConfirmView.as_view(), name="deal-meetup-confirm"),
    path("<int:pk>/confirm-receipt/", ConfirmReceiptView.as_view(), name="deal-confirm-receipt"),
    path("<int:pk>/report/", ReportView.as_view(), name="deal-report"),
]
