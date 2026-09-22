from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import (
    EMPLOYER_ALLOWED_TRANSITIONS,
    Application,
    ApplicationStatus,
    INACTIVE_STATUSES,
    Job,
    Notification,
    NotificationType,
)


class ApplicationError(ValidationError):
    """Raised for business-rule violations when applying to a job."""


@transaction.atomic
def create_application(candidate_profile, job_id, resume, cover_letter=""):
    """
    Apply to a job on behalf of `candidate_profile`.

    Enforces every server-side rule described in the platform spec: the job
    must exist and be open, the deadline must not have passed, the resume
    must belong to the candidate, and no duplicate active application may
    exist. Creates a notification for the employer as part of the same
    transaction so the two writes succeed or fail together.
    """
    try:
        job = Job.objects.select_related("employer", "employer__user").get(pk=job_id)
    except Job.DoesNotExist:
        raise ApplicationError({"job_id": "Job not found."}, code="not_found")

    if not job.is_open:
        if job.is_past_deadline:
            raise ApplicationError(
                {"job_id": "The application deadline for this job has passed."}, code="deadline_passed"
            )
        raise ApplicationError({"job_id": "This job is not accepting applications."}, code="job_closed")

    if resume is not None and resume.candidate_id != candidate_profile.id:
        raise ApplicationError({"resume_id": "This resume does not belong to you."}, code="invalid_resume")

    existing = Application.objects.filter(candidate=candidate_profile, job=job).exclude(
        status__in=INACTIVE_STATUSES
    )
    if existing.exists():
        raise ApplicationError(
            {"job_id": "You have already applied for this job."}, code="duplicate_application"
        )

    try:
        application = Application.objects.create(
            candidate=candidate_profile,
            job=job,
            resume=resume,
            cover_letter=cover_letter,
            status=ApplicationStatus.APPLIED,
        )
    except IntegrityError:
        raise ApplicationError(
            {"job_id": "You have already applied for this job."}, code="duplicate_application"
        )

    Notification.objects.create(
        recipient=job.employer.user,
        application=application,
        message=f"New application received for '{job.title}'.",
        notification_type=NotificationType.NEW_APPLICATION,
    )

    return application


@transaction.atomic
def update_application_status(application, new_status, actor):
    """
    Change an application's status on behalf of the employer that owns the
    job. Validates that the transition is allowed and that the actor is
    actually authorized to make it, then notifies the candidate.
    """
    if application.job.employer.user_id != actor.id:
        raise PermissionDenied("You do not have permission to modify this application.")

    if new_status not in ApplicationStatus.values:
        raise ValidationError({"status": "Invalid status value."})

    allowed = EMPLOYER_ALLOWED_TRANSITIONS.get(application.status, set())
    if new_status not in {s.value for s in allowed}:
        raise ValidationError(
            {"status": f"Cannot transition from {application.status} to {new_status}."},
            code="invalid_transition",
        )

    application.status = new_status
    application.save(update_fields=["status", "updated_at"])

    Notification.objects.create(
        recipient=application.candidate.user,
        application=application,
        message=f"Your application for '{application.job.title}' is now {application.get_status_display()}.",
        notification_type=NotificationType.APPLICATION_STATUS_CHANGE,
    )

    return application


@transaction.atomic
def withdraw_application(application, actor):
    """A candidate withdraws their own application, if it is still active."""
    if application.candidate.user_id != actor.id:
        raise PermissionDenied("You do not have permission to withdraw this application.")

    if application.status in INACTIVE_STATUSES or application.status == ApplicationStatus.HIRED:
        raise ValidationError(
            {"status": f"An application with status {application.status} cannot be withdrawn."},
            code="invalid_transition",
        )

    application.status = ApplicationStatus.WITHDRAWN
    application.save(update_fields=["status", "updated_at"])
    return application
