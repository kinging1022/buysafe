import logging
import shutil
import subprocess
import tempfile

from celery import shared_task
from django.core.files import File

from . import services
from .models import LiveVideo

logger = logging.getLogger(__name__)


@shared_task
def sweep():
    return services.sweep()


@shared_task
def make_thumbnail(video_id):
    """A still from the video for the chat bubble. Needs ffmpeg on the
    server; without it the bubble shows its striped placeholder."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    video = LiveVideo.objects.get(pk=video_id)
    with tempfile.NamedTemporaryFile(suffix=".jpg") as out:
        result = subprocess.run(
            [ffmpeg, "-y", "-loglevel", "error", "-ss", "1", "-i", video.file.path, "-frames:v", "1", "-vf", "scale=440:-2", out.name],
            capture_output=True,
            timeout=60,
        )
        if result.returncode != 0:
            logger.warning("Thumbnail for video %s failed", video_id)
            return False
        video.thumb.save(f"thumb-{video.pk}.jpg", File(open(out.name, "rb")), save=True)
    return True
