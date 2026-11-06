"""The deals API. Everything is for the deal's buyer and seller only: anyone
else gets a 404, as if the deal didn't exist."""

from __future__ import annotations

import mimetypes
import os
import re
import uuid
from datetime import timedelta

from django.core import signing
from django.db.models import Case, F, IntegerField, Q, Value, When
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from . import media, rules, services
from .models import Deal, LiveVideo, Message, VideoUpload
from .serializers import deal_data, deal_row, messages_data
from .storage import private_storage

UPLOAD_SALT = "deal-video-upload"
UPLOAD_MAX_AGE = 30 * 60  # seconds a signed upload URL works for

TABS = {
    "active": Deal.ACTIVE,
    "completed": [Deal.State.RELEASED],
    "refunded": [Deal.State.REFUNDED],
}


def error_response(err: services.DealError):
    return Response(err.as_dict(), status=err.status)


def my_deals(user):
    return Deal.objects.filter(Q(buyer=user) | Q(seller=user))


def get_deal(request, pk) -> Deal:
    return get_object_or_404(
        my_deals(request.user).select_related("listing", "buyer", "seller", "inbound", "refund"), pk=pk
    )


class DealsView(APIView):
    """GET /api/deals/?tab=active|completed|refunded -> {counts, results}.
    Active: deals waiting on you first, then by deadline."""

    def get(self, request):
        tab = request.query_params.get("tab", "active")
        if tab not in TABS:
            tab = "active"
        user = request.user
        mine = my_deals(user)
        counts = {name: mine.filter(state__in=states).count() for name, states in TABS.items()}
        deals = (
            mine.filter(state__in=TABS[tab])
            .select_related("listing", "buyer", "seller", "inbound", "refund", "payout_transfer")
            .prefetch_related("listing__photos", "messages", "meetups")
        )
        if tab == "active":
            deals = deals.annotate(
                my_turn=Case(
                    When(Q(seller=user, state=Deal.State.AWAITING_VIDEO), then=Value(0)),
                    When(Q(buyer=user, state__in=[Deal.State.VIDEO_TO_RATE, Deal.State.AWAITING_DECISION]), then=Value(0)),
                    default=Value(1),
                    output_field=IntegerField(),
                )
            ).order_by("my_turn", F("current_deadline").asc(nulls_last=True), "-created_at")
        elif tab == "completed":
            deals = deals.order_by("-released_at")
        else:
            deals = deals.order_by("-refunded_at")
        now = timezone.now()
        return Response({"counts": counts, "results": [deal_row(d, user, now) for d in deals]})


class DealBadgeView(APIView):
    """GET /api/deals/badge/ -> {count}: unread messages plus deals waiting on you."""

    def get(self, request):
        return Response({"count": services.attention_count(request.user)})


class DealDetailView(APIView):
    """GET /api/deals/{id}/. Polled every 5s by the deal page."""

    def get(self, request, pk):
        deal = get_deal(request, pk)
        return Response(deal_data(deal, request.user))


