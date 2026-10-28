import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from common.constants import FISCAL_PERIODS
from apps.properties.models import Property
from apps.analytics.models import PendingRollup
from apps.analytics.services import AnalyticsService

logger = logging.getLogger(__name__)

# Outbox rows younger than this are assumed to have an in-flight task; the sweep skips them.
SWEEP_GRACE = timedelta(seconds=30)


def _broadcast_analytics_update(org_id: int, property_id: int, fiscal_period: str):
    """Tell connected dashboards that fresh aggregates exist (after the rollup is written)."""
    try:
        from apps.approvals.consumers import broadcast_analytics_update
        broadcast_analytics_update(org_id, property_id, fiscal_period)
    except Exception as exc:
        logger.error("analytics_update broadcast failed for org %s: %s", org_id, exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=5, acks_late=True)
def refresh_rollup_bucket(self, property_id: int, fiscal_period: str):
    """Recompute one (property, fiscal_period) rollup bucket. Idempotent; safe to duplicate."""
    try:
        rollup = AnalyticsService.refresh_bucket(property_id, fiscal_period)
    except Exception as exc:
        logger.exception("Rollup refresh failed for property %s %s", property_id, fiscal_period)
        raise self.retry(exc=exc) from exc
    if rollup is not None:
        _broadcast_analytics_update(rollup.org_id, property_id, fiscal_period)
    return f"refreshed property {property_id} {fiscal_period}"


@shared_task
def sweep_pending_rollups(limit: int = 500):
    """
    Periodic safety net (celery beat): recompute any bucket whose outbox marker is older
    than the grace period — i.e. its task was lost (broker outage, worker crash) or failed.
    """
    cutoff = timezone.now() - SWEEP_GRACE
    stale = list(PendingRollup.objects.filter(requested_at__lt=cutoff).order_by('requested_at')[:limit])
    recovered = 0
    for marker in stale:
        try:
            rollup = AnalyticsService.refresh_bucket(marker.property_id, marker.fiscal_period)
        except Exception:
            logger.exception("Sweep could not refresh property %s %s; will retry next run", marker.property_id, marker.fiscal_period)
            continue
        recovered += 1
        if rollup is not None:
            _broadcast_analytics_update(rollup.org_id, marker.property_id, marker.fiscal_period)
    if recovered:
        logger.warning("Rollup sweep recovered %d stale bucket(s)", recovered)
    return recovered


@shared_task
def recalculate_all_aggregates(org_id: int = None):
    """Full rebuild for an org (or everything): marks every bucket dirty and fans out one task each."""
    qs = Property.objects.all()
    if org_id:
        qs = qs.filter(org_id=org_id)
    count = 0
    for prop in qs.only('id', 'org_id').iterator():
        AnalyticsService.mark_buckets_dirty(prop.org_id, [(prop.id, fp) for fp in FISCAL_PERIODS])
        count += 1
    return f"Queued rollup rebuild for {count} properties."
