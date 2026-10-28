from rest_framework import serializers
from apps.approvals.models import ApprovalEvent

class ApprovalActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(
        choices=['submit', 'manager_approve', 'finance_approve', 'final_approve', 'reject'],
        required=True
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class ApprovalEventSerializer(serializers.ModelSerializer):
    actor_email = serializers.ReadOnlyField(source='actor.email')

    class Meta:
        model = ApprovalEvent
        fields = (
            'id', 'project_id', 'org_id', 'property_id',
            'from_status', 'to_status', 'actor_id', 'actor_email',
            'notes', 'created_at'
        )
        read_only_fields = fields
