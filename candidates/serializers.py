from rest_framework import serializers

from .models import CandidateProfile, Resume


class CandidateProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = CandidateProfile
        fields = [
            "id",
            "username",
            "email",
            "full_name",
            "headline",
            "bio",
            "phone",
            "location",
            "skills",
            "experience",
            "education",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "username", "email", "created_at", "updated_at"]

    def validate_skills(self, value):
        if value in (None, ""):
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("Skills must be provided as a list of strings.")
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        return cleaned


class ResumeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resume
        fields = [
            "id",
            "original_filename",
            "content_type",
            "file_size",
            "uploaded_at",
            "updated_at",
        ]
        read_only_fields = fields


class ResumeUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
