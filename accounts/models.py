from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    CANDIDATE = "CANDIDATE", "Candidate"
    EMPLOYER = "EMPLOYER", "Employer"
    ADMIN = "ADMIN", "Admin"


class User(AbstractUser):
    """
    Custom user model. Adds a `role` field that drives authorization
    throughout the platform. Roles are never trusted from arbitrary client
    input for privileged assignment - see accounts.serializers.SignupSerializer.
    """

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CANDIDATE)

    def __str__(self):
        return f"{self.username} ({self.role})"

    @property
    def is_candidate(self):
        return self.role == Role.CANDIDATE

    @property
    def is_employer(self):
        return self.role == Role.EMPLOYER

    @property
    def is_admin_role(self):
        return self.role == Role.ADMIN or self.is_staff or self.is_superuser
