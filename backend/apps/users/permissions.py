from rest_framework.permissions import BasePermission


class IsVerifiedUser(BasePermission):
    """Default for every API view: signed in *and* phone verified.
    Auth endpoints opt out with AllowAny."""

    message = "Verify your phone number to continue."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, "phone_verified", False))
