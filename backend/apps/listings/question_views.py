"""Public Q&A on a listing. Views call questions.py; they never set a status."""

from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle, SimpleRateThrottle
from rest_framework.views import APIView

from apps.users.permissions import IsVerifiedUser

from . import questions
from . import status as listing_status
from .models import Listing, ListingQuestion


class QuestionIpThrottle(SimpleRateThrottle):
    """Second layer on posting questions: per IP, whoever is signed in."""

    scope = "questions_ip"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class QuestionSerializer(serializers.ModelSerializer):
    asker = serializers.SerializerMethodField()
    edited = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = ListingQuestion
        fields = ["id", "text", "asker", "created_at", "answer", "answered_at", "edited", "status", "is_mine"]
        read_only_fields = fields

    def get_asker(self, question):
        return {"first_name": question.asker.first_name, "last_initial": question.asker.last_name[:1].upper()}

    def get_edited(self, question):
        return question.answer_edited_at is not None

    def get_is_mine(self, question):
        user = self.context.get("user")
        return bool(user and user.is_authenticated and question.asker_id == user.pk)


def _error(err):
    return Response(err.as_dict(), status=err.status)


def _page(request):
    raw = request.query_params.get("page", "1")
    return int(raw) if raw.isdigit() and int(raw) > 0 else 1


class ListingQuestionsView(APIView):
    """GET /api/listings/{id}/questions/?page= (anyone): answered questions
    (10 a page, newest answered first), plus the viewer's own pending ones, or
    every pending one for the owner, and `meta`. POST (verified buyer): ask."""

    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [IsVerifiedUser()]

    def get_throttles(self):
        if self.request.method != "POST":
            return []
        self.throttle_scope = "questions"
        return [ScopedRateThrottle(), QuestionIpThrottle()]

    def get_listing(self, request, pk):
        listing = get_object_or_404(
            listing_status.with_display_status(Listing.objects.all()), pk=pk
        )
        is_owner = request.user.is_authenticated and listing.seller_id == request.user.pk
        if not is_owner and listing.display_status in (listing_status.PENDING, listing_status.REJECTED):
            raise Http404
        return listing, is_owner

    def get(self, request, pk):
        listing, is_owner = self.get_listing(request, pk)
        user = request.user
        pending, answered = questions.visible_questions(listing, user)
        page = _page(request)
        start = (page - 1) * questions.PAGE_SIZE
        answered_page = list(answered[start : start + questions.PAGE_SIZE + 1])
        has_more = len(answered_page) > questions.PAGE_SIZE
        ask = questions.ask_status(listing, user)
        context = {"user": user}
        return Response(
            {
                "meta": {
                    "public_count": answered.count(),
                    "pending_count": pending.count() if is_owner else None,
                    "questions_left_today": ask["questions_left_today"],
                    "can_ask": ask["can_ask"],
                    "reason": ask["reason"],
                    "retry_at": ask["retry_at"],
                    "is_owner": is_owner,
                },
                "pending": QuestionSerializer(pending, many=True, context=context).data if page == 1 else [],
                "answered": QuestionSerializer(answered_page[: questions.PAGE_SIZE], many=True, context=context).data,
                "next_page": page + 1 if has_more else None,
            }
        )

    def post(self, request, pk):
        listing, _ = self.get_listing(request, pk)
        try:
            question = questions.ask_question(listing, request.user, request.data.get("text"))
        except questions.QuestionError as err:
            return _error(err)
        return Response(QuestionSerializer(question, context={"user": request.user}).data, status=status.HTTP_201_CREATED)


class _OwnerQuestionView(APIView):
    def get_question(self, request, pk):
        return get_object_or_404(ListingQuestion, pk=pk, listing__seller=request.user)

    def respond(self, request, fn, *args):
        try:
            question = fn(self.get_question(request, self.kwargs["pk"]), request.user, *args)
        except questions.QuestionError as err:
            return _error(err)
        return Response(QuestionSerializer(question, context={"user": request.user}).data)


class QuestionAnswerView(_OwnerQuestionView):
    """POST /api/questions/{id}/answer/ (owner, once). PATCH: edit the answer."""

    def post(self, request, pk):
        return self.respond(request, questions.answer_question, request.data.get("answer"))

    def patch(self, request, pk):
        return self.respond(request, questions.edit_answer, request.data.get("answer"))


class QuestionRemoveView(_OwnerQuestionView):
    """POST /api/questions/{id}/remove/ (owner): remove as spam; undo within 60s."""

    def post(self, request, pk):
        return self.respond(request, questions.remove_question)


class QuestionRestoreView(_OwnerQuestionView):
    """POST /api/questions/{id}/restore/ (owner), within 60s of removing."""

    def post(self, request, pk):
        return self.respond(request, questions.restore_question)
