"""Deal videos and chat photos live outside MEDIA_ROOT and are never served
publicly: only the deal's buyer and seller can fetch them (views.py)."""

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.functional import LazyObject


class _PrivateStorage(LazyObject):
    def _setup(self):
        self._wrapped = FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT, base_url=None)


private_storage = _PrivateStorage()


def get_private_storage():
    return private_storage
