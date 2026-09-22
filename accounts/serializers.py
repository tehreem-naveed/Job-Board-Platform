from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Role, User

# Only these roles may be self-selected at signup. ADMIN is never assignable
# through the public API - it is only ever granted through Django Admin /
# createsuperuser, keeping privilege escalation impossible via request data.
SELF_SERVICE_ROLES = (Role.CANDIDATE, Role.EMPLOYER)


class UserSerializer(serializers.ModelSerializer):
    """Safe, minimal representation of a user. Never includes the password."""

    class Meta:
        model = User
        fields = ["id", "username", "email", "role", "date_joined"]
        read_only_fields = fields


class SignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    role = serializers.ChoiceField(choices=[(r.value, r.label) for r in SELF_SERVICE_ROLES])

    class Meta:
        model = User
        fields = ["id", "username", "email", "password", "role"]

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_username(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Username cannot be blank.")
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return value

    def validate_role(self, value):
        # Belt-and-braces: even though the ChoiceField already restricts the
        # allowed values, this guarantees a malicious client can never smuggle
        # an ADMIN role through this endpoint.
        if value not in SELF_SERVICE_ROLES:
            raise serializers.ValidationError("Invalid role.")
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        user = authenticate(
            username=attrs.get("username"),
            password=attrs.get("password"),
        )
        if not user:
            raise serializers.ValidationError("Invalid username or password.", code="invalid_credentials")
        if not user.is_active:
            raise serializers.ValidationError("This account is disabled.", code="account_disabled")
        attrs["user"] = user
        return attrs
