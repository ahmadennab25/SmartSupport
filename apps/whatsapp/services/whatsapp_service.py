"""Turns a Twilio WhatsApp webhook payload into an agent reply."""
import logging
from collections.abc import Mapping

from django.conf import settings

from apps.chat.models import ChatMessage
from apps.chat.services.chat_service import EmptyMessage, handle_incoming_message
from apps.customers.services.customer_service import InvalidPhoneNumber

logger = logging.getLogger(__name__)

TEXT_ONLY_REPLY = (
    "عذراً، أستطيع التعامل مع الرسائل النصية فقط حالياً.\n"
    "Sorry, I can only handle text messages for now."
)


def process_incoming(form: Mapping) -> str:
    """Return the text to send back. Raises InvalidPhoneNumber if the sender is malformed."""
    sender = form.get("From", "")
    body = (form.get("Body") or "").strip()
    if not body:
        return TEXT_ONLY_REPLY  # media-only message (image, voice note, ...)
    try:
        outcome = handle_incoming_message(
            phone=sender,
            text=body,
            channel=ChatMessage.Channel.WHATSAPP,
            display_name=form.get("ProfileName", ""),
        )
        return outcome.reply
    except (InvalidPhoneNumber, EmptyMessage):
        raise
    except Exception:
        logger.exception("WhatsApp message processing failed")
        return settings.OPENAI_DEFAULT_ERROR_MESSAGE
