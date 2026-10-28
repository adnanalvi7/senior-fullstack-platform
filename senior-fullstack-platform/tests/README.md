# Automated Test Suite

The tests live in `backend/tests/` (47 tests):

- `test_authz.py`: tenant and property isolation, mass-assignment protection, no foreign-key existence oracle, input validation, entitlement revocation.
- `test_authz_routes.py`: walks every registered object route and HTTP method and asserts that out-of-scope IDs return 404.
- `test_approvals.py`: state machine, segregation of duties, finalized-state protection, audit retention.
- `test_analytics.py`: rollups match ground truth, freshness after every write path, cycle-time weighting, cache invalidation, Redis-outage tolerance, outbox recovery.
- `test_concurrency.py`: real parallel requests on PostgreSQL (skipped on SQLite).
- `test_realtime.py`: WebSocket authentication, scoped delivery, revocation, analytics events.

## Running tests

From the `backend/` directory:
```bash
python manage.py test tests -v 2
```
or
```bash
pytest tests -v
```

To run against real Redis instead of the in-memory backends, set `TEST_WITH_REDIS=true`.
