import os

from django.conf import settings
from django.core.exceptions import ValidationError


def validate_resume_file(uploaded_file):
    """
    Validate an uploaded resume file against extension, size and (where
    possible) content-type rules. Raises django.core.exceptions.ValidationError
    on any violation. This is intentionally defense-in-depth: extension AND
    content-type are both checked, since either alone can be spoofed.
    """
    name = uploaded_file.name or ""
    ext = os.path.splitext(name)[1].lower()

    if ext not in settings.RESUME_ALLOWED_EXTENSIONS:
        allowed = ", ".join(settings.RESUME_ALLOWED_EXTENSIONS)
        raise ValidationError(f"Unsupported file type '{ext}'. Allowed types: {allowed}.")

    if uploaded_file.size is None or uploaded_file.size <= 0:
        raise ValidationError("The uploaded file is empty.")

    if uploaded_file.size > settings.RESUME_MAX_UPLOAD_BYTES:
        raise ValidationError(
            f"File is too large. Maximum allowed size is {settings.RESUME_MAX_UPLOAD_MB} MB."
        )

    content_type = getattr(uploaded_file, "content_type", None)
    if content_type and content_type not in settings.RESUME_ALLOWED_CONTENT_TYPES:
        raise ValidationError("Unsupported file content type.")

    # Lightweight "magic bytes" sanity check for PDFs, since extension and the
    # client-supplied content-type can both be forged easily.
    if ext == ".pdf":
        head = uploaded_file.read(5)
        uploaded_file.seek(0)
        if head != b"%PDF-":
            raise ValidationError("File does not appear to be a valid PDF.")

    return True
