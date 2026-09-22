from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import Role, User


class SignupTests(APITestCase):
    def setUp(self):
        self.url = reverse("accounts:signup")

    def test_signup_succeeds_for_candidate(self):
        response = self.client.post(
            self.url,
            {"username": "jane", "email": "jane@example.com", "password": "SecurePass123", "role": "CANDIDATE"},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["user"]["role"], "CANDIDATE")
        self.assertNotIn("password", response.data["user"])
        self.assertTrue(User.objects.filter(username="jane").exists())

    def test_signup_succeeds_for_employer(self):
        response = self.client.post(
            self.url,
            {"username": "acme_hr", "email": "hr@acme.com", "password": "SecurePass123", "role": "EMPLOYER"},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["user"]["role"], "EMPLOYER")

    def test_signup_cannot_grant_admin_role(self):
        response = self.client.post(
            self.url,
            {"username": "hacker", "email": "hacker@example.com", "password": "SecurePass123", "role": "ADMIN"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(username="hacker").exists())

    def test_signup_rejects_missing_fields(self):
        response = self.client.post(self.url, {"username": "incomplete"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_signup_rejects_invalid_email(self):
        response = self.client.post(
            self.url,
            {"username": "bademail", "email": "not-an-email", "password": "SecurePass123", "role": "CANDIDATE"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_signup_rejects_duplicate_username(self):
        User.objects.create_user(username="jane", email="jane1@example.com", password="SecurePass123")
        response = self.client.post(
            self.url,
            {"username": "jane", "email": "jane2@example.com", "password": "SecurePass123", "role": "CANDIDATE"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_signup_rejects_duplicate_email(self):
        User.objects.create_user(username="jane1", email="jane@example.com", password="SecurePass123")
        response = self.client.post(
            self.url,
            {"username": "jane2", "email": "jane@example.com", "password": "SecurePass123", "role": "CANDIDATE"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_signup_rejects_weak_password(self):
        response = self.client.post(
            self.url,
            {"username": "weakpass", "email": "weak@example.com", "password": "123", "role": "CANDIDATE"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class LoginLogoutTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="jane", email="jane@example.com", password="SecurePass123", role=Role.CANDIDATE
        )
        self.login_url = reverse("accounts:login")
        self.logout_url = reverse("accounts:logout")
        self.me_url = reverse("accounts:me")

    def test_login_succeeds_with_valid_credentials(self):
        response = self.client.post(self.login_url, {"username": "jane", "password": "SecurePass123"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("token", response.data)

    def test_login_fails_with_invalid_credentials(self):
        response = self.client.post(self.login_url, {"username": "jane", "password": "WrongPassword"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_me_requires_authentication(self):
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_returns_current_user_when_authenticated(self):
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user"]["username"], "jane")

    def test_logout_invalidates_token(self):
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = self.client.post(self.logout_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Token.objects.filter(user=self.user).exists())

        # The old token must no longer work.
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_requires_authentication(self):
        response = self.client.post(self.logout_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
