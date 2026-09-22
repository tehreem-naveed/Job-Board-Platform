import os
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class CandidateProfile(models.Model):
    """A candidate profile owned by exactly one CANDIDATE user."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="candidate_profile",
    )
    full_name = models.CharField(max_length=150, blank=True)
    headline = models.CharField(max_length=200, blank=True)
    bio = models.TextField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    location = models.CharField(max_length=150, blank=True)
    skills = models.JSONField(default=list, blank=True)
    experience = models.TextField(blank=True)
    education = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.full_name or self.user.username

    def clean(self):
        if not isinstance(self.skills, list):
            raise ValidationError({"skills": "Skills must be a list of strings."})


def _resume_upload_path(instance, filename):
    """
    Build a safe, unguessable storage path. The original filename is never
    used to build the filesystem path, which prevents path traversal and
    filename collisions between candidates.
    """
    ext = os.path.splitext(filename)[1].lower()
    safe_name = f"{uuid.uuid4().hex}{ext}"
    return os.path.join("resumes", str(instance.candidate.user_id), safe_name)


class Resume(models.Model):
    """
    A candidate's current resume. Each candidate has at most one resume
    record; uploading a new file replaces the previous one (see
    candidates.services.replace_resume) rather than accumulating duplicates.
    """

    candidate = models.OneToOneField(
        CandidateProfile,
        on_delete=models.CASCADE,
        related_name="resume",
    )
    file = models.FileField(upload_to=_resume_upload_path)
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=120, blank=True)
    file_size = models.PositiveIntegerField(default=0)

    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Resume for {self.candidate}"
