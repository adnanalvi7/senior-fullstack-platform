from decimal import Decimal
from rest_framework import serializers
from common.exceptions import ConflictException
from apps.projects.models import Project
from apps.properties.models import Property

class ProjectSerializer(serializers.ModelSerializer):
    property_name = serializers.ReadOnlyField(source='property.name')
    property_code = serializers.ReadOnlyField(source='property.code')
    submitted_by_email = serializers.ReadOnlyField(source='submitted_by.email')
    variance_amount = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    variance_percentage = serializers.FloatField(read_only=True)

    class Meta:
        model = Project
        fields = (
            'id', 'org_id', 'property', 'property_name', 'property_code',
            'title', 'category', 'fiscal_period', 'budget_amount', 'actual_cost',
            'status', 'submitted_by', 'submitted_by_email', 'variance_amount',
            'variance_percentage', 'created_at', 'updated_at'
        )
        # `status` only ever changes through ApprovalWorkflowService (locked, audited, broadcast).
        read_only_fields = ('id', 'org_id', 'status', 'submitted_by', 'created_at', 'updated_at')

    def get_fields(self):
        fields = super().get_fields()
        # RLS on the foreign key itself: properties outside the caller's scope are
        # indistinguishable from nonexistent ones ("Invalid pk"), so no existence oracle.
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        fields['property'].queryset = Property.objects.for_user(user) if user else Property.objects.none()
        return fields

    def validate_budget_amount(self, value):
        if value <= Decimal('0.00'):
            raise serializers.ValidationError("Budget amount must be strictly greater than zero.")
        return value

    def validate_actual_cost(self, value):
        if value < Decimal('0.00'):
            raise serializers.ValidationError("Actual cost cannot be negative.")
        return value

    def validate(self, attrs):
        # Reject (rather than silently ignore) attempts to drive the workflow through CRUD.
        if 'status' in getattr(self, 'initial_data', {}):
            current = self.instance.status if self.instance is not None else 'draft'
            if self.initial_data.get('status') != current:
                raise serializers.ValidationError(
                    {'status': ["Status is managed by the approval workflow: use POST /api/v1/projects/{id}/approve/."]}
                )
        instance = self.instance
        if instance is not None and instance.status != 'draft':
            changed = {name for name, value in attrs.items() if getattr(instance, name) != value}
            locked = changed - Project.POST_SUBMISSION_EDITABLE_FIELDS
            if locked:
                raise ConflictException(
                    f"Project is '{instance.status}': {', '.join(sorted(locked))} cannot change after submission "
                    f"(only {', '.join(sorted(Project.POST_SUBMISSION_EDITABLE_FIELDS))} may be updated)."
                )
        return attrs
