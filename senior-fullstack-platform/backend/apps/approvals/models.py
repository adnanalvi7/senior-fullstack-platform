from django.db import models
from django.utils import timezone
from common.managers import TenantScopedManager

class ApprovalEvent(models.Model):
    # PROTECT: the approval audit trail must outlive accidental project deletion.
    project = models.ForeignKey('projects.Project', on_delete=models.PROTECT, related_name='approval_events', db_index=True)
    org = models.ForeignKey('accounts.Organization', on_delete=models.CASCADE, related_name='approval_events', db_index=True)
    property = models.ForeignKey('properties.Property', on_delete=models.CASCADE, related_name='approval_events', db_index=True)
    from_status = models.CharField(max_length=32)
    to_status = models.CharField(max_length=32)
    actor = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='approval_actions')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    objects = TenantScopedManager()

    class Meta:
        ordering = ['created_at', 'id']
        indexes = [
            models.Index(fields=['project', 'created_at']),
            models.Index(fields=['org', 'to_status']),
            models.Index(fields=['property', 'created_at']),
        ]

    def __str__(self):
        return f"Project #{self.project_id}: {self.from_status} -> {self.to_status} by User {self.actor_id}"
