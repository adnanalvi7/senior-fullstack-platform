import random
from datetime import datetime, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import connection
from django.contrib.auth.hashers import make_password

from apps.accounts.models import Organization, User, UserPropertyAccess
from apps.properties.models import Property, Budget
from apps.projects.models import Project
from apps.approvals.models import ApprovalEvent
from apps.analytics.models import PendingRollup, PropertyAggregateRollup
from apps.analytics.services import AnalyticsService

from django.utils import timezone

from common.constants import CATEGORIES as _CATEGORIES, FISCAL_PERIODS as _FISCAL_PERIODS

CATEGORIES = list(_CATEGORIES)
STATUSES = ["draft", "submitted", "manager_review", "finance_review", "approved", "rejected"]
APPROVAL_FLOW = ["submitted", "manager_review", "finance_review", "approved"]
FISCAL_PERIODS = list(_FISCAL_PERIODS)
BASE_DATE = timezone.make_aware(datetime(2024, 1, 1))


def org_name(i):
    brands = ["Highview", "Coastline", "Summit", "Harborpoint", "Maple Grove",
              "Sterling", "Brookfield", "Lakeshore", "Granite Bay", "Westwind"]
    return f"{brands[i % len(brands)]} Hospitality Group {i+1}"

class Command(BaseCommand):
    help = "Deterministic multi-tenant database seeder for CapEx platform"

    def add_arguments(self, parser):
        parser.add_argument("--orgs", type=int, default=8, help="Number of organizations (default: 8)")
        parser.add_argument("--projects-per-org", type=int, default=1000, help="Projects per org (default: 1000)")
        parser.add_argument("--scale", choices=["normal", "big"], default="normal", help="'big' expands org 1 to 5x")
        parser.add_argument("--seed", type=int, default=42, help="Deterministic random seed (default: 42)")
        parser.add_argument("--flush-existing", action="store_true", help="Flush existing data before seeding")

    def handle(self, *args, **options):
        seed_val = options["seed"]
        num_orgs = options["orgs"]
        projects_per_org = options["projects_per_org"]
        scale = options["scale"]
        big_org_id = 1 if scale == "big" else None

        rng = random.Random(seed_val)

        self.stdout.write(self.style.WARNING(f"Starting deterministic seed (seed={seed_val}, orgs={num_orgs}, scale={scale})..."))

        if not options["flush_existing"] and Organization.objects.exists():
            # Container restarts must not re-seed (or re-run the rollup bootstrap).
            self.stdout.write(self.style.SUCCESS("Database already seeded; skipping (use --flush-existing to reseed)."))
            return

        if options["flush_existing"]:
            self.stdout.write("Flushing existing data...")
            PendingRollup.objects.all().delete()
            ApprovalEvent.objects.all().delete()
            Project.objects.all().delete()
            PropertyAggregateRollup.objects.all().delete()
            Budget.objects.all().delete()
            UserPropertyAccess.objects.all().delete()
            User.objects.all().delete()
            Property.objects.all().delete()
            Organization.objects.all().delete()

        # 1. Organizations
        org_objs = []
        for i in range(num_orgs):
            org_objs.append(Organization(
                id=i + 1,
                name=org_name(i),
                slug=f"org-{i+1:03d}"
            ))
        Organization.objects.bulk_create(org_objs, ignore_conflicts=True)
        self.stdout.write(f"  [+] Seeded {len(org_objs)} Organizations")

        # 2. Properties
        prop_objs = []
        pid = 1
        for org in org_objs:
            count = rng.randint(4, 12)
            for j in range(count):
                prop_objs.append(Property(
                    id=pid,
                    org_id=org.id,
                    name=f"{org.name.split(' Hospitality')[0]} Property {j+1}",
                    code=f"P{org.id:03d}-{j+1:02d}",
                ))
                pid += 1
        Property.objects.bulk_create(prop_objs, ignore_conflicts=True)
        self.stdout.write(f"  [+] Seeded {len(prop_objs)} Properties")

        # Map properties by org
        props_by_org = {}
        for p in prop_objs:
            props_by_org.setdefault(p.org_id, []).append(p.id)

        # 3. Users
        user_objs = []
        user_prop_accesses = []
        uid = 1
        default_pwd_hash = make_password("Passw0rd!")

        for org in org_objs:
            org_props = props_by_org[org.id]
            # 1 org_admin (whole org)
            admin_user = User(
                id=uid,
                org_id=org.id,
                email=f"admin{uid}@org{org.id}.example.com",
                role="org_admin",
                password=default_pwd_hash,
            )
            user_objs.append(admin_user)
            uid += 1

            # Property managers (each scoped to 1-3 properties)
            for _ in range(max(2, len(org_props) // 3)):
                scope = rng.sample(org_props, k=min(len(org_props), rng.randint(1, 3)))
                pm_user = User(
                    id=uid,
                    org_id=org.id,
                    email=f"pm{uid}@org{org.id}.example.com",
                    role="property_manager",
                    password=default_pwd_hash,
                )
                user_objs.append(pm_user)
                for sp in scope:
                    user_prop_accesses.append(UserPropertyAccess(user_id=uid, property_id=sp))
                uid += 1

            # Approvers (scoped to 2-4 properties)
            for _ in range(2):
                scope = rng.sample(org_props, k=min(len(org_props), rng.randint(2, 4)))
                appr_user = User(
                    id=uid,
                    org_id=org.id,
                    email=f"appr{uid}@org{org.id}.example.com",
                    role="approver",
                    password=default_pwd_hash,
                )
                user_objs.append(appr_user)
                for sp in scope:
                    user_prop_accesses.append(UserPropertyAccess(user_id=uid, property_id=sp))
                uid += 1

            # Viewers (scoped to 1-2 properties)
            for _ in range(2):
                scope = rng.sample(org_props, k=min(len(org_props), rng.randint(1, 2)))
                view_user = User(
                    id=uid,
                    org_id=org.id,
                    email=f"view{uid}@org{org.id}.example.com",
                    role="viewer",
                    password=default_pwd_hash,
                )
                user_objs.append(view_user)
                for sp in scope:
                    user_prop_accesses.append(UserPropertyAccess(user_id=uid, property_id=sp))
                uid += 1

        User.objects.bulk_create(user_objs, ignore_conflicts=True)
        UserPropertyAccess.objects.bulk_create(user_prop_accesses, ignore_conflicts=True)
        self.stdout.write(f"  [+] Seeded {len(user_objs)} Users & Entitlements")

        # 4. Budgets
        budget_objs = []
        bid = 1
        for p in prop_objs:
            for fp in FISCAL_PERIODS:
                budget_objs.append(Budget(
                    id=bid,
                    org_id=p.org_id,
                    property_id=p.id,
                    fiscal_period=fp,
                    allocated_amount=Decimal(str(round(rng.uniform(250_000, 5_000_000), 2))),
                ))
                bid += 1
        Budget.objects.bulk_create(budget_objs, ignore_conflicts=True)
        self.stdout.write(f"  [+] Seeded {len(budget_objs)} Budgets")

        # 5. Projects & Approval Events
        project_objs = []
        approval_event_objs = []
        proj_id = 1
        evt_id = 1

        for org_id, org_pids in props_by_org.items():
            n = projects_per_org * (5 if org_id == big_org_id else 1)
            for _ in range(n):
                chosen_pid = rng.choice(org_pids)
                budget = Decimal(str(round(rng.uniform(5_000, 750_000), 2)))
                cost = Decimal(str(round(float(budget) * rng.uniform(0.3, 1.4), 2)))
                status = rng.choices(
                    STATUSES, weights=[8, 12, 14, 14, 45, 7], k=1
                )[0]
                created = BASE_DATE + timedelta(days=rng.randint(0, 800), minutes=rng.randint(0, 1440))

                project_objs.append(Project(
                    id=proj_id,
                    org_id=org_id,
                    property_id=chosen_pid,
                    title=f"{rng.choice(CATEGORIES)} project #{proj_id}",
                    category=rng.choice(CATEGORIES),
                    fiscal_period=rng.choice(FISCAL_PERIODS),
                    budget_amount=budget,
                    actual_cost=cost,
                    status=status,
                    created_at=created,
                ))

                if status != "draft":
                    t = created
                    reached = APPROVAL_FLOW.index(status) + 1 if status in APPROVAL_FLOW else len(APPROVAL_FLOW)
                    if status == "rejected":
                        reached = rng.randint(1, len(APPROVAL_FLOW) - 1)
                    for level in APPROVAL_FLOW[:reached]:
                        t = t + timedelta(hours=rng.randint(2, 96))
                        target_status = "rejected" if (status == "rejected" and level == APPROVAL_FLOW[reached - 1]) else level
                        approval_event_objs.append(ApprovalEvent(
                            id=evt_id,
                            project_id=proj_id,
                            org_id=org_id,
                            property_id=chosen_pid,
                            from_status="draft" if level == "submitted" else APPROVAL_FLOW[APPROVAL_FLOW.index(level)-1] if level in APPROVAL_FLOW and APPROVAL_FLOW.index(level) > 0 else "submitted",
                            to_status=target_status,
                            created_at=t,
                        ))
                        evt_id += 1
                proj_id += 1

        # Bulk create projects and events in chunks for performance
        BATCH_SIZE = 2000
        for i in range(0, len(project_objs), BATCH_SIZE):
            Project.objects.bulk_create(project_objs[i:i+BATCH_SIZE], ignore_conflicts=True)
        self.stdout.write(f"  [+] Seeded {len(project_objs)} Projects")

        for i in range(0, len(approval_event_objs), BATCH_SIZE):
            ApprovalEvent.objects.bulk_create(approval_event_objs[i:i+BATCH_SIZE], ignore_conflicts=True)
        self.stdout.write(f"  [+] Seeded {len(approval_event_objs)} Approval Events")

        # 6. Precompute Rollup Aggregates
        self.stdout.write("  [*] Precomputing initial aggregate rollups...")
        for prop in prop_objs:
            for fp in FISCAL_PERIODS:
                AnalyticsService.compute_property_rollup(prop.id, fp)

        # 7. Synchronize Database Sequences for PostgreSQL
        if connection.vendor == 'postgresql':
            self.stdout.write("  [*] Synchronizing PostgreSQL primary key sequences...")
            from django.core.management.color import no_style
            from django.apps import apps
            reset_commands = connection.ops.sequence_reset_sql(no_style(), apps.get_models())
            with connection.cursor() as cursor:
                for sql in reset_commands:
                    cursor.execute(sql)

        self.stdout.write(self.style.SUCCESS("Deterministic multi-tenant seeding successfully completed!"))
        self.stdout.write(self.style.SUCCESS("All demo users created with password: 'Passw0rd!'"))
