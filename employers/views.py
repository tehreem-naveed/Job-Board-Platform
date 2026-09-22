from rest_framework import generics
from rest_framework.exceptions import PermissionDenied

from accounts.permissions import IsEmployer
from .models import EmployerProfile
from .serializers import EmployerProfileSerializer


class MyEmployerProfileView(generics.RetrieveUpdateAPIView):
    """
    GET/PATCH the authenticated employer's own company profile.
    The profile is created automatically the first time it is accessed,
    which keeps onboarding simple without exposing an employer/user id the
    client could tamper with.
    """

    serializer_class = EmployerProfileSerializer
    permission_classes = [IsEmployer]

    def get_object(self):
        if not self.request.user.is_employer:
            raise PermissionDenied("Only employer accounts have a company profile.")
        profile, _ = EmployerProfile.objects.get_or_create(
            user=self.request.user,
            defaults={"company_name": self.request.user.username},
        )
        return profile
