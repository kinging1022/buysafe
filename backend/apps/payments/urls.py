from django.urls import path

from .views import (
    BanksView,
    ListingPayView,
    PaymentCancelView,
    PaymentIntentView,
    PayoutAccountView,
    PayoutLookupView,
    TransferWebhookView,
)

# Mounted at /api/.
urlpatterns = [
    path("listings/<int:pk>/pay/", ListingPayView.as_view(), name="listing-pay"),
    path("payments/banks/", BanksView.as_view(), name="payment-banks"),
    path("payments/webhooks/anchor/", TransferWebhookView.as_view(), name="payment-webhook"),
    path("payments/<int:pk>/", PaymentIntentView.as_view(), name="payment-intent"),
    path("payments/<int:pk>/cancel/", PaymentCancelView.as_view(), name="payment-cancel"),
    path("me/payout-account/", PayoutAccountView.as_view(), name="payout-account"),
    path("me/payout-account/lookup/", PayoutLookupView.as_view(), name="payout-lookup"),
]
