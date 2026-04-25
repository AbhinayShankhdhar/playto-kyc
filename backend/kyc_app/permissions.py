from rest_framework.permissions import BasePermission


class IsMerchant(BasePermission):
    """Only users with role=merchant can access."""
    message = "Only merchants can perform this action."

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and hasattr(request.user, 'profile')
            and request.user.profile.is_merchant
        )


class IsReviewer(BasePermission):
    """Only users with role=reviewer can access."""
    message = "Only reviewers can perform this action."

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and hasattr(request.user, 'profile')
            and request.user.profile.is_reviewer
        )


class IsOwnerOrReviewer(BasePermission):
    """
    Object-level permission:
    - Merchant can only access their OWN submission.
    - Reviewer can access ANY submission.

    This is the key guard that stops merchant A from seeing merchant B's data.
    """
    message = "You do not have permission to access this submission."

    def has_object_permission(self, request, view, obj):
        user = request.user
        # Reviewer sees all
        if hasattr(user, 'profile') and user.profile.is_reviewer:
            return True
        # Merchant sees only their own
        return obj.merchant == user
