from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Role, User
from .models import CandidateProfile, Resume

PDF_BYTES = b"%PDF-1.4\n%mock pdf content for testing\n%%EOF"


class CandidateProfileTests(APITestCase):
    def setUp(self):
        self.candidate = User.objects.create_user(
            username="jane", email="jane@example.com", password="SecurePass123", role=Role.CANDIDATE
        )
        self.other_candidate = User.objects.create_user(
            username="john", email="john@example.com", password="SecurePass123", role=Role.CANDIDATE
        )
        self.employer = User.objects.create_user(
            username="acme_hr", email="hr@acme.com", password="SecurePass123", role=Role.EMPLOYER
        )
        self.url = reverse("candidates:me")

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def test_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_candidate_can_create_and_update_own_profile(self):
        self._auth(self.candidate)
        response = self.client.patch(self.url, {"full_name": "Jane Doe", "skills": ["Python", "Django"]})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["full_name"], "Jane Doe")
        self.assertEqual(response.data["skills"], ["Python", "Django"])

    def test_employer_cannot_access_candidate_profile_endpoint(self):
        self._auth(self.employer)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_candidate_cannot_modify_another_candidates_profile(self):
        CandidateProfile.objects.create(user=self.candidate, full_name="Jane")
        CandidateProfile.objects.create(user=self.other_candidate, full_name="John")

        self._auth(self.candidate)
        self.client.patch(self.url, {"full_name": "Hijacked"})

        other_profile = CandidateProfile.objects.get(user=self.other_candidate)
        self.assertEqual(other_profile.full_name, "John")

    def test_skills_must_be_a_list(self):
        self._auth(self.candidate)
        response = self.client.patch(self.url, {"skills": "not-a-list"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


@override_settings(RESUME_MAX_UPLOAD_BYTES=1024 * 1024, RESUME_MAX_UPLOAD_MB=1)
class ResumeTests(APITestCase):
    def setUp(self):
        self.candidate = User.objects.create_user(
            username="jane", email="jane@example.com", password="SecurePass123", role=Role.CANDIDATE
        )
        self.other_candidate = User.objects.create_user(
            username="john", email="john@example.com", password="SecurePass123", role=Role.CANDIDATE
        )
        self.employer = User.objects.create_user(
            username="acme_hr", email="hr@acme.com", password="SecurePass123", role=Role.EMPLOYER
        )
        self.url = reverse("candidates:my-resume")
        self.download_url = reverse("candidates:my-resume-download")

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def test_valid_pdf_upload_succeeds(self):
        self._auth(self.candidate)
        upload = SimpleUploadedFile("resume.pdf", PDF_BYTES, content_type="application/pdf")
        response = self.client.post(self.url, {"file": upload}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["resume"]["original_filename"], "resume.pdf")

    def test_valid_docx_upload_succeeds(self):
        self._auth(self.candidate)
        upload = SimpleUploadedFile(
            "resume.docx",
            b"docx binary content stand-in",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        response = self.client.post(self.url, {"file": upload}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_unsupported_file_type_rejected(self):
        self._auth(self.candidate)
        upload = SimpleUploadedFile("resume.exe", b"MZ-fake-binary", content_type="application/octet-stream")
        response = self.client.post(self.url, {"file": upload}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Resume.objects.filter(candidate__user=self.candidate).exists())

    def test_oversized_file_rejected(self):
        self._auth(self.candidate)
        oversized_content = b"%PDF-1.4\n" + b"0" * (2 * 1024 * 1024)
        upload = SimpleUploadedFile("resume.pdf", oversized_content, content_type="application/pdf")
        response = self.client.post(self.url, {"file": upload}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_fake_pdf_with_wrong_magic_bytes_rejected(self):
        self._auth(self.candidate)
        upload = SimpleUploadedFile("resume.pdf", b"NOT-A-REAL-PDF", content_type="application/pdf")
        response = self.client.post(self.url, {"file": upload}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_upload_requires_authentication(self):
        upload = SimpleUploadedFile("resume.pdf", PDF_BYTES, content_type="application/pdf")
        response = self.client.post(self.url, {"file": upload}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_employer_cannot_upload_resume(self):
        self._auth(self.employer)
        upload = SimpleUploadedFile("resume.pdf", PDF_BYTES, content_type="application/pdf")
        response = self.client.post(self.url, {"file": upload}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_replacing_resume_does_not_create_duplicate_records(self):
        self._auth(self.candidate)
        first = SimpleUploadedFile("first.pdf", PDF_BYTES, content_type="application/pdf")
        self.client.post(self.url, {"file": first}, format="multipart")

        second = SimpleUploadedFile("second.pdf", PDF_BYTES, content_type="application/pdf")
        response = self.client.post(self.url, {"file": second}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        profile = CandidateProfile.objects.get(user=self.candidate)
        self.assertEqual(Resume.objects.filter(candidate=profile).count(), 1)
        self.assertEqual(profile.resume.original_filename, "second.pdf")

    def test_candidate_can_download_own_resume(self):
        self._auth(self.candidate)
        upload = SimpleUploadedFile("resume.pdf", PDF_BYTES, content_type="application/pdf")
        self.client.post(self.url, {"file": upload}, format="multipart")

        response = self.client.get(self.download_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unauthenticated_user_cannot_access_resume_download(self):
        response = self.client.get(self.download_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_candidate_without_resume_gets_not_found(self):
        self._auth(self.candidate)
        response = self.client.get(self.download_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_candidate_can_delete_own_resume(self):
        self._auth(self.candidate)
        upload = SimpleUploadedFile("resume.pdf", PDF_BYTES, content_type="application/pdf")
        self.client.post(self.url, {"file": upload}, format="multipart")

        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        profile = CandidateProfile.objects.get(user=self.candidate)
        self.assertFalse(Resume.objects.filter(candidate=profile).exists())
