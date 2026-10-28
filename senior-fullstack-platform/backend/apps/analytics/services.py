import hashlib
import logging
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional

from django.db import transaction
from django.db.models import Count, DurationField, ExpressionWrapper, F, OuterRef, Subquery, Sum
from django.utils import timezone

from common.cache import bump_version, cache_get, cache_set, get_version, redis_circuit_open, trip_redis_circuit
from common.constants import ALL_PERIODS, FISCAL_PERIODS, PENDING_STATUSES, TERMINAL_STATUSES
from apps.projects.models import Project
from apps.properties.models import Property
from apps.approvals.models import ApprovalEvent
from apps.analytics.models import PendingRollup, PropertyAggregateRollup

logger = logging.getLogger(__name__)

CENT = Decimal('0.01')


def _pct(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator <= 0:
        return Decimal('0.00')
    return (numerator / denominator * 100).quantize(CENT)


class AnalyticsService:
    CACHE_TTL_SECONDS = 1800  # upper bound only; entries are orphaned by version bumps on write

    # ------------------------------------------------------------------ write side
    @classmethod
    def compute_property_rollup(cls, property_id: int, fiscal_period: str) -> PropertyAggregateRollup:
        """Full, idempotent recompute of one (property, fiscal_period) bucket."""
        if fiscal_period not in FISCAL_PERIODS:
            raise ValueError(f"Unknown fiscal period {fiscal_period!r}")
        prop = Property.objects.only('id', 'org_id').get(id=property_id)

        qs = Project.objects.filter(property_id=property_id, fiscal_period=fiscal_period)
        agg = qs.aggregate(budget_total=Sum('budget_amount'), actual_cost_total=Sum('actual_cost'), project_count=Count('id'))
        budget_total = agg['budget_total'] or Decimal('0.00')
        actual_cost_total = agg['actual_cost_total'] or Decimal('0.00')
        variance_amount = actual_cost_total - budget_total

        category_spend = {
            row['category']: str(row['spend'] or Decimal('0.00'))
            for row in qs.values('category').annotate(spend=Sum('actual_cost')).order_by('category')
        }
        status_counts = {row['status']: row['cnt'] for row in qs.values('status').annotate(cnt=Count('id')).order_by('status')}
        pending_count = sum(status_counts.get(st, 0) for st in PENDING_STATUSES)

        cycle_sum, cycle_count = cls._cycle_time_components(property_id, fiscal_period)

        rollup, _ = PropertyAggregateRollup.objects.update_or_create(
            property_id=property_id,
            fiscal_period=fiscal_period,
            defaults={
                'org_id': prop.org_id,
                'budget_total': budget_total,
                'actual_cost_total': actual_cost_total,
                'variance_amount': variance_amount,
                'variance_percentage': _pct(variance_amount, budget_total),
                'category_spend': category_spend,
                'status_counts': status_counts,
                'project_count': agg['project_count'] or 0,
                'pending_approval_count': pending_count,
                'cycle_time_hours_sum': cycle_sum,
                'cycle_time_count': cycle_count,
                'avg_cycle_time_hours': (cycle_sum / cycle_count).quantize(CENT) if cycle_count else Decimal('0.00'),
            },
        )
        return rollup

    @classmethod
    def _cycle_time_components(cls, property_id: int, fiscal_period: str):
        """
        (sum of hours, number of projects) from first approval event (submission) to the
        terminal decision, for decided projects in the bucket. One SQL statement: the start
        time is a correlated subquery served by the (project, created_at) index.
        """
        first_event = (
            ApprovalEvent.objects.filter(project_id=OuterRef('project_id'))
            .order_by('created_at', 'id').values('created_at')[:1]
        )
        agg = (
            ApprovalEvent.objects
            .filter(property_id=property_id, project__fiscal_period=fiscal_period, to_status__in=TERMINAL_STATUSES)
            .annotate(started_at=Subquery(first_event))
            .filter(created_at__gt=F('started_at'))
            .annotate(duration=ExpressionWrapper(F('created_at') - F('started_at'), output_field=DurationField()))
            .aggregate(total=Sum('duration'), n=Count('id'))
        )
        total = agg['total']
        if not agg['n'] or total is None:
            return Decimal('0'), 0
        hours = Decimal(total.total_seconds()) / Decimal(3600)
        return hours.quantize(Decimal('0.0001')), agg['n']

    @classmethod
    def mark_buckets_dirty(cls, org_id: int, buckets: Iterable[tuple]):
        """
        Record (property_id, fiscal_period) buckets for recomputation inside the caller's
        transaction (outbox), and enqueue the work once that transaction commits.
        """
        buckets = {(p, fp) for p, fp in buckets if fp in FISCAL_PERIODS}
        if not buckets:
            return
        now = timezone.now()
        PendingRollup.objects.bulk_create(
            [PendingRollup(org_id=org_id, property_id=p, fiscal_period=fp, requested_at=now) for p, fp in buckets],
            update_conflicts=True, unique_fields=['property', 'fiscal_period'], update_fields=['requested_at'],
        )

        def enqueue():
            # Broker trouble must never fail or stall the user's (already committed) write:
            # the outbox row is durable and the periodic sweep picks it up.
            if redis_circuit_open():
                logger.warning("Broker bypassed (circuit open); %d bucket(s) left to the sweep", len(buckets))
                return
            from apps.analytics.tasks import refresh_rollup_bucket
            for p, fp in buckets:
                try:
                    refresh_rollup_bucket.delay(property_id=p, fiscal_period=fp)
                except Exception as exc:
                    trip_redis_circuit("rollup task publish", exc)
                    return

        transaction.on_commit(enqueue)

    @classmethod
    def refresh_bucket(cls, property_id: int, fiscal_period: str) -> Optional[PropertyAggregateRollup]:
        """
        Recompute one bucket, invalidate the org's cached views, then clear its outbox marker
        unless it was re-requested meanwhile. If invalidation fails (Redis down) this raises
        and the marker stays, so the bucket is retried rather than served stale from cache.
        """
        marker = PendingRollup.objects.filter(property_id=property_id, fiscal_period=fiscal_period).first()
        try:
            rollup = cls.compute_property_rollup(property_id, fiscal_period)
        except Property.DoesNotExist:
            PendingRollup.objects.filter(property_id=property_id).delete()
            return None
        cls.invalidate_org_caches(rollup.org_id)
        if marker:
            PendingRollup.objects.filter(pk=marker.pk, requested_at=marker.requested_at).delete()
        return rollup

    @staticmethod
    def _version_key(org_id: int) -> str:
        return f"analytics:org:{org_id}:version"

    @classmethod
    def invalidate_org_caches(cls, org_id: int):
        """O(1), tenant-local invalidation: bump the org's version so old keys are never read."""
        bump_version(cls._version_key(org_id))

    # ------------------------------------------------------------------ read side
    @classmethod
    def get_dashboard_data(cls, user, fiscal_period: str = ALL_PERIODS, selected_property_id: int = None) -> Dict[str, Any]:
        """
        Dashboard KPIs/charts for the caller's entitled properties, merged from precomputed
        per-(property, fiscal_period) rollups. Never scans projects on the request path
        except to bootstrap a bucket that has never been computed (new property).
        """
        entitled_prop_ids = sorted(user.property_ids)
        if selected_property_id is not None:
            if selected_property_id not in entitled_prop_ids:
                return cls._empty_dashboard(fiscal_period)
            active_prop_ids = [selected_property_id]
        else:
            active_prop_ids = entitled_prop_ids
        if not active_prop_ids:
            return cls._empty_dashboard(fiscal_period)

        periods: List[str] = list(FISCAL_PERIODS) if fiscal_period == ALL_PERIODS else [fiscal_period]

        version = get_version(cls._version_key(user.org_id))
        prop_hash = hashlib.sha256(",".join(map(str, active_prop_ids)).encode()).hexdigest()[:16]
        cache_key = f"analytics:org:{user.org_id}:v{version}:props:{prop_hash}:fp:{fiscal_period}"
        if version is not None:
            cached = cache_get(cache_key)
            if cached is not None:
                return cached

        rollups = list(PropertyAggregateRollup.objects.filter(property_id__in=active_prop_ids, fiscal_period__in=periods))
        present = {(r.property_id, r.fiscal_period) for r in rollups}
        for pid in active_prop_ids:
            for fp in periods:
                if (pid, fp) not in present:
                    rollups.append(cls.compute_property_rollup(pid, fp))

        payload = cls._merge(rollups, fiscal_period, len(active_prop_ids))
        if version is not None:
            # Built under `version`; if a write bumped it meanwhile this entry is simply never read.
            cache_set(cache_key, payload, cls.CACHE_TTL_SECONDS)
        return payload

    @classmethod
    def _merge(cls, rollups, fiscal_period: str, property_count: int) -> Dict[str, Any]:
        total_budget = sum((r.budget_total for r in rollups), Decimal('0.00'))
        total_actual = sum((r.actual_cost_total for r in rollups), Decimal('0.00'))
        cycle_sum = sum((r.cycle_time_hours_sum for r in rollups), Decimal('0'))
        cycle_count = sum(r.cycle_time_count for r in rollups)
        categories: Dict[str, Decimal] = {}
        statuses: Dict[str, int] = {}
        for r in rollups:
            for cat, amount in (r.category_spend or {}).items():
                categories[cat] = categories.get(cat, Decimal('0.00')) + Decimal(str(amount))
            for st, cnt in (r.status_counts or {}).items():
                statuses[st] = statuses.get(st, 0) + cnt
        variance = total_actual - total_budget
        as_of = min((r.last_calculated_at for r in rollups), default=None)
        return {
            'fiscal_period': fiscal_period,
            'property_count': property_count,
            'as_of': as_of.isoformat() if as_of else None,
            'kpis': {
                'total_budget': float(total_budget),
                'total_actual': float(total_actual),
                'total_variance': float(variance),
                'variance_percentage': float(_pct(variance, total_budget)),
                'project_count': sum(r.project_count for r in rollups),
                'pending_approval_count': sum(r.pending_approval_count for r in rollups),
                'avg_cycle_time_hours': float((cycle_sum / cycle_count).quantize(CENT)) if cycle_count else 0.0,
            },
            'category_spend': [
                {'category': cat, 'actual_spend': float(amt)}
                for cat, amt in sorted(categories.items(), key=lambda x: x[1], reverse=True)
            ],
            'status_distribution': [{'status': st, 'count': cnt} for st, cnt in sorted(statuses.items())],
        }

    @classmethod
    def _empty_dashboard(cls, fiscal_period: str = ALL_PERIODS):
        return cls._merge([], fiscal_period, 0)
