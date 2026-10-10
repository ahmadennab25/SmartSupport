"""One-time, NON-destructive patch that wires phases 3-4 into an existing SmartSupport project.

It only ADDS things (new INSTALLED_APPS entries, new settings, new URL routes, new env variables,
a README section). It never deletes or rewrites your existing lines and is safe to run twice.

Usage (from the project root):  python scripts/apply_phase3_4.py
"""
import secrets
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
REPORT: list[str] = []

SETTINGS_BLOCK = '''# --- Chat API / agent / WhatsApp (phases 3-4) -------------------------------
CHAT_API_KEY = os.getenv("CHAT_API_KEY", "")  # required header X-API-Key for POST /api/chat/
CHAT_MAX_MESSAGE_CHARS = int(os.getenv("CHAT_MAX_MESSAGE_CHARS", "1500"))
AGENT_HISTORY_LIMIT = int(os.getenv("AGENT_HISTORY_LIMIT", "10"))
AGENT_MAX_TOOL_ROUNDS = int(os.getenv("AGENT_MAX_TOOL_ROUNDS", "5"))
STORE_NAME = os.getenv("STORE_NAME", "SmartSupport Store")
# Exact public webhook URL (e.g. your ngrok URL) used for Twilio signature validation. Optional.
TWILIO_WEBHOOK_URL = os.getenv("TWILIO_WEBHOOK_URL", "")
'''

ENV_EXAMPLE_BLOCK = """
# Chat API (POST /api/chat/ requires this value in the X-API-Key header)
CHAT_API_KEY='your-chat-api-key'
# Optional: exact public webhook URL for Twilio signature validation (e.g. your ngrok URL)
TWILIO_WEBHOOK_URL=''
"""

README_MARKER = "## Chat API and WhatsApp (phases 3-4)"
README_BLOCK = '''
## Chat API and WhatsApp (phases 3-4)

**Flow:** WhatsApp / REST client -> view -> `chat_service` -> `SupportAgent` (OpenAI function calling)
-> tools -> services -> PostgreSQL. Views never touch the database; tools never receive a customer id
from the model (the customer is identified from the phone number), so an agent can only read and
change the data of the person it is talking to.

**Agent tools** (`apps/agent/tools.py`): `lookup_order`, `list_my_orders`, `create_support_ticket`,
`get_ticket_status`, `add_ticket_update`, `escalate_to_human`. The agent cannot cancel orders or
refund money; those cases become tickets for staff. The RAG tool `search_policies` is added in phase 5.

### Setup after pulling these phases
```bash
python manage.py makemigrations chat
python manage.py migrate
python manage.py test tests
```
Add `CHAT_API_KEY` to `.env` (any long random string).

### Test the agent without WhatsApp: `POST /api/chat/`
Header `X-API-Key: <CHAT_API_KEY>`, JSON body `{"phone": "+962...", "message": "...", "display_name": "optional"}`.
Response: `reply`, `customer`, `tool_calls`, `latency_ms`, `failed`.

PowerShell:
```powershell
$headers = @{ "X-API-Key" = "YOUR_CHAT_API_KEY" }
$body = '{"phone": "+962XXXXXXXXX", "message": "Where is my order 1025?"}'
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/chat/ -Method Post -Headers $headers `
  -ContentType "application/json; charset=utf-8" -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
```
Use the phone number you passed to `seed_demo_data --phone`: it owns orders 1025 (shipped) and 1028 (delivered 10 days ago).

### Connect Twilio WhatsApp
1. `python manage.py runserver`, then in another terminal `ngrok http 8000`.
2. Twilio Console -> Messaging -> Try it out -> Send a WhatsApp message -> Sandbox settings:
   *When a message comes in* = `https://<your-ngrok-domain>/api/whatsapp/webhook/`, method `POST`.
3. Join the sandbox from your phone (the `join ...` message), then chat with the sandbox number.
4. Start with `TWILIO_VALIDATE_REQUESTS=False`. Once it works, set it to `True` and fill
   `TWILIO_AUTH_TOKEN`; if the signature check fails behind ngrok, set `TWILIO_WEBHOOK_URL` to the exact URL from step 2.

Known limits: no rate limiting and no de-duplication of Twilio retries yet; text messages only.
'''


