from django.db import models

class TenantScopedQuerySet(models.QuerySet):
    """
    Centralized QuerySet providing row-level security (RLS) scoping
    based on the authenticated user's organization and property assignments.

    Every request-path read and write must start from `.for_user(user)`; this is enforced
    by tests/test_authz_routes.py, which walks every registered object route and asserts
    out-of-scope IDs return 404. Unscoped `.objects` access is reserved for workers/seeding.
    """
    def for_user(self, user):
        if not user or not user.is_authenticated:
            return self.none()

        # If user has no organization associated, deny access
        if not getattr(user, 'org_id', None):
            return self.none()

        # Check if the model has an 'org' or 'org_id' field
        has_org_field = any(f.name in ('org', 'org_id') for f in self.model._meta.fields)
        if not has_org_field:
            return self.none()

        # Base filter by tenant organization
        qs = self.filter(org_id=user.org_id)

        # Organization Admins have visibility across the entire tenant organization
        if getattr(user, 'role', None) == 'org_admin':
            return qs

        # Non-admins (property_manager, approver, viewer) are strictly scoped to their assigned properties.
        # Materialised id list (one tiny indexed read): a literal IN-list lets the planner use the
        # (property, created_at) ordering index; a semi-join subquery measured ~3x slower.
        assigned_prop_ids = list(user.assigned_properties.values_list('id', flat=True))

        # Check if the model is Property itself or has a property/property_id field
        if self.model._meta.model_name == 'property':
            return qs.filter(id__in=assigned_prop_ids)

        has_property_field = any(f.name in ('property', 'property_id') for f in self.model._meta.fields)
        if has_property_field:
            return qs.filter(property_id__in=assigned_prop_ids)

        return qs


class TenantScopedManager(models.Manager.from_queryset(TenantScopedQuerySet)):
    """Default manager implementing centralized row-level security."""
    pass
