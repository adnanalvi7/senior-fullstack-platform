from datetime import datetime, timezone

from django.db import migrations

FISCAL_PERIODS = ('FY2024', 'FY2025', 'FY2026')


def forwards(apps, schema_editor):
    """
    'ALL' is now derived at read time from per-period rows, and cycle time is stored as
    sum/count. Drop stored 'ALL' (and any junk-period) rows and queue every remaining bucket
    in the outbox; the worker / beat sweep rebuilds them with the new columns populated.
    """
    Rollup = apps.get_model('analytics', 'PropertyAggregateRollup')
    Pending = apps.get_model('analytics', 'PendingRollup')
    Rollup.objects.exclude(fiscal_period__in=FISCAL_PERIODS).delete()
    epoch = datetime(2000, 1, 1, tzinfo=timezone.utc)  # older than the sweep grace period
    Pending.objects.bulk_create(
        [Pending(org_id=r.org_id, property_id=r.property_id, fiscal_period=r.fiscal_period, requested_at=epoch)
         for r in Rollup.objects.only('org_id', 'property_id', 'fiscal_period').iterator()],
        ignore_conflicts=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('analytics', '0002_propertyaggregaterollup_cycle_time_count_and_more'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
