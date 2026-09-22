from rest_framework import serializers

from .models import EmployerProfile


class EmployerProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = EmployerProfile
        fields = [
            "id",
            "username",
            "company_name",
            "description",
            "website",
            "industry",
            "location",
            "company_size",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "username", "created_at", "updated_at"]

    def validate_company_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Company name cannot be blank.")
        return value


class PublicEmployerSerializer(serializers.ModelSerializer):
    """A minimal, public-safe view of an employer, used when embedded in job listings."""

    class Meta:
        model = EmployerProfile
        fields = ["id", "company_name", "industry", "location", "website"]
        read_only_fields = fields
