from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsJobOwnerOrReadOnly(BasePermission):
    """
    Anyone can read (list/retrieve) jobs. Only the employer that owns a job
    may update or delete it.
    """

    message = "You do not have permission to modify this job."

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated and request.user.is_employer)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return obj.employer.user_id == request.user.id


class IsApplicationParticipant(BasePermission):
    """
    Only the candidate who owns the application, or the employer who owns
    the job it was submitted to, may view/act on it.
    """

    message = "You do not have permission to access this application."

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_candidate:
            return obj.candidate.user_id == user.id
        if user.is_employer:
            return obj.job.employer.user_id == user.id
        return user.is_admin_role
