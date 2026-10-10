from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def get_openai_client():
    """Build the OpenAI client lazily so tests and management commands do not need a key."""
    from openai import OpenAI

    if not settings.OPENAI_API_KEY:
        raise ImproperlyConfigured("OPENAI_API_KEY is not set.")
    return OpenAI(
        api_key=settings.OPENAI_API_KEY,
        max_retries=settings.OPENAI_MAX_RETRIES,
        timeout=30.0,
    )
