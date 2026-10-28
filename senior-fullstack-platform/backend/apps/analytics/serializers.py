from rest_framework import serializers
from common.constants import ALL_PERIODS, FISCAL_PERIODS
from apps.analytics.models import PropertyAggregateRollup

class DashboardQuerySerializer(serializers.Serializer):
    # Closed vocabulary: unknown periods are a 400, never a synchronous recompute.
    fiscal_period = serializers.ChoiceField(choices=(ALL_PERIODS, *FISCAL_PERIODS), required=False, default=ALL_PERIODS)
    property_id = serializers.IntegerField(required=False, allow_null=True, default=None, min_value=1)


class PropertyAggregateRollupSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyAggregateRollup
        fields = '__all__'
