"""Business logic of a chat turn, shared by the REST API and the WhatsApp webhook."""
import logging
from dataclasses import dataclass

from django.conf import settings

from apps.agent.agent import AgentResult, SupportAgent
from apps.chat.models import ChatMessage
from apps.customers.models import Customer
from apps.customers.services.customer_service import get_or_create_customer

logger = logging.getLogger(__name__)

INACTIVE_CUSTOMER_REPLY = (
    "عذراً، لا يمكننا معالجة طلبك حالياً. يرجى التواصل مع خدمة العملاء مباشرة.\n"
    "Sorry, we cannot process your request right now. Please contact customer service directly."
)


class EmptyMessage(ValueError):
    """Raised when the incoming message has no text."""


@dataclass
class ChatReply:
    customer: Customer
    reply: str
    result: AgentResult
    message: ChatMessage


def load_history(customer: Customer, limit: int | None = None) -> list[dict]:
    limit = limit or getattr(settings, "AGENT_HISTORY_LIMIT", 10)
    recent = list(ChatMessage.objects.filter(customer=customer).order_by("-created_at", "-id")[:limit])
    recent.reverse()
    return [{"role": m.role, "content": m.content} for m in recent]


def handle_incoming_message(
    phone: str,
    text: str,
    channel: str = ChatMessage.Channel.API,
    display_name: str = "",
    agent: SupportAgent | None = None,
) -> ChatReply:
    """Identify the customer by phone, run the agent and log both sides of the exchange.

    Raises InvalidPhoneNumber or EmptyMessage for bad input.
    """
    text = (text or "").strip()
    if not text:
        raise EmptyMessage("The message is empty.")
    text = text[: getattr(settings, "CHAT_MAX_MESSAGE_CHARS", 1500)]

    customer, _ = get_or_create_customer(phone, display_name)
    history = load_history(customer)  # loaded before saving, so the new message is not duplicated
    ChatMessage.objects.create(
        customer=customer, channel=channel, role=ChatMessage.Role.USER, content=text
    )

    if customer.is_active:
        result = (agent or SupportAgent()).run(customer, text, history)
    else:
        result = AgentResult(reply=INACTIVE_CUSTOMER_REPLY)

    message = ChatMessage.objects.create(
        customer=customer,
        channel=channel,
        role=ChatMessage.Role.ASSISTANT,
        content=result.reply,
        tool_calls=result.tool_calls,
        latency_ms=result.latency_ms,
        model_name=result.model,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
    )
    return ChatReply(customer=customer, reply=result.reply, result=result, message=message)
