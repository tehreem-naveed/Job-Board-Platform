from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import FileResponse, Http404
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsCandidate
from .models import CandidateProfile, Resume
from .serializers import CandidateProfileSerializer, ResumeSerializer, ResumeUploadSerializer
from .services import replace_resume


class MyCandidateProfileView(generics.RetrieveUpdateAPIView):
    """GET/PATCH the authenticated candidate's own profile."""

    serializer_class = CandidateProfileSerializer
    permission_classes = [IsCandidate]

    def get_object(self):
        if not self.request.user.is_candidate:
            raise PermissionDenied("Only candidate accounts have a candidate profile.")
        profile, _ = CandidateProfile.objects.get_or_create(user=self.request.user)
        return profile


class MyResumeView(APIView):
    """
    GET: current resume metadata (or 404 if none uploaded).
    POST: upload/replace the current resume.
    DELETE: remove the current resume.
    """

    permission_classes = [IsCandidate]

    def _profile(self, request):
        profile, _ = CandidateProfile.objects.get_or_create(user=request.user)
        return profile

    def get(self, request):
        profile = self._profile(request)
        resume = Resume.objects.filter(candidate=profile).first()
        if not resume:
            return Response({"success": False, "error": "No resume uploaded yet.", "code": "NOT_FOUND"}, status=404)
        return Response({"success": True, "resume": ResumeSerializer(resume).data})

    def post(self, request):
        profile = self._profile(request)
        upload_serializer = ResumeUploadSerializer(data=request.data)
        upload_serializer.is_valid(raise_exception=True)
        uploaded_file = upload_serializer.validated_data["file"]
        try:
            resume = replace_resume(profile, uploaded_file)
        except DjangoValidationError as exc:
            raise ValidationError({"file": exc.messages})
        return Response(
            {"success": True, "resume": ResumeSerializer(resume).data},
            status=status.HTTP_201_CREATED,
        )

    def delete(self, request):
        profile = self._profile(request)
        resume = Resume.objects.filter(candidate=profile).first()
        if not resume:
            return Response({"success": False, "error": "No resume to delete.", "code": "NOT_FOUND"}, status=404)
        file_ref = resume.file
        resume.delete()
        if file_ref and file_ref.name:
            file_ref.storage.delete(file_ref.name)
        return Response({"success": True, "message": "Resume deleted."})


class MyResumeDownloadView(APIView):
    """Stream the authenticated candidate's own resume file."""

    permission_classes = [IsCandidate]

    def get(self, request):
        profile, _ = CandidateProfile.objects.get_or_create(user=request.user)
        resume = Resume.objects.filter(candidate=profile).first()
        if not resume or not resume.file:
            raise Http404("No resume uploaded.")
        return FileResponse(
            resume.file.open("rb"),
            as_attachment=True,
            filename=resume.original_filename or "resume",
        )
