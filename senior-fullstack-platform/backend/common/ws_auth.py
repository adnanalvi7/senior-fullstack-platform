"""
WebSocket handshake authentication.

Browsers cannot set an Authorization header on a WebSocket, and putting the long-lived JWT
in the URL leaks it into proxy/access logs. Instead the client exchanges its JWT for a
short-lived, single-purpose signed ticket (POST /api/v1/auth/ws-ticket/) and connects with
ws://host/ws/approvals/?ticket=<ticket>. The ticket only authorises the handshake.
"""
import urllib.parse
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.core import signing

WS_TICKET_SALT = 'ws-ticket'
WS_TICKET_MAX_AGE_SECONDS = 60


def issue_ws_ticket(user) -> str:
    return signing.dumps({'uid': user.id}, salt=WS_TICKET_SALT)


@database_sync_to_async
def get_user_from_ticket(ticket: str):
    from apps.accounts.models import User
    try:
        payload = signing.loads(ticket, salt=WS_TICKET_SALT, max_age=WS_TICKET_MAX_AGE_SECONDS)
        return User.objects.select_related('org').get(id=payload['uid'], is_active=True)
    except (signing.BadSignature, KeyError, User.DoesNotExist):
        return AnonymousUser()


class TicketAuthMiddleware:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        params = urllib.parse.parse_qs(scope.get('query_string', b'').decode('utf-8'))
        ticket = (params.get('ticket') or [None])[0]
        scope['user'] = await get_user_from_ticket(ticket) if ticket else AnonymousUser()
        return await self.inner(scope, receive, send)


def TicketAuthMiddlewareStack(inner):
    return TicketAuthMiddleware(inner)
