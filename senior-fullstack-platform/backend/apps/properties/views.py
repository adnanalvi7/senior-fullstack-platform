from rest_framework import viewsets, generics
from rest_framework.permissions import IsAuthenticated
from common.exceptions import int_query_param
from common.permissions import IsTenantMember, TenantObjectPermission
from apps.properties.models import Property, Budget
from apps.properties.serializers import PropertySerializer, BudgetSerializer

class PropertyViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PropertySerializer
    permission_classes = [IsAuthenticated, IsTenantMember, TenantObjectPermission]

    def get_queryset(self):
        return Property.objects.for_user(self.request.user)


class BudgetListView(generics.ListAPIView):
    serializer_class = BudgetSerializer
    permission_classes = [IsAuthenticated, IsTenantMember]

    def get_queryset(self):
        qs = Budget.objects.for_user(self.request.user)
        fiscal_period = self.request.query_params.get('fiscal_period')
        if fiscal_period:
            qs = qs.filter(fiscal_period=fiscal_period)
        property_id = int_query_param(self.request, 'property_id')
        if property_id is not None:
            qs = qs.filter(property_id=property_id)
        return qs
