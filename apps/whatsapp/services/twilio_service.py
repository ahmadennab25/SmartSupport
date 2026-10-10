"""Twilio helpers: webhook signature validation and TwiML replies."""
from django.conf import settings
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse

WHATSAPP_MESSAGE_LIMIT = 1500


def get_public_url(request) -> str:
    """The exact URL Twilio called. Behind ngrok the scheme/host come from X-Forwarded-* headers."""
    override = getattr(settings, "TWILIO_WEBHOOK_URL", "")
    if override:
        return override
    scheme = request.headers.get("X-Forwarded-Proto", request.scheme).split(",")[0].strip()
    host = request.headers.get("X-Forwarded-Host", request.get_host()).split(",")[0].strip()
    return f"{scheme}://{host}{request.get_full_path()}"


def is_valid_signature(request) -> bool:
    """Verify X-Twilio-Signature. Disabled when TWILIO_VALIDATE_REQUESTS is False; fails closed
    when validation is on but no auth token is configured."""
    if not getattr(settings, "TWILIO_VALIDATE_REQUESTS", False):
        return True
    token = getattr(settings, "TWILIO_AUTH_TOKEN", "")
    if not token:
        return False
    signature = request.headers.get("X-Twilio-Signature", "")
    return RequestValidator(token).validate(get_public_url(request), request.POST.dict(), signature)


def split_message(text: str, limit: int = WHATSAPP_MESSAGE_LIMIT) -> list[str]:
    """Split a long reply on line boundaries so every part fits the WhatsApp size limit."""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        while len(line) > limit:
            if current:
                chunks.append(current.rstrip())
                current = ""
            chunks.append(line[:limit])
            line = line[limit:]
        if len(current) + len(line) > limit:
            chunks.append(current.rstrip())
            current = ""
        current += line
    if current.strip():
        chunks.append(current.rstrip())
    return chunks


def build_twiml(text: str) -> str:
    response = MessagingResponse()
    for part in split_message(text):
        response.message(part)
    return str(response)
