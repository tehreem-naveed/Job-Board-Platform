from rest_framework.permissions import BasePermission


class IsOwnerCandidate(BasePermission):
    """Object-level permission: only the owning candidate may access/modify."""

    message = "You do not have permission to access this candidate resource."

    def has_object_permission(self, request, view, obj):
        candidate = getattr(obj, "candidate", obj)
        return candidate.user_id == request.user.id
