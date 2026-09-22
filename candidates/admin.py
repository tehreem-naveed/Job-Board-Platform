from django.contrib import admin

from .models import CandidateProfile, Resume


@admin.register(CandidateProfile)
class CandidateProfileAdmin(admin.ModelAdmin):
    list_display = ("full_name", "user", "location", "created_at")
    search_fields = ("full_name", "user__username", "user__email", "location")
    list_filter = ("location",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Resume)
class ResumeAdmin(admin.ModelAdmin):
    list_display = ("candidate", "original_filename", "file_size", "uploaded_at")
    search_fields = ("candidate__full_name", "candidate__user__username", "original_filename")
    readonly_fields = ("uploaded_at", "updated_at", "file_size", "content_type")
