from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsCandidate(BasePermission):
    """Grants access only to authenticated users with the CANDIDATE role."""

    message = "Only candidate accounts can perform this action."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_candidate)


class IsEmployer(BasePermission):
    """Grants access only to authenticated users with the EMPLOYER role."""

    message = "Only employer accounts can perform this action."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_employer)


class IsAdminRole(BasePermission):
    """Grants access only to admin/staff users."""

    message = "Only administrators can perform this action."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_admin_role)


class ReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS
