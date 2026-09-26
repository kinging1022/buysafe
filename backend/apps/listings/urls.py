from django.urls import path

from .views import MyListingStatsView, MyListingsView

# Mounted at /api/me/.
urlpatterns = [
    path("listings/", MyListingsView.as_view(), name="my-listings"),
    path("listing-stats/", MyListingStatsView.as_view(), name="my-listing-stats"),
]
