from pathlib import Path

from django.conf import settings
from rest_framework.exceptions import ValidationError


ALLOWED_SUFFIXES = {".pdf", ".jpg", ".jpeg", ".png"}
MAX_DOCUMENT_UPLOAD_BYTES = 10 * 1024 * 1024


def validate_document_upload(upload, field_name='file'):
    if not upload:
        return
    suffix = Path(upload.name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValidationError({field_name: "Upload a PDF, JPG, or PNG file."})

    max_bytes = getattr(settings, "DOCUMENT_MAX_UPLOAD_BYTES", MAX_DOCUMENT_UPLOAD_BYTES)
    if upload.size > max_bytes:
        raise ValidationError({field_name: f"File exceeds the {max_bytes // (1024 * 1024)} MB limit."})

    header = upload.read(12)
    upload.seek(0)
    valid = (
        (suffix == ".pdf" and header.startswith(b"%PDF-"))
        or (suffix in {".jpg", ".jpeg"} and header.startswith(b"\xff\xd8\xff"))
        or (suffix == ".png" and header.startswith(b"\x89PNG\r\n\x1a\n"))
    )
    if not valid:
        raise ValidationError({field_name: "File contents do not match a supported PDF, JPG, or PNG."})
