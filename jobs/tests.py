import datetime

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Role, User
from candidates.models import CandidateProfile, Resume
from employers.models import EmployerProfile

from .models import Application, ApplicationStatus, EmploymentType, ExperienceLevel, Job, JobStatus, Notification

PDF_BYTES = b"%PDF-1.4\n%mock pdf content for testing\n%%EOF"


def tomorrow():
    return (timezone.localdate() + datetime.timedelta(days=1)).isoformat()


def yesterday():
    return (timezone.localdate() - datetime.timedelta(days=1)).isoformat()


class BaseAPITestCase(APITestCase):
    def setUp(self):
        self.employer_user = User.objects.create_user(
            username="acme_hr", email="hr@acme.com", password="SecurePass123", role=Role.EMPLOYER
        )
        self.other_employer_user = User.objects.create_user(
            username="globex_hr", email="hr@globex.com", password="SecurePass123", role=Role.EMPLOYER
        )
        self.candidate_user = User.objects.create_user(
            username="jane", email="jane@example.com", password="SecurePass123", role=Role.CANDIDATE
        )
        self.other_candidate_user = User.objects.create_user(
            username="john", email="john@example.com", password="SecurePass123", role=Role.CANDIDATE
        )

        self.employer = EmployerProfile.objects.create(user=self.employer_user, company_name="Acme Corp")
        self.other_employer = EmployerProfile.objects.create(user=self.other_employer_user, company_name="Globex")
        self.candidate = CandidateProfile.objects.create(user=self.candidate_user, full_name="Jane Doe")
        self.other_candidate = CandidateProfile.objects.create(user=self.other_candidate_user, full_name="John Roe")

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def _make_job(self, employer=None, **overrides):
        data = dict(
            employer=employer or self.employer,
            title="Backend Developer",
            description="We are looking for a Python developer.",
            location="Lahore",
            employment_type=EmploymentType.FULL_TIME,
            experience_level=ExperienceLevel.ENTRY,
            salary_min=80000,
            salary_max=120000,
            currency="PKR",
            skills=["Python", "Django"],
            status=JobStatus.OPEN,
        )
        data.update(overrides)
        return Job.objects.create(**data)


class JobCreationTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse("jobs:job-list")

    def _payload(self, **overrides):
        payload = {
            "title": "Backend Developer",
            "description": "We are looking for a Python developer.",
            "location": "Lahore",
            "employment_type": "FULL_TIME",
            "experience_level": "ENTRY",
            "salary_min": 80000,
            "salary_max": 120000,
            "currency": "PKR",
            "skills": ["Python", "Django"],
            "application_deadline": tomorrow(),
        }
        payload.update(overrides)
        return payload

    def test_unauthenticated_user_cannot_create_job(self):
        response = self.client.post(self.url, self._payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_candidate_cannot_create_job(self):
        self._auth(self.candidate_user)
        response = self.client.post(self.url, self._payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_employer_can_create_job_and_ownership_is_server_derived(self):
        self._auth(self.employer_user)
        response = self.client.post(self.url, self._payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        job = Job.objects.get(pk=response.data["id"])
        self.assertEqual(job.employer, self.employer)

    def test_invalid_salary_range_rejected(self):
        self._auth(self.employer_user)
        response = self.client.post(self.url, self._payload(salary_min=100000, salary_max=50000), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_negative_salary_rejected(self):
        self._auth(self.employer_user)
        response = self.client.post(self.url, self._payload(salary_min=-100), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_deadline_rejected(self):
        self._auth(self.employer_user)
        response = self.client.post(self.url, self._payload(application_deadline=yesterday()), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_employment_type_rejected(self):
        self._auth(self.employer_user)
        response = self.client.post(self.url, self._payload(employment_type="NOT_A_TYPE"), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_blank_title_rejected(self):
        self._auth(self.employer_user)
        response = self.client.post(self.url, self._payload(title="   "), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_blank_description_rejected(self):
        self._auth(self.employer_user)
        response = self.client.post(self.url, self._payload(description=""), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class JobOwnershipTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.job = self._make_job()

    def _detail_url(self, job=None):
        return reverse("jobs:job-detail", args=[(job or self.job).pk])

    def _close_url(self, job=None):
        return reverse("jobs:job-close", args=[(job or self.job).pk])

    def test_owner_can_edit_own_job(self):
        self._auth(self.employer_user)
        response = self.client.patch(self._detail_url(), {"title": "Senior Backend Developer"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.job.refresh_from_db()
        self.assertEqual(self.job.title, "Senior Backend Developer")

    def test_other_employer_cannot_edit_job(self):
        self._auth(self.other_employer_user)
        response = self.client.patch(self._detail_url(), {"title": "Hijacked"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.job.refresh_from_db()
        self.assertEqual(self.job.title, "Backend Developer")

    def test_candidate_cannot_edit_job(self):
        self._auth(self.candidate_user)
        response = self.client.patch(self._detail_url(), {"title": "Hijacked"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_close_own_job(self):
        self._auth(self.employer_user)
        response = self.client.post(self._close_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, JobStatus.CLOSED)

    def test_other_employer_cannot_close_job(self):
        self._auth(self.other_employer_user)
        response = self.client.post(self._close_url())
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, JobStatus.OPEN)

    def test_owner_can_delete_own_job(self):
        self._auth(self.employer_user)
        response = self.client.delete(self._detail_url())
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_other_employer_cannot_delete_job(self):
        self._auth(self.other_employer_user)
        response = self.client.delete(self._detail_url())
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class JobListingTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.job1 = self._make_job(title="Python Backend Engineer", location="Lahore", skills=["Python", "Django"])
        self.job2 = self._make_job(
            title="Frontend Engineer",
            description="We are looking for a React developer to join our UI team.",
            location="Karachi",
            employment_type=EmploymentType.PART_TIME,
            experience_level=ExperienceLevel.MID,
            skills=["React", "JavaScript"],
        )
        self.closed_job = self._make_job(title="Closed Role", status=JobStatus.CLOSED)
        self.url = reverse("jobs:job-list")

    def test_public_can_list_jobs(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_closed_jobs_excluded_from_public_list(self):
        response = self.client.get(self.url)
        titles = [item["title"] for item in response.data["results"]]
        self.assertNotIn("Closed Role", titles)

    def test_job_detail_public(self):
        response = self.client.get(reverse("jobs:job-detail", args=[self.job1.pk]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Python Backend Engineer")

    def test_closed_job_detail_still_reachable_directly(self):
        response = self.client.get(reverse("jobs:job-detail", args=[self.closed_job.pk]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "CLOSED")

    def test_search_by_keyword(self):
        response = self.client.get(self.url, {"search": "Python"})
        titles = [item["title"] for item in response.data["results"]]
        self.assertIn("Python Backend Engineer", titles)
        self.assertNotIn("Frontend Engineer", titles)

    def test_filter_by_location(self):
        response = self.client.get(self.url, {"location": "Karachi"})
        titles = [item["title"] for item in response.data["results"]]
        self.assertEqual(titles, ["Frontend Engineer"])

    def test_filter_by_employment_type(self):
        response = self.client.get(self.url, {"employment_type": "PART_TIME"})
        titles = [item["title"] for item in response.data["results"]]
        self.assertEqual(titles, ["Frontend Engineer"])

    def test_combined_filters(self):
        response = self.client.get(self.url, {"search": "Engineer", "location": "Lahore"})
        titles = [item["title"] for item in response.data["results"]]
        self.assertEqual(titles, ["Python Backend Engineer"])

    def test_pagination_present(self):
        response = self.client.get(self.url)
        self.assertIn("count", response.data)
        self.assertIn("results", response.data)

    def test_ordering_by_created_at(self):
        response = self.client.get(self.url, {"ordering": "created_at"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_ordering_rejects_unapproved_field(self):
        response = self.client.get(self.url, {"ordering": "employer__user__password"})
        # Unapproved ordering fields are silently ignored by DRF's
        # OrderingFilter rather than causing a raw SQL error or field leak.
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ApplicationTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.job = self._make_job(application_deadline=timezone.localdate() + datetime.timedelta(days=5))
        self.closed_job = self._make_job(status=JobStatus.CLOSED)
        self.expired_job = self._make_job(
            application_deadline=timezone.localdate() - datetime.timedelta(days=1)
        )
        self.url = reverse("jobs:application-list-create")

        resume_file = SimpleUploadedFile("resume.pdf", PDF_BYTES, content_type="application/pdf")
        self.resume = Resume.objects.create(
            candidate=self.candidate,
            file=resume_file,
            original_filename="resume.pdf",
            content_type="application/pdf",
            file_size=len(PDF_BYTES),
        )
        other_resume_file = SimpleUploadedFile("other.pdf", PDF_BYTES, content_type="application/pdf")
        self.other_resume = Resume.objects.create(
            candidate=self.other_candidate,
            file=other_resume_file,
            original_filename="other.pdf",
            content_type="application/pdf",
            file_size=len(PDF_BYTES),
        )

    def test_candidate_can_apply(self):
        self._auth(self.candidate_user)
        response = self.client.post(
            self.url, {"job_id": self.job.id, "resume_id": self.resume.id, "cover_letter": "Hi"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        application = Application.objects.get(candidate=self.candidate, job=self.job)
        self.assertEqual(application.status, ApplicationStatus.APPLIED)

    def test_application_creates_employer_notification(self):
        self._auth(self.candidate_user)
        self.client.post(self.url, {"job_id": self.job.id, "resume_id": self.resume.id}, format="json")
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.employer_user, notification_type="NEW_APPLICATION"
            ).exists()
        )

    def test_unrelated_employer_does_not_receive_notification(self):
        self._auth(self.candidate_user)
        self.client.post(self.url, {"job_id": self.job.id, "resume_id": self.resume.id}, format="json")
        self.assertFalse(Notification.objects.filter(recipient=self.other_employer_user).exists())

    def test_employer_cannot_apply_as_candidate(self):
        self._auth(self.employer_user)
        response = self.client.post(self.url, {"job_id": self.job.id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_user_cannot_apply(self):
        response = self.client.post(self.url, {"job_id": self.job.id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_nonexistent_job_fails(self):
        self._auth(self.candidate_user)
        response = self.client.post(self.url, {"job_id": 999999}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_closed_job_rejects_application(self):
        self._auth(self.candidate_user)
        response = self.client.post(self.url, {"job_id": self.closed_job.id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_expired_job_rejects_application(self):
        self._auth(self.candidate_user)
        response = self.client.post(self.url, {"job_id": self.expired_job.id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_resume_ownership_fails(self):
        self._auth(self.candidate_user)
        response = self.client.post(
            self.url, {"job_id": self.job.id, "resume_id": self.other_resume.id}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_application_fails(self):
        self._auth(self.candidate_user)
        self.client.post(self.url, {"job_id": self.job.id, "resume_id": self.resume.id}, format="json")
        response = self.client.post(self.url, {"job_id": self.job.id, "resume_id": self.resume.id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Application.objects.filter(candidate=self.candidate, job=self.job).count(), 1)

    def test_client_cannot_set_status_or_candidate_on_create(self):
        self._auth(self.candidate_user)
        response = self.client.post(
            self.url,
            {"job_id": self.job.id, "resume_id": self.resume.id, "status": "HIRED"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        application = Application.objects.get(candidate=self.candidate, job=self.job)
        self.assertEqual(application.status, ApplicationStatus.APPLIED)

    def test_candidate_sees_only_own_applications(self):
        self._auth(self.candidate_user)
        self.client.post(self.url, {"job_id": self.job.id, "resume_id": self.resume.id}, format="json")

        self._auth(self.other_candidate_user)
        response = self.client.get(self.url)
        self.assertEqual(response.data["count"], 0)

    def test_candidate_id_query_param_cannot_bypass_ownership(self):
        self._auth(self.candidate_user)
        self.client.post(self.url, {"job_id": self.job.id, "resume_id": self.resume.id}, format="json")

        self._auth(self.other_candidate_user)
        response = self.client.get(self.url, {"candidate_id": self.candidate.id})
        self.assertEqual(response.data["count"], 0)


class ApplicationDetailAndIDORTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.job = self._make_job()
        self.application = Application.objects.create(
            candidate=self.candidate, job=self.job, status=ApplicationStatus.APPLIED
        )
        self.detail_url = reverse("jobs:application-detail", args=[self.application.id])

    def test_owning_candidate_can_view_application(self):
        self._auth(self.candidate_user)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_owning_employer_can_view_application(self):
        self._auth(self.employer_user)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unrelated_candidate_cannot_view_application(self):
        self._auth(self.other_candidate_user)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unrelated_employer_cannot_view_application(self):
        self._auth(self.other_employer_user)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_user_cannot_view_application(self):
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class EmployerApplicationListTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.job_a = self._make_job(employer=self.employer, title="Job A")
        self.job_b = self._make_job(employer=self.other_employer, title="Job B")
        Application.objects.create(candidate=self.candidate, job=self.job_a)
        Application.objects.create(candidate=self.other_candidate, job=self.job_b)
        self.url = reverse("jobs:employer-application-list")

    def test_employer_sees_only_applications_for_own_jobs(self):
        self._auth(self.employer_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["job_title"], "Job A")

    def test_employer_b_cannot_see_employer_a_applications(self):
        self._auth(self.other_employer_user)
        response = self.client.get(self.url)
        job_titles = [item["job_title"] for item in response.data["results"]]
        self.assertNotIn("Job A", job_titles)

    def test_candidate_cannot_access_employer_application_list(self):
        self._auth(self.candidate_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class ApplicationStatusTransitionTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.job = self._make_job()
        self.application = Application.objects.create(
            candidate=self.candidate, job=self.job, status=ApplicationStatus.APPLIED
        )
        self.status_url = reverse("jobs:application-status", args=[self.application.id])
        self.withdraw_url = reverse("jobs:application-withdraw", args=[self.application.id])

    def test_owning_employer_can_advance_status(self):
        self._auth(self.employer_user)
        response = self.client.patch(self.status_url, {"status": "UNDER_REVIEW"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, ApplicationStatus.UNDER_REVIEW)

    def test_status_change_notifies_candidate(self):
        self._auth(self.employer_user)
        self.client.patch(self.status_url, {"status": "UNDER_REVIEW"}, format="json")
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.candidate_user, notification_type="APPLICATION_STATUS_CHANGE"
            ).exists()
        )

    def test_unrelated_employer_cannot_change_status(self):
        self._auth(self.other_employer_user)
        response = self.client.patch(self.status_url, {"status": "UNDER_REVIEW"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, ApplicationStatus.APPLIED)

    def test_candidate_cannot_set_own_status_to_hired(self):
        self._auth(self.candidate_user)
        response = self.client.patch(self.status_url, {"status": "HIRED"}, format="json")
        # Candidates are not permitted to use the employer status endpoint at all.
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, ApplicationStatus.APPLIED)

    def test_invalid_transition_rejected(self):
        self._auth(self.employer_user)
        # APPLIED -> HIRED is not a legal direct transition.
        response = self.client.patch(self.status_url, {"status": "HIRED"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, ApplicationStatus.APPLIED)

    def test_invalid_status_value_rejected(self):
        self._auth(self.employer_user)
        response = self.client.patch(self.status_url, {"status": "NOT_A_STATUS"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_candidate_can_withdraw_own_application(self):
        self._auth(self.candidate_user)
        response = self.client.post(self.withdraw_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, ApplicationStatus.WITHDRAWN)

    def test_other_candidate_cannot_withdraw_application(self):
        self._auth(self.other_candidate_user)
        response = self.client.post(self.withdraw_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_withdraw_hired_application(self):
        self.application.status = ApplicationStatus.HIRED
        self.application.save()
        self._auth(self.candidate_user)
        response = self.client.post(self.withdraw_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_withdrawn_application_allows_reapplying(self):
        self._auth(self.candidate_user)
        self.client.post(self.withdraw_url)

        apply_url = reverse("jobs:application-list-create")
        response = self.client.post(apply_url, {"job_id": self.job.id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class ApplicationResumeAccessTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.job = self._make_job()
        resume_file = SimpleUploadedFile("resume.pdf", PDF_BYTES, content_type="application/pdf")
        self.resume = Resume.objects.create(
            candidate=self.candidate,
            file=resume_file,
            original_filename="resume.pdf",
            content_type="application/pdf",
            file_size=len(PDF_BYTES),
        )
        self.application = Application.objects.create(candidate=self.candidate, job=self.job, resume=self.resume)
        self.url = reverse("jobs:application-resume", args=[self.application.id])

    def test_owning_candidate_can_download(self):
        self._auth(self.candidate_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_owning_employer_can_download(self):
        self._auth(self.employer_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unrelated_employer_cannot_download(self):
        self._auth(self.other_employer_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unrelated_candidate_cannot_download(self):
        self._auth(self.other_candidate_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_download(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class NotificationTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.job = self._make_job()
        self.application = Application.objects.create(candidate=self.candidate, job=self.job)
        self.notification = Notification.objects.create(
            recipient=self.employer_user,
            application=self.application,
            message="New application received.",
            notification_type="NEW_APPLICATION",
        )
        self.other_notification = Notification.objects.create(
            recipient=self.other_employer_user,
            message="Unrelated notification.",
            notification_type="NEW_APPLICATION",
        )
        self.list_url = reverse("jobs:notification-list")

    def test_user_sees_only_own_notifications(self):
        self._auth(self.employer_user)
        response = self.client.get(self.list_url)
        self.assertEqual(response.data["count"], 1)

    def test_unread_filter(self):
        self._auth(self.employer_user)
        response = self.client.get(self.list_url, {"is_read": "false"})
        self.assertEqual(response.data["count"], 1)

    def test_mark_own_notification_read(self):
        self._auth(self.employer_user)
        url = reverse("jobs:notification-read", args=[self.notification.id])
        response = self.client.patch(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_read)

    def test_cannot_mark_another_users_notification_read(self):
        self._auth(self.employer_user)
        url = reverse("jobs:notification-read", args=[self.other_notification.id])
        response = self.client.patch(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.other_notification.refresh_from_db()
        self.assertFalse(self.other_notification.is_read)

    def test_unauthenticated_cannot_list_notifications(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
