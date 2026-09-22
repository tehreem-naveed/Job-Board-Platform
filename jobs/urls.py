from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ApplicationDetailView,
    ApplicationListCreateView,
    ApplicationResumeDownloadView,
    ApplicationStatusUpdateView,
    ApplicationWithdrawView,
    CloseJobView,
    EmployerApplicationListView,
    JobViewSet,
    NotificationListView,
    NotificationMarkReadView,
)

app_name = "jobs"

router = DefaultRouter()
router.register("jobs", JobViewSet, basename="job")

urlpatterns = [
    path("", include(router.urls)),
    path("jobs/<int:pk>/close/", CloseJobView.as_view(), name="job-close"),
    path("applications/", ApplicationListCreateView.as_view(), name="application-list-create"),
    path("applications/<int:pk>/", ApplicationDetailView.as_view(), name="application-detail"),
    path("applications/<int:pk>/status/", ApplicationStatusUpdateView.as_view(), name="application-status"),
    path("applications/<int:pk>/withdraw/", ApplicationWithdrawView.as_view(), name="application-withdraw"),
    path("applications/<int:pk>/resume/", ApplicationResumeDownloadView.as_view(), name="application-resume"),
    path("employer/applications/", EmployerApplicationListView.as_view(), name="employer-application-list"),
    path("notifications/", NotificationListView.as_view(), name="notification-list"),
    path("notifications/<int:pk>/read/", NotificationMarkReadView.as_view(), name="notification-read"),
]
