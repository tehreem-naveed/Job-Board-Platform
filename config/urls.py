from django.contrib import admin
from django.urls import include, path

from candidates.views import MyResumeDownloadView, MyResumeView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/employers/", include("employers.urls")),
    path("api/candidates/", include("candidates.urls")),
    path("api/", include("jobs.urls")),
    # Convenience top-level resume routes, in addition to /api/candidates/me/resume/.
    path("api/resumes/", MyResumeView.as_view(), name="resumes-root"),
    path("api/resumes/download/", MyResumeDownloadView.as_view(), name="resumes-root-download"),
]
