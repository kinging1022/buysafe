"""Reading what we can from an uploaded video file, without ffmpeg: the
container's own creation time (and duration, for MP4).

- MP4/MOV (Safari's MediaRecorder): the `mvhd` box has creation_time
  (seconds since 1904) and duration.
- WebM (Chrome/Android): the Segment Info `DateUTC` element, when the
  recorder writes one (Chrome's usually doesn't).

A missing or zero time comes back as None; the caller then falls back to
the device's capture time.
"""

from __future__ import annotations

import struct
from datetime import datetime, timedelta, timezone

MP4_EPOCH = datetime(1904, 1, 1, tzinfo=timezone.utc)
MKV_EPOCH = datetime(2001, 1, 1, tzinfo=timezone.utc)
SCAN_BYTES = 4 * 1024 * 1024


def _read_scan(path):
    with open(path, "rb") as f:
        head = f.read(SCAN_BYTES)
        f.seek(0, 2)
        size = f.tell()
        tail = b""
        if size > SCAN_BYTES:
            f.seek(max(size - SCAN_BYTES, SCAN_BYTES))
            tail = f.read()
    return head + tail


def _mp4(data):
    i = data.find(b"mvhd")
    if i < 0 or i + 32 > len(data):
        return None, None
    version = data[i + 4]
    if version == 1:
        created, _mod, timescale, duration = struct.unpack(">QQIQ", data[i + 8 : i + 36])
    else:
        created, _mod, timescale, duration = struct.unpack(">IIII", data[i + 8 : i + 24])
    when = MP4_EPOCH + timedelta(seconds=created) if created else None
    seconds = duration / timescale if timescale and duration not in (0, 0xFFFFFFFF) else None
    return when, seconds


def _webm(data):
    i = data.find(b"\x44\x61\x88")  # DateUTC, size 8
    if i < 0 or i + 11 > len(data):
        return None, None
    (nanos,) = struct.unpack(">q", data[i + 3 : i + 11])
    return (MKV_EPOCH + timedelta(microseconds=nanos // 1000) if nanos else None), None


def container_info(path, mime) -> tuple:
    """(created_at or None, duration_seconds or None)."""
    try:
        data = _read_scan(path)
    except OSError:
        return None, None
    try:
        return _webm(data) if mime == "video/webm" else _mp4(data)
    except struct.error:
        return None, None


def looks_like_video(path, mime) -> bool:
    with open(path, "rb") as f:
        head = f.read(12)
    if mime == "video/webm":
        return head.startswith(b"\x1a\x45\xdf\xa3")  # EBML
    return head[4:8] == b"ftyp"
