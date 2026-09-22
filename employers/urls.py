from django.urls import path

from .views import MyEmployerProfileView

app_name = "employers"

urlpatterns = [
    path("me/", MyEmployerProfileView.as_view(), name="me"),
]
