import builtins
from decimal import Decimal
from django.db import models
from django.utils import timezone
from common.constants import CATEGORY_CHOICES, FISCAL_PERIOD_CHOICES
from common.managers import TenantScopedManager

class Project(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('manager_review', 'Manager Review'),
        ('finance_review', 'Finance Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    CATEGORY_CHOICES = CATEGORY_CHOICES

    # Fields that may still change once a project has left 'draft'. Actuals keep accruing
    # after approval (that is what budget-vs-actuals measures); everything that was
    # approved (scope, amount, property, period) is frozen.
    POST_SUBMISSION_EDITABLE_FIELDS = frozenset({'actual_cost'})

    org = models.ForeignKey('accounts.Organization', on_delete=models.CASCADE, related_name='projects', db_index=True)
    property = models.ForeignKey('properties.Property', on_delete=models.CASCADE, related_name='projects', db_index=True)
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=64, choices=CATEGORY_CHOICES, db_index=True)
    fiscal_period = models.CharField(max_length=16, choices=FISCAL_PERIOD_CHOICES, db_index=True)
    budget_amount = models.DecimalField(max_digits=15, decimal_places=2)
    actual_cost = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default='draft', db_index=True)
    submitted_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='submitted_projects')
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantScopedManager()

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['org', 'property', 'status']),
            models.Index(fields=['org', 'fiscal_period']),
            models.Index(fields=['property', 'status']),
            models.Index(fields=['org', 'status']),
            # Default list ordering, scoped per tenant / per property (avoids walking the
            # global created_at index and filtering out other tenants' rows).
            models.Index(fields=['org', '-created_at', '-id'], name='proj_org_created_idx'),
            models.Index(fields=['property', '-created_at', '-id'], name='proj_prop_created_idx'),
            # Rollup recomputation reads exactly one (property, fiscal_period) bucket.
            models.Index(fields=['property', 'fiscal_period'], name='proj_prop_fp_idx'),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(budget_amount__gt=0), name='project_budget_positive'),
            models.CheckConstraint(condition=models.Q(actual_cost__gte=0), name='project_actual_non_negative'),
        ]

    def __str__(self):
        return f"[{self.status}] {self.title} (${self.budget_amount})"

    @builtins.property
    def variance_amount(self):
        return Decimal(self.actual_cost) - Decimal(self.budget_amount)

    @builtins.property
    def variance_percentage(self):
        if self.budget_amount == 0:
            return 0.0
        return round(float(self.variance_amount / Decimal(self.budget_amount)) * 100, 2)
