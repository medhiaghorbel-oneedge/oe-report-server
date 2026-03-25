from rest_framework.permissions import IsAuthenticated, BasePermission
from django.conf import settings


class IsAuthenticatedOrDevDisabled(BasePermission):
    """
    Grants access when DISABLE_AUTH=True in settings (dev only).
    Falls back to standard IsAuthenticated in all other cases.
    """

    def has_permission(self, request, view):
        if getattr(settings, "DISABLE_AUTH", False):
            return True
        return IsAuthenticated().has_permission(request, view)
