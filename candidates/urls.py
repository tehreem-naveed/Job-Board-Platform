from django.urls import path

from .views import MyCandidateProfileView, MyResumeDownloadView, MyResumeView

app_name = "candidates"

urlpatterns = [
    path("me/", MyCandidateProfileView.as_view(), name="me"),
    path("me/resume/", MyResumeView.as_view(), name="my-resume"),
    path("me/resume/download/", MyResumeDownloadView.as_view(), name="my-resume-download"),
]
