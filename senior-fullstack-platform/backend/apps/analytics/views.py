from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from common.constants import ALL_PERIODS
from common.permissions import IsTenantMember, IsOrgAdmin
from apps.analytics.serializers import DashboardQuerySerializer
from apps.analytics.services import AnalyticsService
from apps.analytics.tasks import recalculate_all_aggregates

class DashboardAnalyticsView(APIView):
    """
    Returns high-performance precomputed dashboard aggregates and charts.
    Strictly isolated and scoped to the authenticated user's organization and property entitlements.
    Served from a version-keyed Redis cache, falling back to the rollup table.
    """
    permission_classes = [IsAuthenticated, IsTenantMember]

    def get(self, request):
        query_serializer = DashboardQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)

        fiscal_period = query_serializer.validated_data.get('fiscal_period', ALL_PERIODS)
        property_id = query_serializer.validated_data.get('property_id')

        data = AnalyticsService.get_dashboard_data(
            user=request.user,
            fiscal_period=fiscal_period,
            selected_property_id=property_id
        )
        return Response(data, status=status.HTTP_200_OK)


class RefreshAnalyticsView(APIView):
    """
    Triggers an asynchronous recalculation of all precomputed property aggregates
    for the user's organization via Celery.
    """
    permission_classes = [IsAuthenticated, IsTenantMember, IsOrgAdmin]

    def post(self, request):
        task = recalculate_all_aggregates.delay(org_id=request.user.org_id)
        return Response({
            'success': True,
            'message': 'Background aggregate rebuild dispatched.',
            'task_id': task.id
        }, status=status.HTTP_202_ACCEPTED)
