from django.db import models
from common.constants import FISCAL_PERIOD_CHOICES
from common.managers import TenantScopedManager

class PropertyAggregateRollup(models.Model):
    """
    Precomputed aggregates for exactly one (property, fiscal_period) bucket.

    Every stored field is additive across buckets (sums and counts), so any wider view —
    several properties, or 'ALL' fiscal periods — is an exact sum of rows computed at read
    time. Ratios (variance %, average cycle time) are derived from the summed components,
    never averaged.
    """
    org = models.ForeignKey('accounts.Organization', on_delete=models.CASCADE, related_name='aggregate_rollups', db_index=True)
    property = models.ForeignKey('properties.Property', on_delete=models.CASCADE, related_name='aggregate_rollups', db_index=True)
    fiscal_period = models.CharField(max_length=16, choices=FISCAL_PERIOD_CHOICES, db_index=True)

    budget_total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    actual_cost_total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    variance_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    variance_percentage = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    # {category: "decimal string"} — strings keep cent precision through JSON.
    category_spend = models.JSONField(default=dict)
    status_counts = models.JSONField(default=dict)
    project_count = models.IntegerField(default=0)
    pending_approval_count = models.IntegerField(default=0)

    # Cycle time components (submission -> terminal decision) for decided projects.
    cycle_time_hours_sum = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    cycle_time_count = models.IntegerField(default=0)
    avg_cycle_time_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    last_calculated_at = models.DateTimeField(auto_now=True)

    objects = TenantScopedManager()

    class Meta:
        ordering = ['org', 'property', 'fiscal_period']
        unique_together = ('property', 'fiscal_period')
        indexes = [
            models.Index(fields=['org', 'fiscal_period']),
            models.Index(fields=['property', 'fiscal_period']),
            models.Index(fields=['org', 'property']),
        ]

    def __str__(self):
        return f"Rollup: Prop {self.property_id} ({self.fiscal_period}) - Budget: ${self.budget_total}"


class PendingRollup(models.Model):
    """
    Transactional outbox of rollup buckets that need recomputation.

    Written in the same DB transaction as the project/approval change, so a refresh request
    can never be lost to a broker outage, a worker crash or a Redis flush. Workers delete a
    marker only if it was not re-requested while they were computing (requested_at check),
    which also makes out-of-order job completion harmless. A periodic sweep drains leftovers.
    """
    org = models.ForeignKey('accounts.Organization', on_delete=models.CASCADE, related_name='+')
    property = models.ForeignKey('properties.Property', on_delete=models.CASCADE, related_name='+')
    fiscal_period = models.CharField(max_length=16, choices=FISCAL_PERIOD_CHOICES)
    requested_at = models.DateTimeField()

    class Meta:
        unique_together = ('property', 'fiscal_period')
        indexes = [models.Index(fields=['requested_at'])]

    def __str__(self):
        return f"PendingRollup(prop={self.property_id}, fp={self.fiscal_period})"
