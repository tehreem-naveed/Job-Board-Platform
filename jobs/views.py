from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import FileResponse, Http404
from rest_framework import generics, permissions, status, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsCandidate, IsEmployer
from candidates.models import Resume
from employers.models import EmployerProfile

from .filters import JobFilter
from .models import Application, Job, JobStatus, Notification
from .permissions import IsApplicationParticipant, IsJobOwnerOrReadOnly
from .serializers import (
    ApplicationCreateSerializer,
    ApplicationSerializer,
    ApplicationStatusUpdateSerializer,
    EmployerApplicationSerializer,
    JobDetailSerializer,
    JobListSerializer,
    NotificationSerializer,
)
from .services import ApplicationError, create_application, update_application_status, withdraw_application


class JobViewSet(viewsets.ModelViewSet):
    """
    Public read access; only the owning employer may create/update/delete.
    Supports search, filtering, ordering and pagination.
    """

    permission_classes = [IsJobOwnerOrReadOnly]
    filterset_class = JobFilter
    search_fields = ["title", "description", "location", "employer__company_name"]
    ordering_fields = ["created_at", "application_deadline", "salary_min", "salary_max", "title"]
    ordering = ["-created_at"]

    def get_queryset(self):
        from django.db.models import Q

        qs = Job.objects.select_related("employer", "employer__user")

        if self.action != "list":
            # Detail/update/destroy operate on the full queryset - a job's
            # detail page remains reachable (showing its real status) even
            # once closed; ownership for writes is enforced separately by
            # IsJobOwnerOrReadOnly.
            return qs

        user = self.request.user
        if user.is_authenticated and user.is_employer:
            # An employer's listing additionally includes their own closed
            # jobs alongside every open job on the platform.
            return qs.filter(Q(status=JobStatus.OPEN) | Q(employer__user=user))
        return qs.filter(status=JobStatus.OPEN)

    def get_serializer_class(self):
        if self.action == "list":
            return JobListSerializer
        return JobDetailSerializer

    def perform_create(self, serializer):
        if not self.request.user.is_employer:
            raise PermissionDenied("Only employer accounts can create jobs.")
        employer_profile, _ = EmployerProfile.objects.get_or_create(
            user=self.request.user,
            defaults={"company_name": self.request.user.username},
        )
        serializer.save(employer=employer_profile)

    def perform_update(self, serializer):
        job = self.get_object()
        try:
            serializer.save()
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)


class CloseJobView(APIView):
    """POST: close (disable) a job owned by the authenticated employer."""

    permission_classes = [IsEmployer]

    def post(self, request, pk):
        try:
            job = Job.objects.get(pk=pk)
        except Job.DoesNotExist:
            raise Http404
        if job.employer.user_id != request.user.id:
            raise PermissionDenied("You do not have permission to close this job.")
        job.status = JobStatus.CLOSED
        job.save(update_fields=["status", "updated_at"])
        return Response({"success": True, "job": JobDetailSerializer(job).data})


class ApplicationListCreateView(generics.GenericAPIView):
    """
    GET: the authenticated candidate's own applications.
    POST: apply to a job as the authenticated candidate.
    """

    permission_classes = [IsCandidate]

    def get_serializer_class(self):
        return ApplicationCreateSerializer if self.request.method == "POST" else ApplicationSerializer

    def get(self, request):
        from candidates.models import CandidateProfile

        profile, _ = CandidateProfile.objects.get_or_create(user=request.user)
        applications = Application.objects.filter(candidate=profile).select_related("job", "job__employer", "resume")
        page = self.paginate_queryset(applications)
        serializer = ApplicationSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    def post(self, request):
        from candidates.models import CandidateProfile

        serializer = ApplicationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        profile, _ = CandidateProfile.objects.get_or_create(user=request.user)

        resume = None
        resume_id = data.get("resume_id")
        if resume_id is not None:
            resume = Resume.objects.filter(pk=resume_id).first()
            if resume is None:
                raise ValidationError({"resume_id": "Resume not found."})
        else:
            resume = Resume.objects.filter(candidate=profile).first()

        try:
            application = create_application(
                candidate_profile=profile,
                job_id=data["job_id"],
                resume=resume,
                cover_letter=data.get("cover_letter", ""),
            )
        except ApplicationError as exc:
            raise exc

        return Response(
            {"success": True, "application": ApplicationSerializer(application).data},
            status=status.HTTP_201_CREATED,
        )