def log(message: str) -> None:
    REPORT.append(message)
    print(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def patch_settings() -> None:
    path = BASE / "config" / "settings.py"
    text = read(path)
    changed = False
    if '"apps.chat"' not in text:
        anchor = '    "apps.tickets",\n'
        if anchor in text:
            text = text.replace(anchor, anchor + '    "apps.chat",\n    "apps.agent",\n    "apps.whatsapp",\n', 1)
            changed = True
        else:
            log('! settings.py: add "apps.chat", "apps.agent", "apps.whatsapp" to INSTALLED_APPS manually.')
    if "CHAT_API_KEY" not in text:
        text = text.rstrip("\n") + "\n\n" + SETTINGS_BLOCK
        changed = True
    if changed:
        write(path, text)
        log("+ config/settings.py: apps registered and new settings added")
    else:
        log("= config/settings.py: already patched")


def patch_urls() -> None:
    path = BASE / "config" / "urls.py"
    text = read(path)
    if "apps.chat.urls" in text:
        log("= config/urls.py: already patched")
        return
    if "from django.urls import path\n" in text:
        text = text.replace("from django.urls import path\n", "from django.urls import include, path\n", 1)
    elif "include" not in text.split("urlpatterns")[0]:
        log("! urls.py: add `include` to the django.urls import manually.")
    anchor = '    path("admin/", admin.site.urls),\n'
    if anchor not in text:
        log('! urls.py: add path("api/whatsapp/", include("apps.whatsapp.urls")) and '
            'path("api/", include("apps.chat.urls")) to urlpatterns manually.')
        return
    text = text.replace(
        anchor,
        anchor
        + '    path("api/whatsapp/", include("apps.whatsapp.urls")),\n'
        + '    path("api/", include("apps.chat.urls")),\n',
        1,
    )
    write(path, text)
    log("+ config/urls.py: /api/chat/ and /api/whatsapp/webhook/ routes added")


def patch_env_example() -> None:
    path = BASE / ".env.example"
    if not path.exists():
        log("! .env.example not found, skipped")
        return
    text = read(path)
    if "CHAT_API_KEY" in text:
        log("= .env.example: already patched")
        return
    write(path, text.rstrip("\n") + "\n" + ENV_EXAMPLE_BLOCK)
    log("+ .env.example: CHAT_API_KEY and TWILIO_WEBHOOK_URL added")


def patch_env() -> None:
    path = BASE / ".env"
    if not path.exists():
        log("! .env not found: copy .env.example to .env and set CHAT_API_KEY yourself")
        return
    data = path.read_bytes()
    if b"CHAT_API_KEY" in data:
        log("= .env: CHAT_API_KEY already present")
        return
    key = secrets.token_urlsafe(32)
    prefix = b"" if data.endswith(b"\n") or not data else b"\n"
    with path.open("ab") as handle:
        handle.write(prefix + f"\n# Chat API (phase 3)\nCHAT_API_KEY='{key}'\n".encode("utf-8"))
    log("+ .env: generated a random CHAT_API_KEY (open .env to read it)")


def patch_readme() -> None:
    path = BASE / "README.md"
    if not path.exists():
        log("! README.md not found, skipped")
        return
    text = read(path)
    if README_MARKER in text:
        log("= README.md: section already present")
        return
    write(path, text.rstrip("\n") + "\n" + README_BLOCK)
    log("+ README.md: phases 3-4 section appended")


if __name__ == "__main__":
    patch_settings()
    patch_urls()
    patch_env_example()
    patch_env()
    patch_readme()
    print("\nNext: python manage.py makemigrations chat && python manage.py migrate && python manage.py test tests")
