from rest_framework import serializers
from apps.properties.models import Property, Budget

class PropertySerializer(serializers.ModelSerializer):
    class Meta:
        model = Property
        fields = ('id', 'org_id', 'name', 'code', 'created_at')
        read_only_fields = ('id', 'org_id', 'created_at')


class BudgetSerializer(serializers.ModelSerializer):
    property_name = serializers.ReadOnlyField(source='property.name')
    property_code = serializers.ReadOnlyField(source='property.code')

    class Meta:
        model = Budget
        fields = ('id', 'org_id', 'property_id', 'property_name', 'property_code', 'fiscal_period', 'allocated_amount', 'created_at', 'updated_at')
        read_only_fields = ('id', 'org_id', 'created_at', 'updated_at')