class ApplicationDetailView(generics.RetrieveAPIView):
    """Candidates see their own application; employers see applications to their jobs."""

    queryset = Application.objects.select_related(
        "job", "job__employer", "job__employer__user", "candidate", "candidate__user", "resume"
    )
    permission_classes = [permissions.IsAuthenticated, IsApplicationParticipant]

    def get_serializer_class(self):
        user = self.request.user
        if user.is_employer:
            return EmployerApplicationSerializer
        return ApplicationSerializer


class ApplicationStatusUpdateView(APIView):
    """PATCH: employer updates an application's status for a job they own."""

    permission_classes = [IsEmployer]

    def patch(self, request, pk):
        try:
            application = Application.objects.select_related("job", "job__employer", "candidate", "candidate__user").get(pk=pk)
        except Application.DoesNotExist:
            raise Http404

        serializer = ApplicationStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        application = update_application_status(
            application=application,
            new_status=serializer.validated_data["status"],
            actor=request.user,
        )
        return Response(
            {"success": True, "application": EmployerApplicationSerializer(application).data}
        )


class ApplicationWithdrawView(APIView):
    """POST: candidate withdraws their own application."""

    permission_classes = [IsCandidate]

    def post(self, request, pk):
        try:
            application = Application.objects.select_related("candidate", "job").get(pk=pk)
        except Application.DoesNotExist:
            raise Http404

        application = withdraw_application(application=application, actor=request.user)
        return Response({"success": True, "application": ApplicationSerializer(application).data})


class ApplicationResumeDownloadView(APIView):
    """
    Stream the resume attached to a specific application.
    Only the owning candidate, or the employer who owns the job the
    application was submitted to, may download it.
    """

    permission_classes = [permissions.IsAuthenticated, IsApplicationParticipant]

    def get(self, request, pk):
        try:
            application = Application.objects.select_related(
                "job", "job__employer", "candidate", "resume"
            ).get(pk=pk)
        except Application.DoesNotExist:
            raise Http404
        self.check_object_permissions(request, application)

        resume = application.resume
        if not resume or not resume.file:
            raise Http404("No resume attached to this application.")

        return FileResponse(
            resume.file.open("rb"),
            as_attachment=True,
            filename=resume.original_filename or "resume",
        )


class EmployerApplicationListView(generics.GenericAPIView):
    """GET: applications submitted to jobs owned by the authenticated employer."""

    permission_classes = [IsEmployer]
    serializer_class = EmployerApplicationSerializer
    filterset_fields = ["status", "job"]

    def get(self, request):
        applications = (
            Application.objects.filter(job__employer__user=request.user)
            .select_related("job", "candidate")
            .order_by("-applied_at")
        )
        job_id = request.query_params.get("job")
        status_filter = request.query_params.get("status")
        if job_id:
            applications = applications.filter(job_id=job_id)
        if status_filter:
            applications = applications.filter(status=status_filter)

        page = self.paginate_queryset(applications)
        serializer = EmployerApplicationSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)


class NotificationListView(generics.GenericAPIView):
    """GET: the authenticated user's own notifications."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NotificationSerializer

    def get(self, request):
        notifications = Notification.objects.filter(recipient=request.user)
        is_read = request.query_params.get("is_read")
        if is_read is not None:
            notifications = notifications.filter(is_read=is_read.lower() == "true")
        page = self.paginate_queryset(notifications)
        serializer = NotificationSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)


class NotificationMarkReadView(APIView):
    """PATCH: mark a single notification (belonging to the requester) as read."""

    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        try:
            notification = Notification.objects.get(pk=pk, recipient=request.user)
        except Notification.DoesNotExist:
            raise Http404
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        return Response({"success": True, "notification": NotificationSerializer(notification).data})
