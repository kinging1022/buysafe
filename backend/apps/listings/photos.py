"""Listing photo processing. Every upload is re-encoded, so nothing from the
original file survives except the pixels: no EXIF, and in particular no GPS
coordinates (they can reveal where the seller lives)."""

import uuid
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_EDGE = 2000  # px, long edge
WEBP_QUALITY = 82

TYPE_ERROR = "Use a JPG, PNG or WebP photo."
SIZE_ERROR = "Each photo must be 10 MB or smaller."


def process_photo(upload) -> ContentFile:
    """Validate one uploaded file and return it as a clean WebP. Raises ValidationError."""
    if upload.size > MAX_UPLOAD_BYTES:
        raise ValidationError(SIZE_ERROR)
    try:
        Image.open(upload).verify()  # structural check; the image must be reopened after
        upload.seek(0)
        image = Image.open(upload)
        image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, SyntaxError, ValueError):
        raise ValidationError(TYPE_ERROR) from None
    if image.format not in ALLOWED_FORMATS:
        raise ValidationError(TYPE_ERROR)

    # Apply the camera's rotation to the pixels before the metadata is dropped.
    image = ImageOps.exif_transpose(image)
    has_alpha = image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info)
    image = image.convert("RGBA" if has_alpha else "RGB")
    image.thumbnail((MAX_EDGE, MAX_EDGE), Image.LANCZOS)

    out = BytesIO()
    # No exif/xmp/icc arguments: the saved file carries no metadata.
    image.save(out, "WEBP", quality=WEBP_QUALITY, method=4)
    return ContentFile(out.getvalue(), name=f"{uuid.uuid4().hex}.webp")
