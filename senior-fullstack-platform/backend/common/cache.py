"""
Failure-tolerant cache helpers.

Redis is an accelerator, not a source of truth: every helper degrades to "cache miss" /
"no-op" when Redis is unavailable so requests fall through to the database instead of
failing. Errors are logged, never swallowed silently.
"""
import logging
import time
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Circuit breaker: after a Redis failure, skip Redis for a few seconds instead of paying the
# connect timeout on every call. Shared by cache helpers, Celery publishing and broadcasts.
CIRCUIT_OPEN_SECONDS = 15.0
_down_until = 0.0


def redis_circuit_open() -> bool:
    return time.monotonic() < _down_until


def reset_redis_circuit():
    """Close the breaker (tests, or after an operator confirms Redis is healthy)."""
    global _down_until
    _down_until = 0.0


def trip_redis_circuit(what: str, exc: Exception):
    global _down_until
    _down_until = time.monotonic() + CIRCUIT_OPEN_SECONDS
    logger.warning("Redis unavailable during %s (%s); bypassing Redis for %.0fs", what, exc, CIRCUIT_OPEN_SECONDS)


def cache_get(key, default=None):
    if redis_circuit_open():
        return default
    try:
        return cache.get(key, default)
    except Exception as exc:
        trip_redis_circuit(f"cache get {key}", exc)
        return default


def cache_set(key, value, timeout):
    if redis_circuit_open():
        return
    try:
        cache.set(key, value, timeout)
    except Exception as exc:
        trip_redis_circuit(f"cache set {key}", exc)


def get_version(key):
    """Current integer version stored at `key` (created as 1). Returns None if Redis is down."""
    if redis_circuit_open():
        return None
    try:
        return cache.get_or_set(key, 1, timeout=None)
    except Exception as exc:
        trip_redis_circuit(f"cache version read {key}", exc)
        return None


def bump_version(key):
    """
    Atomically increment a version key, orphaning every cache entry built on the old one.
    If Redis is down the bump is skipped; the bucket's outbox marker survives and the sweep
    that runs once Redis is back recomputes the bucket and bumps the version then.
    """
    if redis_circuit_open():
        raise ConnectionError("Redis circuit open; version bump deferred")
    try:
        try:
            cache.incr(key)
        except ValueError:  # key missing (evicted / never read): any fresh value invalidates
            cache.add(key, 1, timeout=None)
            cache.incr(key)
    except Exception as exc:
        trip_redis_circuit(f"cache version bump {key}", exc)
        raise