class DealMessagesView(APIView):
    """GET /api/deals/{id}/messages/: the whole chat, oldest first (marks the
    other person's messages read). POST {body} or multipart {photo}."""

    parser_classes = [JSONParser, MultiPartParser, FormParser]
    throttle_scope = "deal_messages"

    def get_throttles(self):
        return super().get_throttles() if self.request.method == "POST" else []

    def get(self, request, pk):
        deal = get_deal(request, pk)
        services.mark_read(deal, request.user)
        return Response({"results": messages_data(deal, request.user)})

    def post(self, request, pk):
        deal = get_deal(request, pk)
        try:
            services.send_message(deal, request.user, body=request.data.get("body", ""), photo=request.FILES.get("photo"))
        except services.DealError as err:
            return error_response(err)
        return Response({"results": messages_data(deal, request.user)}, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Live videos: a resumable upload to a signed URL, then "complete".


def _base_mime(value):
    return (value or "").split(";")[0].strip().lower()


class DealVideosView(APIView):
    """POST /api/deals/{id}/videos/
        {action: "init", size, mime, duration, captured_at}
            -> {upload_id, upload_url, chunk_size, offset}
        {action: "complete", upload_id} -> the new video
    Only the seller, only while the deal waits for a video. The file must
    come from the in-app camera: it has to have been recorded in the last
    5 minutes (by its container's creation time when it has one)."""

    def post(self, request, pk):
        deal = get_deal(request, pk)
        if deal.role_of(request.user) != "seller" or deal.state != Deal.State.AWAITING_VIDEO:
            return error_response(services.DealError("wrong_state", "There’s no video to send right now."))
        action = request.data.get("action")
        if action == "init":
            return self.init(request, deal)
        if action == "complete":
            return self.complete(request, deal)
        return Response({"code": "invalid", "detail": "Unknown action."}, status=400)

    def init(self, request, deal):
        now = timezone.now()
        mime = _base_mime(request.data.get("mime"))
        try:
            size = int(request.data.get("size"))
            duration = float(request.data.get("duration"))
        except (TypeError, ValueError):
            return Response({"code": "invalid", "detail": "Missing video details."}, status=400)
        captured_at = parse_datetime(str(request.data.get("captured_at", "")))
        if mime not in rules.VIDEO_TYPES or not 0 < size <= rules.MAX_VIDEO_BYTES:
            return Response({"code": "invalid", "detail": "That video can’t be sent."}, status=400)
        if duration < rules.MIN_VIDEO_SECONDS - 0.5:
            return Response({"code": "too_short", "detail": "Videos need at least 20 seconds."}, status=400)
        if duration > rules.MAX_VIDEO_SECONDS + 1:
            return Response({"code": "too_long", "detail": "Videos can be at most 1 minute."}, status=400)
        if captured_at is None or not (now - rules.CAPTURE_MAX_AGE <= captured_at <= now + timedelta(minutes=1)):
            return Response({"code": "stale", "detail": "Record the video again, then send it straight away."}, status=400)
        path = f"uploads/{uuid.uuid4().hex}.part"
        os.makedirs(os.path.dirname(private_storage.path(path)), exist_ok=True)
        open(private_storage.path(path), "wb").close()
        upload = VideoUpload.objects.create(
            deal=deal,
            uploader=request.user,
            n=deal.video_count + 1,
            size=size,
            mime=mime,
            duration=duration,
            captured_at=captured_at,
            path=path,
        )
        token = signing.dumps({"u": upload.pk}, salt=UPLOAD_SALT)
        return Response(
            {
                "upload_id": upload.pk,
                "upload_url": f"/api/deals/uploads/{token}/",
                "chunk_size": rules.UPLOAD_CHUNK_BYTES,
                "offset": 0,
            },
            status=201,
        )

    def complete(self, request, deal):
        upload = VideoUpload.objects.filter(
            pk=request.data.get("upload_id"), deal=deal, uploader=request.user, completed_at__isnull=True
        ).first()
        if upload is None:
            return Response({"code": "not_found", "detail": "Upload not found. Send the video again."}, status=404)
        if upload.received_bytes != upload.size:
            return Response({"code": "incomplete", "detail": "The upload isn’t finished.", "offset": upload.received_bytes}, status=409)
        temp = private_storage.path(upload.path)
        if not media.looks_like_video(temp, upload.mime):
            return Response({"code": "invalid", "detail": "That file isn’t a video."}, status=400)
        created, container_duration = media.container_info(temp, upload.mime)
        # The container's own clock, when it has one, must say "just now"
        # (measured from when the upload started, so slow networks aren't punished).
        if created is not None and not (
            upload.created_at - rules.CAPTURE_MAX_AGE <= created <= upload.created_at + timedelta(minutes=2)
        ):
            return Response({"code": "stale", "detail": "This video wasn’t just recorded. Record it again in the app."}, status=400)
        duration = container_duration or upload.duration
        if not rules.MIN_VIDEO_SECONDS - 0.5 <= duration <= rules.MAX_VIDEO_SECONDS + 1:
            return Response({"code": "bad_length", "detail": "Videos need 20 to 60 seconds."}, status=400)

        ext = {"video/webm": "webm", "video/mp4": "mp4", "video/quicktime": "mov"}[upload.mime]
        now = timezone.now()
        final = f"deal-videos/{now:%Y/%m}/{uuid.uuid4().hex}.{ext}"
        os.makedirs(os.path.dirname(private_storage.path(final)), exist_ok=True)
        os.replace(temp, private_storage.path(final))
        try:
            video = services.add_video(
                deal,
                request.user,
                file_name=final,
                mime=upload.mime,
                duration=duration,
                captured_at=upload.captured_at,
                container_created_at=created,
                now=now,
            )
        except services.DealError as err:
            private_storage.delete(final)
            return error_response(err)
        upload.completed_at = now
        upload.save(update_fields=["completed_at"])
        from .tasks import make_thumbnail

        make_thumbnail.delay(video.pk)
        return Response({"n": video.n, "overlay_text": video.overlay_text}, status=201)


_RANGE = re.compile(r"bytes (\d+)-(\d+)/(\d+)")


class VideoUploadChunkView(APIView):
    """/api/deals/uploads/{signed token}/
    GET -> {offset}: how much arrived (to resume).
    PUT a chunk with Content-Range: bytes start-end/total -> {offset}."""

    def _upload(self, request, token):
        try:
            data = signing.loads(token, salt=UPLOAD_SALT, max_age=UPLOAD_MAX_AGE)
        except signing.BadSignature:
            raise Http404
        return get_object_or_404(VideoUpload, pk=data.get("u"), uploader=request.user, completed_at__isnull=True)

    def get(self, request, token):
        return Response({"offset": self._upload(request, token).received_bytes})

    def put(self, request, token):
        upload = self._upload(request, token)
        match = _RANGE.fullmatch(request.headers.get("Content-Range", ""))
        if not match:
            return Response({"code": "invalid", "detail": "Content-Range is required."}, status=400)
        start, end, total = (int(g) for g in match.groups())
        body = request.body
        if total != upload.size or end - start + 1 != len(body) or end >= total:
            return Response({"code": "invalid", "detail": "The chunk doesn’t fit."}, status=400)
        if start != upload.received_bytes:
            return Response({"code": "offset", "offset": upload.received_bytes}, status=409)
        with open(private_storage.path(upload.path), "ab") as f:
            f.write(body)
        VideoUpload.objects.filter(pk=upload.pk).update(received_bytes=upload.received_bytes + len(body))
        return Response({"offset": upload.received_bytes + len(body)})


def _ranged(request, path, content_type):
    """The file, honouring a single Range request (video players seek with them)."""
    size = os.path.getsize(path)
    header = request.headers.get("Range", "")
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", header)
    if not match or (not match.group(1) and not match.group(2)):
        response = FileResponse(open(path, "rb"), content_type=content_type)
        response["Accept-Ranges"] = "bytes"
        return response
    start = int(match.group(1)) if match.group(1) else max(size - int(match.group(2)), 0)
    end = int(match.group(2)) if match.group(1) and match.group(2) else size - 1
    end = min(end, size - 1)
    if start > end:
        response = HttpResponse(status=416)
        response["Content-Range"] = f"bytes */{size}"
        return response
    with open(path, "rb") as f:
        f.seek(start)
        chunk = f.read(end - start + 1)
    response = HttpResponse(chunk, status=206, content_type=content_type)
    response["Content-Range"] = f"bytes {start}-{end}/{size}"
    response["Accept-Ranges"] = "bytes"
    return response


def _private(response):
    response["Cache-Control"] = "private, max-age=3600"
    response["X-Content-Type-Options"] = "nosniff"
    return response


class VideoFileView(APIView):
    """GET /api/deals/{id}/videos/{n}/file/ (and /thumb/): the deal's people only."""

    def get(self, request, pk, n, part="file"):
        deal = get_deal(request, pk)
        video = get_object_or_404(LiveVideo, deal=deal, n=n)
        field = video.thumb if part == "thumb" else video.file
        if not field:
            raise Http404
        content_type = "image/jpeg" if part == "thumb" else video.mime
        return _private(_ranged(request, field.path, content_type))


class PhotoFileView(APIView):
    """GET /api/deals/{id}/messages/{message id}/photo/"""

    def get(self, request, pk, mid):
        deal = get_deal(request, pk)
        message = get_object_or_404(Message, deal=deal, pk=mid, kind=Message.Kind.PHOTO)
        content_type = mimetypes.guess_type(message.attachment.name)[0] or "image/webp"
        return _private(FileResponse(message.attachment.open("rb"), content_type=content_type))


# ---------------------------------------------------------------------------
# Steps


class _StepView(APIView):
    def act(self, request, pk, fn):
        deal = get_deal(request, pk)
        try:
            fn(deal)
        except services.DealError as err:
            return error_response(err)
        return Response(deal_data(get_deal(request, pk), request.user))


class RateVideoView(_StepView):
    """POST /api/deals/{id}/videos/{n}/rate/ {verdict: good|bad, chips[], note}"""

    def post(self, request, pk, n):
        data = request.data
        chips = data.get("chips") or []
        if not isinstance(chips, list):
            chips = []
        return self.act(
            request, pk, lambda d: services.rate_video(d, request.user, n, data.get("verdict"), chips, data.get("note", ""))
        )


class DecideView(_StepView):
    """POST /api/deals/{id}/after-third-bad/ {choice: refund|continue}"""

    def post(self, request, pk):
        return self.act(request, pk, lambda d: services.decide(d, request.user, request.data.get("choice")))


class ConfirmReceiptView(_StepView):
    """POST /api/deals/{id}/confirm-receipt/ {checked: true}"""

    def post(self, request, pk):
        return self.act(request, pk, lambda d: services.confirm_receipt(d, request.user, request.data.get("checked") is True))


class MeetupsView(_StepView):
    """POST /api/deals/{id}/meetups/ {when (ISO), place}"""

    def post(self, request, pk):
        when = parse_datetime(str(request.data.get("when", "")))
        if when is None or when.tzinfo is None:
            return Response({"code": "invalid", "detail": "Pick a date and time."}, status=400)
        return self.act(request, pk, lambda d: services.propose_meetup(d, request.user, when, request.data.get("place", "")))


class MeetupConfirmView(_StepView):
    """POST /api/deals/{id}/meetups/{meetup id}/confirm/"""

    def post(self, request, pk, mid):
        return self.act(request, pk, lambda d: services.confirm_meetup(d, request.user, mid))


class ReportView(APIView):
    """POST /api/deals/{id}/report/ {text}. Staff are emailed."""

    def post(self, request, pk):
        deal = get_deal(request, pk)
        try:
            services.report_problem(deal, request.user, request.data.get("text", ""))
        except services.DealError as err:
            return error_response(err)
        return Response({"status": "received"}, status=201)
