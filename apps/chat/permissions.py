import hmac

from django.conf import settings
from rest_framework.permissions import BasePermission


class HasChatApiKey(BasePermission):
    """Requires the X-API-Key header to match CHAT_API_KEY. Fails closed if no key is configured."""

    message = "Missing or invalid API key."

    def has_permission(self, request, view) -> bool:
        expected = getattr(settings, "CHAT_API_KEY", "")
        if not expected:
            self.message = "CHAT_API_KEY is not configured on the server."
            return False
        provided = request.headers.get("X-API-Key", "")
        return hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))
