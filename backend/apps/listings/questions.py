"""Public questions on a listing: one function per change. Views call these
and never set a status themselves.

    (none)   -> pending   ask_question      a buyer asks; the owner is notified
    pending  -> answered  answer_question   the owner answers once; the asker is notified
    answered -> answered  edit_answer       the owner edits; the old answer is kept
    any      -> removed   remove_question   the owner removes it as spam (no notification)
    removed  -> previous  restore_question  within 60s of removing

Visibility: answered questions are public; a pending one is seen only by its
asker and the owner; a removed one by no one. Contact details are refused in
questions and answers (contact_guard).
"""

from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.notifications.services import notify

from . import contact_guard
from . import status as listing_status
from .models import Listing, ListingQuestion, ListingQuestionEdit

Status = ListingQuestion.Status

QUESTION_MIN, QUESTION_MAX = 5, 280
ANSWER_MIN, ANSWER_MAX = 2, 500
# Per buyer, per listing, in any rolling 24 hours. Removed questions count.
DAILY_LIMIT = 3
LIMIT_WINDOW = timedelta(hours=24)
RESTORE_WINDOW = timedelta(seconds=60)
PAGE_SIZE = 10

CONTACT_MESSAGE = "Contact details can’t be shared before payment."


class QuestionError(Exception):
    """A rule was broken. `status` is the HTTP status the view returns."""

    def __init__(self, code, detail, status=400, **extra):
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status = status
        self.extra = extra

    def as_dict(self):
        return {"code": self.code, "detail": self.detail, **self.extra}


def public_name(user):
    return f"{user.first_name} {user.last_name[:1].upper()}."


def _clean(text, low, high, what):
    text = (text or "").strip()
    if len(text) < low:
        raise QuestionError("too_short", f"Your {what} is too short.")
    if len(text) > high:
        raise QuestionError("too_long", f"Keep your {what} under {high} characters.")
    kind = contact_guard.find_contact(text)
    if kind:
        raise QuestionError("contact_details", CONTACT_MESSAGE, kind=kind)
    return text


# ---------------------------------------------------------------------------
# Who can ask


def _recent_questions(listing, user, now):
    return ListingQuestion.objects.filter(listing=listing, asker=user, created_at__gt=now - LIMIT_WINDOW)


def ask_status(listing, user, now=None) -> dict:
    """{can_ask, reason, questions_left_today, retry_at} for this viewer.
    reason: login_required | own_listing | not_live | question_limit | None."""
    now = now or timezone.now()
    result = {"can_ask": False, "reason": None, "questions_left_today": None, "retry_at": None}
    if not user.is_authenticated:
        result["reason"] = "login_required"
        return result
    if listing.seller_id == user.pk:
        result["reason"] = "own_listing"
        return result
    recent = list(_recent_questions(listing, user, now).order_by("created_at").values_list("created_at", flat=True))
    left = max(0, DAILY_LIMIT - len(recent))
    result["questions_left_today"] = left
    if listing_status.listing_display_status(listing) != listing_status.LIVE:
        result["reason"] = "not_live"
        return result
    if not left:
        result["reason"] = "question_limit"
        result["retry_at"] = recent[len(recent) - DAILY_LIMIT] + LIMIT_WINDOW
        return result
    result["can_ask"] = True
    return result


# ---------------------------------------------------------------------------
# Changes


def ask_question(listing: Listing, user, text: str) -> ListingQuestion:
    text = _clean(text, QUESTION_MIN, QUESTION_MAX, "question")
    with transaction.atomic():
        # Lock the listing so two quick submissions can't both slip under the limit.
        listing = Listing.objects.select_for_update().get(pk=listing.pk)
        status = ask_status(listing, user)
        if not status["can_ask"]:
            reason = status["reason"]
            if reason == "question_limit":
                raise QuestionError(
                    "question_limit",
                    f"You can ask {DAILY_LIMIT} questions a day on this listing.",
                    status=429,
                    retry_at=status["retry_at"].isoformat(),
                )
            if reason == "own_listing":
                raise QuestionError("own_listing", "You can’t ask about your own listing.", status=403)
            raise QuestionError("not_live", "This listing isn’t taking questions.", status=409)
        question = ListingQuestion.objects.create(listing=listing, asker=user, text=text)
        notify(
            listing.seller,
            "question_new",
            {"listing_id": listing.pk, "listing_title": listing.title, "asker_name": public_name(user)},
            ref=f"question:{question.pk}:new",
        )
    return question


