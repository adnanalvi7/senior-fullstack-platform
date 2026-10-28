import logging
import time
from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.layers import get_channel_layer
from django.conf import settings
from common.cache import redis_circuit_open, trip_redis_circuit

logger = logging.getLogger(__name__)

# How long a socket trusts its cached entitlements before re-reading them from the DB.
ENTITLEMENT_TTL_SECONDS = 30


def org_group(org_id: int) -> str:
    return f"org_{org_id}"


@database_sync_to_async
def _load_access(user_id: int):
    from apps.accounts.models import User
    user = User.objects.filter(id=user_id, is_active=True).only('id', 'role', 'org_id').first()
    if user is None:
        return None
    return {'org_id': user.org_id, 'role': user.role, 'property_ids': set(user.property_ids)}


class ApprovalConsumer(AsyncJsonWebsocketConsumer):
    """
    Tenant-isolated real-time stream.
    1. The handshake must carry a valid ws ticket (see common/ws_auth.py).
    2. The socket joins only its own tenant group org_{org_id}; clients cannot choose groups.
    3. Every event is filtered against the user's *current* property entitlements (re-read
       every ENTITLEMENT_TTL_SECONDS), so revocations take effect without a reconnect.
    4. Sockets are closed when the session lifetime (access-token lifetime) elapses.
    """

    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_authenticated or not getattr(user, 'org_id', None):
            logger.warning("WS connect rejected (unauthenticated)")
            await self.close(code=4001)
            return

        self.user_id = user.id
        self.email = user.email
        self.org_id = user.org_id
        self.group_name = org_group(self.org_id)
        self.expires_at = time.monotonic() + settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds()
        self.access = None
        self.access_loaded_at = 0.0

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.info(f"WS connected: user={self.email} org={self.org_id}")
        await self.send_json({'type': 'connected', 'org_id': self.org_id, 'message': 'Connected to tenant approval stream'})

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        # Heartbeat: lets the client detect a dead stream, and re-asserts group membership
        # (channel-layer groups expire; long-lived sockets must refresh them).
        if content.get('type') == 'ping':
            if not await self._session_valid():
                return
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.send_json({'type': 'pong', 'ts': content.get('ts')})

    async def _session_valid(self) -> bool:
        if time.monotonic() > self.expires_at:
            await self.close(code=4401)
            return False
        return True

    async def _entitled_to(self, property_id) -> bool:
        if not await self._session_valid():
            return False
        now = time.monotonic()
        if self.access is None or now - self.access_loaded_at > ENTITLEMENT_TTL_SECONDS:
            self.access = await _load_access(self.user_id)
            self.access_loaded_at = now
        if self.access is None or self.access['org_id'] != self.org_id:
            await self.close(code=4403)  # deactivated or moved tenant
            return False
        return self.access['role'] == 'org_admin' or property_id in self.access['property_ids']

    async def approval_update(self, event):
        if not await self._entitled_to(event.get('property_id')):
            return
        await self.send_json({'type': 'approval_update', 'data': {k: v for k, v in event.items() if k != 'type'}})

    async def analytics_update(self, event):
        if not await self._entitled_to(event.get('property_id')):
            return
        await self.send_json({'type': 'analytics_update', 'data': {k: v for k, v in event.items() if k != 'type'}})


def _group_send(org_id: int, payload: dict):
    if redis_circuit_open():
        logger.warning("Real-time broadcast skipped (Redis circuit open); clients reconcile on reconnect")
        return
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    try:
        async_to_sync(channel_layer.group_send)(org_group(org_id), payload)
    except Exception as exc:
        trip_redis_circuit("real-time broadcast", exc)


def broadcast_approval_event(project, event, actor):
    """Called from transaction.on_commit() — only committed transitions are published."""
    _group_send(project.org_id, {
        'type': 'approval.update',
        'event_id': event.id,
        'project_id': project.id,
        'property_id': project.property_id,
        'title': project.title,
        'category': project.category,
        'fiscal_period': project.fiscal_period,
        'old_status': event.from_status,
        'new_status': event.to_status,
        'actor_id': actor.id if actor else None,
        'actor_email': actor.email if actor else 'System',
        'notes': event.notes,
        'timestamp': event.created_at.isoformat(),
    })


def broadcast_analytics_update(org_id: int, property_id: int, fiscal_period: str):
    """Called by the worker after a rollup bucket is rewritten: dashboards may refetch now."""
    _group_send(org_id, {'type': 'analytics.update', 'property_id': property_id, 'fiscal_period': fiscal_period})
