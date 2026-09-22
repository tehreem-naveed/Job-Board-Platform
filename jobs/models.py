from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class EmploymentType(models.TextChoices):
    FULL_TIME = "FULL_TIME", "Full time"
    PART_TIME = "PART_TIME", "Part time"
    CONTRACT = "CONTRACT", "Contract"
    INTERNSHIP = "INTERNSHIP", "Internship"
    TEMPORARY = "TEMPORARY", "Temporary"
    REMOTE = "REMOTE", "Remote"


class ExperienceLevel(models.TextChoices):
    ENTRY = "ENTRY", "Entry level"
    MID = "MID", "Mid level"
    SENIOR = "SENIOR", "Senior level"
    LEAD = "LEAD", "Lead / Principal"


class JobStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    CLOSED = "CLOSED", "Closed"


class Job(models.Model):
    employer = models.ForeignKey(
        "employers.EmployerProfile",
        on_delete=models.CASCADE,
        related_name="jobs",
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    location = models.CharField(max_length=150)
    employment_type = models.CharField(max_length=20, choices=EmploymentType.choices)
    experience_level = models.CharField(max_length=20, choices=ExperienceLevel.choices)
    salary_min = models.PositiveIntegerField(null=True, blank=True)
    salary_max = models.PositiveIntegerField(null=True, blank=True)
    currency = models.CharField(max_length=10, default="USD", blank=True)
    skills = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=10, choices=JobStatus.choices, default=JobStatus.OPEN)
    application_deadline = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(salary_min__isnull=True)
                    | models.Q(salary_max__isnull=True)
                    | models.Q(salary_max__gte=models.F("salary_min"))
                ),
                name="job_salary_max_gte_min",
            ),
        ]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["employment_type"]),
            models.Index(fields=["experience_level"]),
        ]

    def __str__(self):
        return self.title

    def clean(self):
        errors = {}

        if not self.title or not self.title.strip():
            errors["title"] = "Title is required."
        elif len(self.title) > 200:
            errors["title"] = "Title is too long."

        if not self.description or not self.description.strip():
            errors["description"] = "Description is required."

        if not self.location or not self.location.strip():
            errors["location"] = "Location is required."

        if self.salary_min is not None and self.salary_min < 0:
            errors["salary_min"] = "Salary cannot be negative."
        if self.salary_max is not None and self.salary_max < 0:
            errors["salary_max"] = "Salary cannot be negative."
        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_max < self.salary_min
        ):
            errors["salary_max"] = "Maximum salary cannot be less than minimum salary."

        if not isinstance(self.skills, list):
            errors["skills"] = "Skills must be a list of strings."

        if errors:
            raise ValidationError(errors)

    @property
    def is_open(self):
        if self.status != JobStatus.OPEN:
            return False
        if self.application_deadline and self.application_deadline < timezone.localdate():
            return False
        return True

    @property
    def is_past_deadline(self):
        return bool(self.application_deadline and self.application_deadline < timezone.localdate())


class ApplicationStatus(models.TextChoices):
    APPLIED = "APPLIED", "Applied"
    UNDER_REVIEW = "UNDER_REVIEW", "Under review"
    SHORTLISTED = "SHORTLISTED", "Shortlisted"
    INTERVIEW = "INTERVIEW", "Interview"
    REJECTED = "REJECTED", "Rejected"
    HIRED = "HIRED", "Hired"
    WITHDRAWN = "WITHDRAWN", "Withdrawn"


# Statuses that represent an application that is no longer active. A
# candidate is blocked from creating a second *active* application to the
# same job, but this set intentionally excludes WITHDRAWN/REJECTED so the
# lifecycle design decision is explicit and easy to find in one place.
INACTIVE_STATUSES = {ApplicationStatus.WITHDRAWN, ApplicationStatus.REJECTED}

# Status transitions an employer is allowed to make. Employers move an
# application forward (or reject it) but never resurrect a withdrawn
# application on the candidate's behalf.
EMPLOYER_ALLOWED_TRANSITIONS = {
    ApplicationStatus.APPLIED: {ApplicationStatus.UNDER_REVIEW, ApplicationStatus.SHORTLISTED, ApplicationStatus.REJECTED},
    ApplicationStatus.UNDER_REVIEW: {ApplicationStatus.SHORTLISTED, ApplicationStatus.REJECTED},
    ApplicationStatus.SHORTLISTED: {ApplicationStatus.INTERVIEW, ApplicationStatus.REJECTED},
    ApplicationStatus.INTERVIEW: {ApplicationStatus.HIRED, ApplicationStatus.REJECTED},
    ApplicationStatus.HIRED: set(),
    ApplicationStatus.REJECTED: set(),
    ApplicationStatus.WITHDRAWN: set(),
}


class Application(models.Model):
    candidate = models.ForeignKey(
        "candidates.CandidateProfile",
        on_delete=models.CASCADE,
        related_name="applications",
    )
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="applications")
    resume = models.ForeignKey(
        "candidates.Resume",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="applications",
    )
    cover_letter = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=ApplicationStatus.choices,
        default=ApplicationStatus.APPLIED,
    )

    applied_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-applied_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["candidate", "job"],
                condition=~models.Q(status__in=["WITHDRAWN", "REJECTED"]),
                name="unique_active_application_per_candidate_job",
            ),
        ]

    def __str__(self):
        return f"{self.candidate} -> {self.job} ({self.status})"


class NotificationType(models.TextChoices):
    NEW_APPLICATION = "NEW_APPLICATION", "New application"
    APPLICATION_STATUS_CHANGE = "APPLICATION_STATUS_CHANGE", "Application status change"


class Notification(models.Model):
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )
    message = models.CharField(max_length=255)
    notification_type = models.CharField(max_length=40, choices=NotificationType.choices)
    is_read = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.notification_type} -> {self.recipient}"
