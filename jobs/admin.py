from django.contrib import admin

from .models import Application, Job, Notification


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("title", "employer", "status", "location", "employment_type", "created_at", "application_deadline")
    list_filter = ("status", "employment_type", "experience_level")
    search_fields = ("title", "location", "employer__company_name")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("employer",)


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("candidate", "job", "status", "applied_at", "updated_at")
    list_filter = ("status",)
    search_fields = ("candidate__full_name", "candidate__user__username", "job__title")
    readonly_fields = ("applied_at", "updated_at")
    autocomplete_fields = ("candidate", "job")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "notification_type", "is_read", "created_at")
    list_filter = ("notification_type", "is_read")
    search_fields = ("recipient__username", "message")
    readonly_fields = ("created_at",)
