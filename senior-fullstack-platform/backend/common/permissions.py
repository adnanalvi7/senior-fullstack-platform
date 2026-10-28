from rest_framework import permissions
from rest_framework.exceptions import NotFound

class IsTenantMember(permissions.BasePermission):
    """
    Ensures the user is authenticated and belongs to an active tenant organization.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            getattr(request.user, 'org_id', None) is not None
        )


class HasRole(permissions.BasePermission):
    """
    Factory / parameterized permission checking user's assigned role.
    """
    allowed_roles = []

    def __init__(self, *roles):
        if roles:
            self.allowed_roles = roles

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        user_role = getattr(request.user, 'role', None)
        return user_role in self.allowed_roles


class IsOrgAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            getattr(request.user, 'role', None) == 'org_admin'
        )


class CanMutateProject(permissions.BasePermission):
    """Only org_admin and property_manager can create or edit projects."""
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(
            request.user and
            request.user.is_authenticated and
            getattr(request.user, 'role', None) in ('org_admin', 'property_manager')
        )


class CanApproveProject(permissions.BasePermission):
    """org_admin, property_manager, and approver can perform approval transitions."""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            getattr(request.user, 'role', None) in ('org_admin', 'property_manager', 'approver')
        )


class TenantObjectPermission(permissions.BasePermission):
    """
    Defence-in-depth object check behind the scoped querysets (`for_user`).
    Raises NotFound (404) rather than Forbidden (403) so out-of-scope IDs are
    indistinguishable from nonexistent ones.
    """
    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated or getattr(obj, 'org_id', None) != user.org_id:
            raise NotFound(detail="Resource not found.")
        if user.role == 'org_admin':
            return True
        from apps.properties.models import Property
        prop_id = obj.id if isinstance(obj, Property) else getattr(obj, 'property_id', None)
        if prop_id is None or prop_id not in set(user.property_ids):
            raise NotFound(detail="Resource not found.")
        return True
