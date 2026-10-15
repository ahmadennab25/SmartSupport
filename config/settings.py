"""Django settings for SmartSupport AI. All secrets come from the .env file."""
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


# --- Core ---------------------------------------------------------------
DEBUG = env_bool("DEBUG", False)
SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "insecure-dev-key-change-me"
    else:
        raise ImproperlyConfigured("SECRET_KEY is required when DEBUG is False.")

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list(
    "CSRF_TRUSTED_ORIGINS", "https://*.ngrok-free.app,https://*.ngrok.app,https://*.ngrok-free.dev"
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    # Project apps
    "apps.core",
    "apps.customers",
    "apps.orders",
    "apps.tickets",
    "apps.chat",
    "apps.agent",
    "apps.whatsapp",
    "apps.knowledge",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --- Database (PostgreSQL) ------------------------------------------------
# The schema is put first in the search_path; "public" stays second as a fallback.
DATABASE_SCHEMA = os.getenv("DATABASE_SCHEMA", "public")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DATABASE_NAME", "SmartSupport"),
        "USER": os.getenv("DATABASE_USER", "postgres"),
        "PASSWORD": os.getenv("DATABASE_PASSWORD", ""),
        "HOST": os.getenv("DATABASE_HOST", "localhost"),
        "PORT": os.getenv("DATABASE_PORT", "5432"),
        "OPTIONS": {"options": f'-c search_path="{DATABASE_SCHEMA}",public'},
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- i18n ------------------------------------------------------------------
LANGUAGE_CODE = "en"
TIME_ZONE = "Asia/Amman"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
}

# --- OpenAI ----------------------------------------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
OPENAI_MAX_RETRIES = int(os.getenv("OPENAI_MAX_RETRIES", "3"))
OPENAI_DEFAULT_TEMPERATURE = float(os.getenv("OPENAI_DEFAULT_TEMPERATURE", "0.3"))
OPENAI_DEFAULT_ERROR_MESSAGE = os.getenv(
    "OPENAI_DEFAULT_ERROR_MESSAGE",
    "I'm sorry, I'm having trouble connecting right now. Please try again in a moment.",
)

# --- Twilio / WhatsApp -------------------------------------------------------
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "")
def twilio_validation_enabled(debug: bool, raw: str | None) -> bool:
    """Webhook signatures are always checked when DEBUG is off. In development they are checked unless the
    developer explicitly sets TWILIO_VALIDATE_REQUESTS=False."""
    if not debug:
        return True
    return True if raw is None else raw.strip().lower() in {"1", "true", "yes", "on"}


TWILIO_VALIDATE_REQUESTS = twilio_validation_enabled(DEBUG, os.getenv("TWILIO_VALIDATE_REQUESTS"))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "[{levelname}] {name}: {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}

# --- Chat API / agent / WhatsApp (phases 3-4) -------------------------------
CHAT_API_KEY = os.getenv("CHAT_API_KEY", "")  # required header X-API-Key for POST /api/chat/
CHAT_MAX_MESSAGE_CHARS = int(os.getenv("CHAT_MAX_MESSAGE_CHARS", "1500"))
AGENT_HISTORY_LIMIT = int(os.getenv("AGENT_HISTORY_LIMIT", "10"))
AGENT_MAX_TOOL_ROUNDS = int(os.getenv("AGENT_MAX_TOOL_ROUNDS", "5"))
STORE_NAME = os.getenv("STORE_NAME", "SmartSupport Store")
# Exact public webhook URL (e.g. your ngrok URL) used for Twilio signature validation. Optional.
TWILIO_WEBHOOK_URL = os.getenv("TWILIO_WEBHOOK_URL", "")

# --- RAG / knowledge base (phase 5) ------------------------------------------
KNOWLEDGE_BASE_DIR = BASE_DIR / "knowledge_base"
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "4"))  # passages returned to the agent
RAG_MIN_SCORE = float(os.getenv("RAG_MIN_SCORE", "0.2"))  # minimum cosine similarity (0-1)
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "64"))

# --- Agent prompt (phase 8) ----------------------------------------------------
AGENT_PROMPT_VERSION = os.getenv("AGENT_PROMPT_VERSION", "v3")  # v1, v2 or v3 (see apps/agent/prompts.py)
