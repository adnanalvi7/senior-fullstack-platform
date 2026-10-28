from django.db import models
from common.constants import FISCAL_PERIOD_CHOICES
from common.managers import TenantScopedManager

class Property(models.Model):
    org = models.ForeignKey('accounts.Organization', on_delete=models.CASCADE, related_name='properties', db_index=True)
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TenantScopedManager()

    class Meta:
        ordering = ['id']
        indexes = [
            models.Index(fields=['org', 'id']),
            models.Index(fields=['org', 'code']),
        ]
        unique_together = ('org', 'code')

    def __str__(self):
        return f"{self.name} ({self.code})"


class Budget(models.Model):
    org = models.ForeignKey('accounts.Organization', on_delete=models.CASCADE, related_name='budgets', db_index=True)
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='budgets', db_index=True)
    fiscal_period = models.CharField(max_length=16, choices=FISCAL_PERIOD_CHOICES, db_index=True)
    allocated_amount = models.DecimalField(max_digits=15, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantScopedManager()

    class Meta:
        ordering = ['-fiscal_period', 'property']
        indexes = [
            models.Index(fields=['org', 'fiscal_period']),
            models.Index(fields=['property', 'fiscal_period']),
        ]
        unique_together = ('property', 'fiscal_period')

    def __str__(self):
        return f"Budget {self.property.code} - {self.fiscal_period}: ${self.allocated_amount}"
