from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Role, User
from .models import EmployerProfile


class EmployerProfileTests(APITestCase):
    def setUp(self):
        self.employer = User.objects.create_user(
            username="acme_hr", email="hr@acme.com", password="SecurePass123", role=Role.EMPLOYER
        )
        self.other_employer = User.objects.create_user(
            username="globex_hr", email="hr@globex.com", password="SecurePass123", role=Role.EMPLOYER
        )
        self.candidate = User.objects.create_user(
            username="jane", email="jane@example.com", password="SecurePass123", role=Role.CANDIDATE
        )
        self.url = reverse("employers:me")

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def test_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_employer_can_create_and_view_profile_via_me(self):
        self._auth(self.employer)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(EmployerProfile.objects.filter(user=self.employer).exists())

    def test_employer_can_update_own_profile(self):
        self._auth(self.employer)
        response = self.client.patch(self.url, {"company_name": "Acme Corp", "industry": "Software"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["company_name"], "Acme Corp")

    def test_candidate_cannot_access_employer_profile_endpoint(self):
        self._auth(self.candidate)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_employer_cannot_modify_another_employers_profile_data_stays_isolated(self):
        EmployerProfile.objects.create(user=self.employer, company_name="Acme")
        EmployerProfile.objects.create(user=self.other_employer, company_name="Globex")

        self._auth(self.employer)
        response = self.client.patch(self.url, {"company_name": "Hijacked Name"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # The "me" endpoint always resolves to the authenticated user's own
        # profile - there is no way to target another employer's profile id.
        other_profile = EmployerProfile.objects.get(user=self.other_employer)
        self.assertEqual(other_profile.company_name, "Globex")

    def test_blank_company_name_rejected(self):
        self._auth(self.employer)
        response = self.client.patch(self.url, {"company_name": "   "})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
