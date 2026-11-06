"""The deal rules, in one place. Hours are working hours: the clock pauses
during quiet hours (deadlines.py)."""

from datetime import timedelta

VIDEO_HOURS = 4  # seller: send the live video, after payment and after each Bad
RATE_HOURS = 2  # buyer: rate each video; no rating counts as Good
MAX_VIDEOS = 3

MIN_VIDEO_SECONDS = 20
MAX_VIDEO_SECONDS = 60
# A video must have been recorded this recently when it reaches us.
CAPTURE_MAX_AGE = timedelta(minutes=5)
MAX_VIDEO_BYTES = 60 * 1024 * 1024
VIDEO_TYPES = {"video/webm", "video/mp4", "video/quicktime"}
UPLOAD_CHUNK_BYTES = 1024 * 1024

# What the buyer can ask for after a Bad rating.
INSTRUCTION_CHIPS = ["Show the back", "Switch it on", "Closer", "Better light"]
INSTRUCTION_NOTE_MAX = 200

MESSAGE_MAX = 1000
MEETUP_PLACE_MAX = 160

# Reminders: (working time into the step, channels). A step's first reminder
# goes out at once (unless it's quiet hours: then at 7 AM).
VIDEO_REMINDERS = [
    (timedelta(0), ("push", "sms")),
    (timedelta(minutes=30), ("call",)),  # only if there's still no video
    (timedelta(hours=3), ("push", "sms")),  # "1 hour left"
]
RATE_REMINDERS = [
    (timedelta(0), ("push",)),  # "video ready to rate"
    (timedelta(minutes=30), ("sms",)),
    (timedelta(hours=1), ("call",)),
]
# After the meetup time has passed, the buyer is reminded to confirm.
CONFIRM_REMINDER_AFTER = timedelta(hours=2)
