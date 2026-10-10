# SmartSupport AI

A WhatsApp customer-service system for an online store. A single AI agent understands customer
messages, looks up orders, answers policy questions with RAG and creates or follows up on support
tickets, handing complex cases over to a human agent.

> **Status:** Phases 1-2 done (project setup, database models, demo data, admin dashboard).
> Next: Twilio webhook, agent tools, RAG, the agent itself, evaluation.

## 1. Problem Statement
Online stores receive many repetitive questions (order status, return policy, payment options) and
complaints. Support staff spend most of their time on answers that already exist in the store
policies or in the orders database, while customers wait for replies. This hurts customer
satisfaction and support costs, especially for small stores.

## 2. Proposed Solution
Customers chat with the store on WhatsApp. One AI agent decides which tool to use:
- **RAG** over store policies and FAQs (returns, refunds, shipping, payment).
- **Database tools** for real order, shipping and ticket data in PostgreSQL (never invented by the model).
- **Ticket tools** to open complaints, set priority, follow up and escalate to staff.

Staff manage orders and tickets from a customised Django Admin dashboard.
A single agent with tools was chosen because it is simpler to test, cheaper and easier to explain than a multi-agent design, and it is enough for this scope.

## 3. Technologies Used
Python, Django, Django REST Framework, PostgreSQL, NumPy, OpenAI API (`gpt-4o-mini`,
`text-embedding-3-small`), Twilio WhatsApp API, python-dotenv, psutil.

## 4. Project Structure
```
smartsupport/
├── config/                  # settings, urls, wsgi/asgi
├── apps/
│   ├── core/                # base model, management commands (init_db, seed_demo_data)
│   ├── customers/           # models/customer.py, admin.py
│   ├── orders/              # models/{product,order,order_item}.py, admin.py
│   ├── tickets/             # models/{ticket,ticket_message}.py, admin.py
│   ├── knowledge/           # (next) RAG: chunks, embeddings, retrieval
│   ├── agent/               # (next) agent, tools, prompts
│   └── whatsapp/            # (next) Twilio webhook
├── knowledge_base/          # policy documents (Arabic/English)
├── evaluation/              # (next) test cases and performance measurement
├── tests/
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```
Architecture rule: `views -> services -> (AI / data access) -> database`. Business logic lives in
`services/`, never inside views.

## 5. How to Run the Project
Requires Python 3.10+ and PostgreSQL.

```bash
# 1. Clone
git clone <your-repo-url> smartsupport && cd smartsupport

# 2. Virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Dependencies
pip install -r requirements.txt

# 4. Environment variables
cp .env.example .env               # Windows: copy .env.example .env
# then edit .env and fill in the real values (see section 6)

# 5. Database: creates the database and schema if missing
python manage.py init_db

# 6. Migrations
python manage.py makemigrations customers orders tickets
python manage.py migrate

# 7. Demo data (use YOUR WhatsApp number so the demo customer is you)
python manage.py seed_demo_data --phone +962791234567
python manage.py createsuperuser

# 8. Start
python manage.py runserver

# 9. Open http://127.0.0.1:8000/admin/
```
Run tests: `python manage.py test tests`

### PyCharm tips
1. Settings -> Project -> Python Interpreter -> add the `.venv` interpreter.
2. Run/Debug Configurations -> add a *Python* configuration with script `manage.py` and parameters
   `runserver` (the `.env` file is loaded automatically by `config/settings.py`).

## 6. Environment Variables / Secrets
Copy `.env.example` to `.env`. Never commit `.env`.

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Django secret key |
| `DEBUG` | `True` in development only |
| `ALLOWED_HOSTS` | Comma-separated hosts (`*` for local development) |
| `DATABASE_HOST/PORT/USER/PASSWORD/NAME` | PostgreSQL connection |
| `DATABASE_SCHEMA` | Schema used by the project (created by `init_db`) |
| `OPENAI_API_KEY` | OpenAI key for the agent and embeddings |
| `OPENAI_MODEL` | Chat model (`gpt-4o-mini`) |
| `OPENAI_EMBEDDING_MODEL` | Embedding model (`text-embedding-3-small`) |
| `OPENAI_MAX_RETRIES`, `OPENAI_DEFAULT_TEMPERATURE`, `OPENAI_DEFAULT_ERROR_MESSAGE` | LLM behaviour and fallback message |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` | Twilio credentials |
| `TWILIO_WHATSAPP_FROM` | Twilio WhatsApp sender, e.g. `whatsapp:+14155238886` |
| `TWILIO_VALIDATE_REQUESTS` | Verify `X-Twilio-Signature` on webhooks (enable in production) |

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

## RAG: policy search (phase 5)

**What goes where:** policies and FAQs (documents) -> RAG; orders, shipping and tickets (changing records) -> database tools.

**Pipeline**
1. `knowledge_base/<slug>.<ar|en>.md` holds the policies (one file per topic and language).
2. `python manage.py ingest_knowledge` splits each file by `##` section (chunks of at most 700 characters,
   each prefixed with the document title and section), embeds the chunks with `text-embedding-3-small`
   (1536 dimensions) and stores them in PostgreSQL as native `double precision[]` arrays (`KnowledgeDocument`, `KnowledgeChunk`).
   Unchanged files are skipped (content hash); use `--force` to re-embed and `--prune` to drop deleted files.
3. When a customer asks about a store rule, the agent calls the `search_policies` tool. The question is embedded
   and compared with the chunks by cosine similarity (computed with NumPy; a few hundred chunks take milliseconds). The top `RAG_TOP_K` chunks above `RAG_MIN_SCORE` are returned
   and the agent answers only from them. If nothing is relevant it says so and offers a support ticket.

**Setup**
```bash
python manage.py init_db                  # creates the database and schema if missing (safe to repeat)
python manage.py makemigrations           # should print "No changes detected"
python manage.py migrate
python manage.py ingest_knowledge         # needs OPENAI_API_KEY; embeds ~64 chunks
python manage.py test tests
```
Edit a policy file, run `ingest_knowledge` again, and the agent uses the new text immediately (no prompt change).
Tune `RAG_TOP_K` and `RAG_MIN_SCORE` in `.env` using the retrieval evaluation (phase 7).
For a much larger knowledge base, switch the column to pgvector (`vector` type with an HNSW index) and let PostgreSQL run the search; it is not needed at this size.

## Grounding rules for the agent (phase 6)

The agent is not a general-knowledge assistant: store facts may only come from tool results.
- Orders and tickets -> database tools; policies/FAQ -> `search_policies` (RAG); products, prices and stock -> `search_products`.
- Anything no tool covers (website, branches, phone numbers, offers...) is answered with "I do not have that information"
  plus an offer to open a ticket or hand over to a human. The system prompt (`apps/agent/prompts.py`) states these
  rules and tests check that they stay in the prompt. Whether the model obeys them is measured in the evaluation (phase 7).
