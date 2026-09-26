from django.urls import path

from .views import ChangePasswordView, MeView

# Mounted at /api/me/.
urlpatterns = [
    path("", MeView.as_view(), name="me"),
    path("password/", ChangePasswordView.as_view(), name="me-password"),
]
