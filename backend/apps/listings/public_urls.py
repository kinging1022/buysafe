from django.urls import path

from .question_views import ListingQuestionsView, QuestionAnswerView, QuestionRemoveView, QuestionRestoreView
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
    path("listings/<int:pk>/questions/", ListingQuestionsView.as_view(), name="listing-questions"),
    path("questions/<int:pk>/answer/", QuestionAnswerView.as_view(), name="question-answer"),
    path("questions/<int:pk>/remove/", QuestionRemoveView.as_view(), name="question-remove"),
    path("questions/<int:pk>/restore/", QuestionRestoreView.as_view(), name="question-restore"),
    path("categories/", CategoriesView.as_view(), name="categories"),
]
