from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chat.models import ChatMessage
from apps.chat.permissions import HasChatApiKey
from apps.chat.serializers import ChatRequestSerializer
from apps.chat.services.chat_service import EmptyMessage, handle_incoming_message
from apps.customers.services.customer_service import InvalidPhoneNumber


class ChatView(APIView):
    """POST /api/chat/ - send a customer message to the agent without WhatsApp (testing, demos, evaluation)."""

    authentication_classes: list = []
    permission_classes = [HasChatApiKey]

    def post(self, request):
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            outcome = handle_incoming_message(
                phone=data["phone"],
                text=data["message"],
                channel=ChatMessage.Channel.API,
                display_name=data.get("display_name", ""),
            )
        except InvalidPhoneNumber as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except EmptyMessage as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "reply": outcome.reply,
                "customer": {"id": outcome.customer.pk, "name": outcome.customer.full_name},
                "tool_calls": outcome.result.tool_calls,
                "latency_ms": outcome.result.latency_ms,
                "failed": outcome.result.failed,
            }
        )
