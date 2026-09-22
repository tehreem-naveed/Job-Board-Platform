from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers

from candidates.models import Resume
from employers.serializers import PublicEmployerSerializer
from .models import Application, Job, Notification


class JobListSerializer(serializers.ModelSerializer):
    """Compact representation used for the public job list endpoint."""

    company = serializers.CharField(source="employer.company_name", read_only=True)

    class Meta:
        model = Job
        fields = [
            "id",
            "title",
            "company",
            "location",
            "employment_type",
            "experience_level",
            "salary_min",
            "salary_max",
            "currency",
            "skills",
            "status",
            "application_deadline",
            "created_at",
        ]
        read_only_fields = fields


class JobDetailSerializer(serializers.ModelSerializer):
    """Full representation used for job detail and employer-managed views."""

    employer = PublicEmployerSerializer(read_only=True)

    class Meta:
        model = Job
        fields = [
            "id",
            "employer",
            "title",
            "description",
            "location",
            "employment_type",
            "experience_level",
            "salary_min",
            "salary_max",
            "currency",
            "skills",
            "status",
            "application_deadline",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "employer", "created_at", "updated_at"]

    def validate_title(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Title cannot be blank.")
        if len(value) > 200:
            raise serializers.ValidationError("Title is too long (max 200 characters).")
        return value.strip()

    def validate_description(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Description cannot be blank.")
        return value

    def validate_location(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Location cannot be blank.")
        return value.strip()

    def validate_skills(self, value):
        if value in (None, ""):
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("Skills must be provided as a list of strings.")
        return [str(item).strip() for item in value if str(item).strip()]

    def validate_application_deadline(self, value):
        if value and value < timezone.localdate():
            raise serializers.ValidationError("Application deadline cannot be in the past.")
        return value

    def validate(self, attrs):
        salary_min = attrs.get("salary_min", getattr(self.instance, "salary_min", None))
        salary_max = attrs.get("salary_max", getattr(self.instance, "salary_max", None))

        if salary_min is not None and salary_min < 0:
            raise serializers.ValidationError({"salary_min": "Salary cannot be negative."})
        if salary_max is not None and salary_max < 0:
            raise serializers.ValidationError({"salary_max": "Salary cannot be negative."})
        if salary_min is not None and salary_max is not None and salary_max < salary_min:
            raise serializers.ValidationError(
                {"salary_max": "Maximum salary cannot be less than minimum salary."}
            )
        return attrs

    def create(self, validated_data):
        # Ownership is always derived from the authenticated request, never
        # from client-supplied data - see JobViewSet.perform_create.
        job = Job(**validated_data)
        try:
            job.full_clean(exclude=["employer"])
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict)
        job.save()
        return job


class CandidateResumeRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resume
        fields = ["id", "original_filename"]
        read_only_fields = fields


class ApplicationSerializer(serializers.ModelSerializer):
    """Used for a candidate's own application list/detail."""

    job_title = serializers.CharField(source="job.title", read_only=True)
    company = serializers.CharField(source="job.employer.company_name", read_only=True)
    job_location = serializers.CharField(source="job.location", read_only=True)
    resume = CandidateResumeRefSerializer(read_only=True)

    class Meta:
        model = Application
        fields = [
            "id",
            "job",
            "job_title",
            "company",
            "job_location",
            "resume",
            "cover_letter",
            "status",
            "applied_at",
            "updated_at",
        ]
        read_only_fields = ["id", "job_title", "company", "job_location", "resume", "status", "applied_at", "updated_at"]


class ApplicationCreateSerializer(serializers.Serializer):
    job_id = serializers.IntegerField()
    resume_id = serializers.IntegerField(required=False, allow_null=True)
    cover_letter = serializers.CharField(required=False, allow_blank=True, default="")


class EmployerApplicationSerializer(serializers.ModelSerializer):
    """Used when an employer views applications submitted to their jobs."""

    candidate_name = serializers.CharField(source="candidate.full_name", read_only=True)
    candidate_headline = serializers.CharField(source="candidate.headline", read_only=True)
    candidate_location = serializers.CharField(source="candidate.location", read_only=True)
    candidate_skills = serializers.ListField(source="candidate.skills", read_only=True)
    job_title = serializers.CharField(source="job.title", read_only=True)
    has_resume = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = [
            "id",
            "job",
            "job_title",
            "candidate_name",
            "candidate_headline",
            "candidate_location",
            "candidate_skills",
            "cover_letter",
            "has_resume",
            "status",
            "applied_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_has_resume(self, obj):
        return bool(obj.resume_id)


class ApplicationStatusUpdateSerializer(serializers.Serializer):
    status = serializers.CharField()


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "application", "message", "notification_type", "is_read", "created_at"]
        read_only_fields = ["id", "application", "message", "notification_type", "created_at"]
