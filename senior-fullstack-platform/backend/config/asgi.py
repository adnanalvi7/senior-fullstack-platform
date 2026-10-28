import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from django.urls import path
from common.ws_auth import TicketAuthMiddlewareStack
from apps.approvals.consumers import ApprovalConsumer

websocket_urlpatterns = [
    path('ws/approvals/', ApprovalConsumer.as_asgi()),
]

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': TicketAuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
