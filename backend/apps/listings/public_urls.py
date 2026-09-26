from django.urls import path

from .views import (
    CategoriesView,
    FacetsView,
    FeeQuoteView,
    FeeScheduleView,
    ListingDetailView,
    ListingsView,
)

# Mounted at /api/.
urlpatterns = [
    path("listings/", ListingsView.as_view(), name="listings"),
    path("listings/facets/", FacetsView.as_view(), name="listing-facets"),
    path("listings/fee-quote/", FeeQuoteView.as_view(), name="fee-quote"),
    path("listings/fee-schedule/", FeeScheduleView.as_view(), name="fee-schedule"),
    path("listings/<int:pk>/", ListingDetailView.as_view(), name="listing-detail"),
    path("categories/", CategoriesView.as_view(), name="categories"),
]
