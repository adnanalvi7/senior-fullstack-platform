from django.db import transaction
from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from common.exceptions import ConflictException, int_query_param
from common.permissions import IsTenantMember, CanMutateProject, TenantObjectPermission
from apps.analytics.services import AnalyticsService
from apps.projects.models import Project
from apps.projects.serializers import ProjectSerializer

class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated, IsTenantMember, CanMutateProject, TenantObjectPermission]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'category', 'property__name', 'property__code']
    ordering_fields = ['created_at', 'budget_amount', 'actual_cost', 'status', 'title']
    ordering = ['-created_at', '-id']

    def get_queryset(self):
        qs = Project.objects.for_user(self.request.user).select_related('property', 'submitted_by')

        if self.request.method in ('PUT', 'PATCH', 'DELETE'):
            # Writes re-read the row under the same lock ApprovalWorkflowService takes, so an
            # edit can never be computed from a status that an approval just changed.
            qs = qs.select_for_update(of=('self',))

        property_id = int_query_param(self.request, 'property_id')
        if property_id is not None:
            qs = qs.filter(property_id=property_id)

        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category=category)

        status_val = self.request.query_params.get('status')
        if status_val:
            qs = qs.filter(status=status_val)

        fiscal_period = self.request.query_params.get('fiscal_period')
        if fiscal_period and fiscal_period != 'ALL':
            qs = qs.filter(fiscal_period=fiscal_period)

        return qs

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    def perform_create(self, serializer):
        user = self.request.user
        project = serializer.save(org=user.org, submitted_by=user)
        AnalyticsService.mark_buckets_dirty(project.org_id, [(project.property_id, project.fiscal_period)])

    def perform_update(self, serializer):
        before = (serializer.instance.property_id, serializer.instance.fiscal_period)
        project = serializer.save()
        # A move between properties / fiscal periods changes two buckets.
        AnalyticsService.mark_buckets_dirty(project.org_id, {before, (project.property_id, project.fiscal_period)})

    def perform_destroy(self, instance):
        if instance.status != 'draft':
            raise ConflictException(
                f"Only draft projects can be deleted; this project is '{instance.status}' and part of the approval record."
            )
        bucket = (instance.property_id, instance.fiscal_period)
        org_id = instance.org_id
        super().perform_destroy(instance)
        AnalyticsService.mark_buckets_dirty(org_id, [bucket])