def _lock_for_owner(question, owner):
    question = ListingQuestion.objects.select_for_update().select_related("listing", "asker").get(pk=question.pk)
    if question.listing.seller_id != owner.pk:
        raise QuestionError("not_found", "Not found.", status=404)
    return question


def answer_question(question: ListingQuestion, owner, text: str) -> ListingQuestion:
    text = _clean(text, ANSWER_MIN, ANSWER_MAX, "answer")
    with transaction.atomic():
        question = _lock_for_owner(question, owner)
        if question.status != Status.PENDING:
            raise QuestionError("not_pending", "This question already has an answer.", status=409)
        question.answer = text
        question.answered_at = timezone.now()
        question.status = Status.ANSWERED
        question.save(update_fields=["answer", "answered_at", "status"])
        notify(
            question.asker,
            "question_answered",
            {
                "listing_id": question.listing_id,
                "listing_title": question.listing.title,
                "seller_first_name": owner.first_name,
            },
            ref=f"question:{question.pk}:answered",
        )
    return question


def edit_answer(question: ListingQuestion, owner, text: str) -> ListingQuestion:
    text = _clean(text, ANSWER_MIN, ANSWER_MAX, "answer")
    with transaction.atomic():
        question = _lock_for_owner(question, owner)
        if question.status != Status.ANSWERED:
            raise QuestionError("not_answered", "Only an answered question can be edited.", status=409)
        if text == question.answer:
            return question
        ListingQuestionEdit.objects.create(question=question, previous_answer=question.answer)
        question.answer = text
        question.answer_edited_at = timezone.now()
        question.save(update_fields=["answer", "answer_edited_at"])
    return question


def remove_question(question: ListingQuestion, owner) -> ListingQuestion:
    """Soft delete as spam. No notification to the asker."""
    with transaction.atomic():
        question = _lock_for_owner(question, owner)
        if question.status == Status.REMOVED:
            raise QuestionError("already_removed", "This question was already removed.", status=409)
        question.status = Status.REMOVED
        question.removed_at = timezone.now()
        question.removed_by = owner
        question.save(update_fields=["status", "removed_at", "removed_by"])
    return question


def restore_question(question: ListingQuestion, owner) -> ListingQuestion:
    with transaction.atomic():
        question = _lock_for_owner(question, owner)
        if question.status != Status.REMOVED:
            raise QuestionError("not_removed", "This question isn’t removed.", status=409)
        if question.removed_at + RESTORE_WINDOW <= timezone.now():
            raise QuestionError("too_late", "It’s too late to undo.", status=409)
        question.status = Status.ANSWERED if question.answer else Status.PENDING
        question.removed_at = None
        question.removed_by = None
        question.save(update_fields=["status", "removed_at", "removed_by"])
    return question


# ---------------------------------------------------------------------------
# Reading


def visible_questions(listing, user):
    """(pending, answered) querysets this viewer may see."""
    base = ListingQuestion.objects.filter(listing=listing).select_related("asker")
    answered = base.filter(status=Status.ANSWERED).order_by("-answered_at", "-id")
    if not user.is_authenticated:
        pending = base.none()
    elif listing.seller_id == user.pk:
        pending = base.filter(status=Status.PENDING).order_by("created_at", "id")
    else:
        pending = base.filter(status=Status.PENDING, asker=user).order_by("-created_at", "-id")
    return pending, answered
