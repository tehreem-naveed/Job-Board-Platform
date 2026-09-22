from django.contrib import admin

from .models import EmployerProfile


@admin.register(EmployerProfile)
class EmployerProfileAdmin(admin.ModelAdmin):
    list_display = ("company_name", "user", "industry", "location", "created_at")
    list_filter = ("industry",)
    search_fields = ("company_name", "user__username", "user__email", "location")
    readonly_fields = ("created_at", "updated_at")
