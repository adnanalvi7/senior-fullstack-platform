from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from apps.accounts.views import CustomLoginView, CurrentUserView, WebSocketTicketView

urlpatterns = [
    path('login/', CustomLoginView.as_view(), name='auth_login'),
    path('refresh/', TokenRefreshView.as_view(), name='auth_refresh'),
    path('me/', CurrentUserView.as_view(), name='auth_me'),
    path('ws-ticket/', WebSocketTicketView.as_view(), name='auth_ws_ticket'),
]
