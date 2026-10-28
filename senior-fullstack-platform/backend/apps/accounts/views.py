from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from common.ws_auth import WS_TICKET_MAX_AGE_SECONDS, issue_ws_ticket
from rest_framework_simplejwt.views import TokenObtainPairView
from apps.accounts.serializers import CustomTokenObtainPairSerializer, UserSerializer

class CustomLoginView(TokenObtainPairView):
    permission_classes = (AllowAny,)
    serializer_class = CustomTokenObtainPairSerializer


class CurrentUserView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class WebSocketTicketView(APIView):
    """Exchange a valid JWT for a short-lived WebSocket handshake ticket (keeps JWTs out of URLs)."""
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        return Response({'ticket': issue_ws_ticket(request.user), 'expires_in': WS_TICKET_MAX_AGE_SECONDS})
