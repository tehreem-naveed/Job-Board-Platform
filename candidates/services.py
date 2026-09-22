from django.db import transaction

from .models import Resume
from .validators import validate_resume_file


@transaction.atomic
def replace_resume(candidate_profile, uploaded_file):
    """
    Create or replace a candidate's resume with a newly uploaded file.

    Only ever touches the resume belonging to `candidate_profile`, so there is
    no risk of deleting or overwriting a file belonging to another candidate.
    The previous file (if any) is deleted from storage once the new record is
    safely saved.
    """
    validate_resume_file(uploaded_file)

    old_resume = Resume.objects.filter(candidate=candidate_profile).first()
    old_file = old_resume.file if old_resume else None

    resume, _ = Resume.objects.update_or_create(
        candidate=candidate_profile,
        defaults={
            "file": uploaded_file,
            "original_filename": uploaded_file.name,
            "content_type": getattr(uploaded_file, "content_type", "") or "",
            "file_size": uploaded_file.size,
        },
    )

    if old_file and old_file.name and old_file.name != resume.file.name:
        old_file.storage.delete(old_file.name)

    return resume
