# Blue Ocean CapEx Platform — Multi-Tenant Budget & Approval Platform

Production-quality Multi-Tenant Capital Expenditure (CapEx) Budget, Workflow Approval, and Scaled Analytics Platform built with **Django REST Framework**, **PostgreSQL**, **Redis**, **Celery**, **Django Channels (WebSockets)**, and **React 18 + TypeScript + Redux Toolkit + MUI**.

---

## Quick Start (Runnable in < 5 Minutes)

### Option 1: Docker Compose (Production Stack)

Prerequisites: Docker & Docker Compose.

```bash
# 1. Start all containerized services (DB, Redis, Backend, Celery worker + beat, Frontend)
docker compose up --build -d

# 2. View logs during automated migration and deterministic database seeding
docker compose logs -f backend
```

Once started:
- **Frontend Dashboard:** [http://localhost:5173](http://localhost:5173)
- **Backend API & Swagger:** [http://localhost:8000/api/v1/](http://localhost:8000/api/v1/)
- **WebSocket Endpoint:** `ws://localhost:8000/ws/approvals/`

---

### Option 2: Local Development Setup (Quick Run)

Prerequisites: Python 3.11+, Node 18+.

#### Backend:
```bash
cd backend
python -m pip install -r requirements.txt
# Without Redis: in-memory cache/channels and eager Celery (explicit opt-in, never a silent fallback).
# With a local Redis, drop USE_REDIS=false and run `celery -A config worker` + `celery -A config beat`.
export DJANGO_DEBUG=True USE_REDIS=false
python manage.py migrate
python manage.py seed_db --orgs 8 --projects-per-org 1000
python manage.py runserver 8000
```

#### Frontend:
```bash
cd frontend
npm install
npm run dev
```

---

## Demo Credentials & Role Personas

All seeded accounts share the password: `Passw0rd!`

| Persona | Role | Scope | Email | Key Capabilities |
| :--- | :--- | :--- | :--- | :--- |
| **Corporate Executive** | `org_admin` | Whole Tenant Org | `admin1@org1.example.com` | Portfolio-wide visibility, all properties, all approvals, trigger rollup |
| **Property Manager** | `property_manager` | Scoped Properties | `pm2@org1.example.com` | Create requests, submit projects, review within assigned properties |
| **Financial Approver** | `approver` | Scoped Properties | `appr4@org1.example.com` | Sign-off on finance review, executive approvals, reject requests |
| **Auditor / Viewer** | `viewer` | Scoped Properties | `view6@org1.example.com` | Read-only analytics and project tracking; cannot mutate or approve |

*Cross-Tenant Validation: Users in Tenant 2 (`admin9@org2.example.com`) can never see Tenant 1 data.*

---

## Automated Test Suite

```bash
cd backend
python manage.py test tests -v 2      # or: pytest tests -v
```
47 tests. On PostgreSQL (the Docker stack) all run; on SQLite the 3 row-lock concurrency tests are skipped.

| File | What it proves |
|---|---|
| `test_authz.py` | Tenant + property scoping on list/detail/analytics; no FK existence oracle; `status`/`org`/`submitted_by` not mass-assignable; closed vocabularies; malformed filters → 400; entitlement revocation applies to existing sessions |
| `test_authz_routes.py` | **Walks every registered object route × HTTP method** and asserts out-of-scope IDs get 404 — a new endpoint that forgets `for_user()` fails CI |
| `test_approvals.py` | Full 4-level lifecycle with distinct actors, skip-level 409, role 403s, segregation of duties, terminal states, frozen scope after submission, draft-only delete with audit retention |
| `test_analytics.py` | Rollups == ground truth across properties and periods (incl. derived `ALL`); cycle time is project-weighted; every write path (create/edit/move/approve/delete) leaves all views fresh; version-key invalidation is tenant-local and never clears the cache; dashboard survives a Redis outage; outbox + sweep recover lost tasks |
| `test_concurrency.py` | Real threads on PostgreSQL: simultaneous approvals → one winner; approve-vs-reject consistency; edits racing approvals never revert status |
| `test_realtime.py` | Through the ASGI app: ticket handshake, tenant/property-scoped delivery across repeated events and rollup jobs, revocation without reconnect, `analytics_update`, heartbeat |

---

## Demo: a full approval chain

Segregation of duties is enforced (the submitter can't sign, and nobody signs two levels), so walk a property-5 project through four people:
`pm2` creates + submits → `pm3` manager sign-off → `appr4` finance → `appr5` final approval (all `@org1.example.com`). `admin1` (org_admin) is the audited break-glass role and may act at any level.

---

## Built vs. Deferred Capabilities

### Implemented in Vertical Slice
- [x] Multi-tenant model: Organization, Property, User, Budget, Project, ApprovalEvent, PropertyAggregateRollup, PendingRollup (outbox).
- [x] Central RLS via `TenantScopedQuerySet.for_user()`, scoped FK querysets, object permission, and a route-walking CI test.
- [x] JWT auth; entitlements read from the DB on every request (claims are informational only).
- [x] Multi-level approval state machine: row lock, state validation after lock, segregation of duties, audit trail protected from deletion.
- [x] Per-(property, fiscal period) additive rollups; `ALL` derived at read time; project-weighted cycle time.
- [x] Refresh on write via a transactional outbox + Celery worker, with a beat sweep bounding staleness (~90 s worst case).
- [x] Version-key cache invalidation (O(1), per tenant); Redis split into broker / cache / channels DBs; circuit breaker for Redis outages.
- [x] Django Channels with short-lived WS tickets, per-event entitlement checks, heartbeat, `analytics_update` events.
- [x] React 18 + TS (strict, no `any`) + RTK + MUI: KPIs, two charts, scoped table, optimistic approval with server reconciliation, role-aware actions mirroring the backend state machine.
- [x] Docker Compose: PostgreSQL, Redis, API, worker, beat, frontend; idempotent seeding.

### Intentionally Deferred (Documented in DESIGN.md)
- Real Azure AD SSO (stubbed with SimpleJWT claims; production SSO architecture documented in `DESIGN.md`).
- Multi-file attachment uploads for CapEx invoices (S3 / Azure Blob Storage integration design documented).
- CSV/Excel asynchronous export engine.

---

## 6-Hour Time Allocation Breakdown

| Phase | Allocation | Focus |
| :--- | :--- | :--- |
| **Phase 1: Architecture & Planning** | 45 min | Domain model design, centralized RLS strategy, `IMPLEMENTATION_PLAN.md` |
| **Phase 2: Backend Models & RLS** | 1 hr 15 min | Models, managers, DRF serializers, viewsets, and seed management command |
| **Phase 3: Approval State Machine** | 45 min | Transactional state machine, `select_for_update()`, audit events |
| **Phase 4: Aggregation & Caching** | 45 min | Rollup schema, Celery worker task, Redis cache keys, invalidation |
| **Phase 5: Real-Time WebSockets** | 30 min | Django Channels ASGI setup, JWT auth middleware, tenant channel groups |
| **Phase 6: React Dashboard** | 1 hr 00 min | Redux Toolkit store, KPI cards, Recharts, optimistic updates, table |
| **Phase 7: Testing & Verification** | 30 min | Automated test suite execution, bug fixes, ground-truth assertion |
| **Phase 8: DESIGN.md & Docs** | 30 min | Comprehensive architectural defense and scalability documentation |
