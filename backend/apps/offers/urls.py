from django.urls import path

from .views import ListingOffersView, OfferAcceptView, OfferDeclineView, OfferUndoDeclineView, OfferWithdrawView

# Mounted at /api/.
urlpatterns = [
    path("listings/<int:pk>/offers/", ListingOffersView.as_view(), name="listing-offers"),
    path("offers/<int:pk>/withdraw/", OfferWithdrawView.as_view(), name="offer-withdraw"),
    path("offers/<int:pk>/decline/", OfferDeclineView.as_view(), name="offer-decline"),
    path("offers/<int:pk>/accept/", OfferAcceptView.as_view(), name="offer-accept"),
    path("offers/<int:pk>/undo-decline/", OfferUndoDeclineView.as_view(), name="offer-undo-decline"),
]
