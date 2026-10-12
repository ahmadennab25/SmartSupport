# SmartSupport AI

A WhatsApp customer-service system for an online store. One AI agent understands customer messages (Arabic or
English), looks up orders in PostgreSQL, answers policy questions with RAG, opens and follows up support tickets, and
hands complex cases to a human agent.

---

## 1. Problem Statement

**What problem are we solving?** Online stores receive a constant stream of repetitive support messages ("where is my
order?", "can I return this after 10 days?", "do you accept cash on delivery?") plus real complaints. Most answers
already exist in the order database or in the store policies, but a human has to look them up and type them.

**Who experiences it?** Small and medium online stores (support staff are overloaded, customers wait hours) and their
customers (who want a quick answer on the app they already use: WhatsApp).

**Why is it important?** Slow or wrong answers cost sales and trust, and support salaries are a fixed cost. An
assistant that answers the repetitive questions correctly, never invents information, and escalates the hard cases lets
staff focus on the customers who really need a person.

## 2. Proposed Solution

Customers chat with the store on WhatsApp (Twilio). A **single AI agent** (OpenAI function calling) decides which
tool to use for each message:

| Question type | Tool | Source of truth |
|---|---|---|
| "Where is my order 1025?" | `lookup_order`, `list_my_orders` | PostgreSQL (orders, shipping, payment) |
| "Can I return it after 10 days?" | `search_policies` (**RAG**) | Policy and FAQ documents (Arabic and English) |
| "Do you sell X? How much is it?" | `search_products` | PostgreSQL product catalog |
| Complaint / follow-up | `create_support_ticket`, `get_ticket_status`, `add_ticket_update` | PostgreSQL (tickets) |
| "I want to talk to a person" | `escalate_to_human` | PostgreSQL (ticket marked escalated) |

**Why this approach**
- *RAG for documents, database tools for records:* policies change rarely and live in text files (edit, re-index, done);
  orders and tickets change constantly and must come from the database, never from the model's memory.
- *One agent with tools* (not a multi-agent system) is simpler to test and explain, cheaper, and enough for this scope.
- *Grounding rules:* the agent may only state store facts returned by a tool. Anything else ("do you have a website?")
  gets "I do not have that information" and an offer to open a ticket. The agent cannot cancel orders or refund money;
  those requests become tickets for staff.
- *Security by design:* the customer is identified from the WhatsApp phone number on the server. Tools never accept a
  customer id from the model, so the agent can only see the data of the person it is talking to.

Staff manage customers, orders, tickets, chat logs and the knowledge base from a customised **Django Admin** dashboard.

## 3. Technologies Used

- **Language / backend:** Python 3.11, Django 5, Django REST Framework
- **Database:** PostgreSQL (psycopg 3). Embeddings are stored as native `double precision[]` columns
- **AI:** OpenAI API: `gpt-4o-mini` (agent, function calling) and `text-embedding-3-small` (RAG)
- **RAG:** markdown chunking, cosine similarity with NumPy
- **Messaging:** Twilio WhatsApp API (sandbox for testing), ngrok for local webhooks
- **Other:** python-dotenv (configuration), psutil (memory measurement), Django's test framework (172 tests)

## 4. Project Structure

```
smartsupport/
├── config/                  # Django settings (all secrets from .env), urls, wsgi/asgi
├── apps/
│   ├── core/                # TimeStampedModel, management commands:
│   │                        #   init_db, seed_demo_data, evaluate_agent, rescore_results
│   ├── customers/           # models/customer.py, services/customer_service.py (phone normalisation), admin
│   ├── orders/              # models/{product,order,order_item}.py, services/{order,product}_service.py, admin
│   ├── tickets/             # models/{ticket,ticket_message}.py, services/ticket_service.py (priority rules), admin
│   ├── knowledge/           # RAG: models (document, chunk), services (chunking, embeddings, ingestion,
│   │                        #   retrieval), command ingest_knowledge, the search_policies tool
│   ├── agent/               # SupportAgent (tool-calling loop), tools.py (tool registry), catalog_tools.py,
│   │                        #   prompts.py (system prompt v1/v2/v3), llm_client.py
│   ├── chat/                # ChatMessage model (history, latency, tokens), chat_service.py,
│   │                        #   views/chat_views.py -> POST /api/chat/
│   └── whatsapp/            # services/twilio_service.py (signature check, TwiML), views/webhook_views.py
├── knowledge_base/          # 10 policy/FAQ documents: <topic>.<ar|en>.md
├── evaluation/              # test cases, scoring, runner, retrieval evaluation, rescoring, results/
├── scripts/ask.py           # send one message to /api/chat/ from the terminal
├── tests/                   # unit and integration tests (OpenAI and Twilio are mocked)
├── requirements.txt
├── .env.example             # every variable the project reads (no real secrets)
├── .gitignore
└── README.md
```

**Request flow** (views contain no business logic):

```
WhatsApp -> Twilio -> POST /api/whatsapp/webhook/ --+
REST client ---------> POST /api/chat/ ------------+
                                                     v
                          views  (HTTP only: auth, parsing, response)
                                                     v
                chat_service  (identify customer by phone, load history, log)
                                                     v
              SupportAgent  (OpenAI function calling, max 5 tool rounds)
          +----------------+----------------+------------------+
    order tools      ticket tools    search_products    search_policies (RAG)
          v                v                v                  v
     services/        services/        services/       knowledge services
          +----------------+---- PostgreSQL --+------------------+
```

## 5. How to Run the Project

**Requirements:** Python 3.10+ (developed on 3.11), PostgreSQL running locally, an OpenAI API key. A Twilio account is
only needed for the WhatsApp demo; everything else works through the REST endpoint.

```bash
# 1. Clone
git clone <repository-url> smartsupport && cd smartsupport

# 2. Virtual environment
python -m venv .venv
source .venv/bin/activate            # Windows (PowerShell): .venv\Scripts\Activate.ps1

# 3. Dependencies
pip install -r requirements.txt

# 4. Environment variables
cp .env.example .env                 # Windows: copy .env.example .env
#    then edit .env: DATABASE_USER, DATABASE_PASSWORD, SECRET_KEY, OPENAI_API_KEY, CHAT_API_KEY (see section 6)

# 5. Database: creates the database and the schema if they do not exist
python manage.py init_db             # needs a PostgreSQL user allowed to create databases;
                                     # otherwise create the database yourself and skip this step

# 6. Migrations
python manage.py migrate

# 7. Demo data: 5 customers, 8 products, 10 orders, 3 tickets.
#    Use YOUR WhatsApp number: it becomes the customer who owns orders 1025 and 1028.
python manage.py seed_demo_data --phone +9627XXXXXXXX

# 8. Knowledge base: chunk, embed and store the policy documents (calls the OpenAI embeddings API)
python manage.py ingest_knowledge    # expect: created=10 ... chunks_written=64

# 9. Admin user for the dashboard
python manage.py createsuperuser

# 10. Start
python manage.py runserver
```

**Access**
- Dashboard: <http://127.0.0.1:8000/admin/> (customers, orders, tickets with actions, chat log, knowledge base)
- Chat API (no WhatsApp needed):
  ```bash
  curl -X POST http://127.0.0.1:8000/api/chat/ \
    -H "X-API-Key: <CHAT_API_KEY>" -H "Content-Type: application/json" \
    -d '{"phone": "+9627XXXXXXXX", "message": "Where is my order 1025?"}'
  ```
  Response: `reply`, `customer`, `tool_calls`, `latency_ms`, `failed`. From a terminal you can also run
  `python scripts/ask.py "وين وصل طلبي 1025؟"`.
- WhatsApp: run `ngrok http 8000`; in the Twilio console (Messaging, Try it out, WhatsApp sandbox) set
  *When a message comes in* to `https://<your-ngrok-domain>/api/whatsapp/webhook/` (POST), join the sandbox from your
  phone, and chat. Start with `TWILIO_VALIDATE_REQUESTS=False`; enable it (with `TWILIO_AUTH_TOKEN`) once it works,
  and set `TWILIO_WEBHOOK_URL` to the exact public URL if the signature check fails behind ngrok.

**Tests** (OpenAI and Twilio are mocked, no key needed): `python manage.py test tests`

**Evaluation** (real OpenAI calls, about 20 minutes and a few cents for the full run):
```bash
python manage.py evaluate_agent --compare --repeat 3                  # main suite, prompts v1/v2/v3 + retrieval
python manage.py evaluate_agent --only agent --suite holdout --compare --repeat 3   # unseen cases
python manage.py rescore_results evaluation/results/<run>/results.json              # re-judge saved replies, no API calls
```
Results (JSON, CSV, summary.md) are written to `evaluation/results/<timestamp>/`.

## 6. Environment Variables / Secrets

Copy `.env.example` to `.env`. **Never commit `.env`.** Only the first five groups are needed to run the project.

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Django secret key (required when `DEBUG=False`) |
| `DEBUG` | `True` for development only |
| `ALLOWED_HOSTS` | Comma-separated hosts (`*` is fine locally, never in production) |
| `DATABASE_HOST`, `DATABASE_PORT`, `DATABASE_USER`, `DATABASE_PASSWORD`, `DATABASE_NAME` | PostgreSQL connection |
| `DATABASE_SCHEMA` | Schema used by the project (default `public`) |
| `OPENAI_API_KEY` | OpenAI key for the agent and the embeddings |
| `OPENAI_MODEL`, `OPENAI_EMBEDDING_MODEL` | Chat model (`gpt-4o-mini`) and embedding model (`text-embedding-3-small`) |
| `OPENAI_MAX_RETRIES`, `OPENAI_DEFAULT_TEMPERATURE`, `OPENAI_DEFAULT_ERROR_MESSAGE` | Retries, sampling temperature, message shown when OpenAI fails |
| `CHAT_API_KEY` | Secret expected in the `X-API-Key` header of `POST /api/chat/` (the endpoint refuses everything if unset) |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` | Twilio credentials (WhatsApp demo only) |
| `TWILIO_WHATSAPP_FROM` | Twilio WhatsApp sender, e.g. `whatsapp:+14155238886` (copy it from your console) |
| `TWILIO_VALIDATE_REQUESTS` | Verify `X-Twilio-Signature` on the webhook (enable once it works; fails closed without a token) |
| `TWILIO_WEBHOOK_URL` | Optional exact public webhook URL used for signature validation (ngrok) |
| `AGENT_PROMPT_VERSION` | System prompt version `v1`, `v2` or `v3` (default `v3`) |
| `AGENT_HISTORY_LIMIT`, `AGENT_MAX_TOOL_ROUNDS`, `CHAT_MAX_MESSAGE_CHARS`, `STORE_NAME` | Conversation memory (10), tool rounds (5), max message length (1500), store name in the prompt |
| `RAG_TOP_K`, `RAG_MIN_SCORE`, `EMBEDDING_BATCH_SIZE` | Passages returned (4), minimum cosine similarity (0.2), embedding batch size (64) |
| `CSRF_TRUSTED_ORIGINS` | Optional, comma-separated (ngrok domains are preconfigured) |

## 7. Evaluation Summary

Full details, tables and analysis are in the performance report. Numbers below come from real runs against the OpenAI API
(`gpt-4o-mini`, temperature 0.3, every case run 3 times, every case a fresh conversation).

| Agent test suite | v1 prompt | v2 prompt | v3 prompt (default) |
|---|---|---|---|
| **Main** (37 cases; used to tune the prompt): task success | 88.3% | 92.8% | 100% |
| Main: correct tool selection | 84.5% | 91.7% | 100% |
| Main: safety and grounding (ownership, prompt injection, no invented facts, scope) | 100% | 100% | 100% |
| **Hold-out** (17 unseen cases): task success, as first scored | 86.3% | 88.2% | 86.3% |
| Hold-out: after correcting 3 faulty checks (agent unchanged) | 98.0% | 100% | 100% |

- **Latency** (agent reply including tool calls, excluding WhatsApp network): mean about 1.9 to 2.1 s, p95 about 2.9 to 3.5 s.
  Suitable for near-real-time chat.
- **Memory:** peak about 116 to 119 MB for the Django process while running the evaluation.
- **RAG retrieval** (27 in-scope questions, Arabic and English): Hit@1 = 92.6%, MRR = 0.935. The two misses are Arabic
  dialect questions. Questions are sent raw, while the agent rewrites them before searching, so this is a conservative figure.
- **Honest limits:** the test sets are small and written by the project author, checks are keyword based, the main suite
  was used to tune the prompt (its 100% is optimistic), three hold-out checks were corrected after reading the replies, and
  all data is synthetic.

## 8. How the Project Meets the Course Requirements

| Requirement | Where |
|---|---|
| Django backend, properly integrated | `config/`, `apps/*` (admin, DRF API, services) |
| AI component: Agentic AI (+ RAG, an NLP technique) | `apps/agent/`, `apps/knowledge/` |
| PostgreSQL, relations, validation, CRUD | `apps/*/models/`, migrations, Django Admin |
| One model per file | `apps/*/models/<model>.py` |
| Views organised by area | `apps/chat/views/`, `apps/whatsapp/views/` |
| Business logic separated from views | `apps/*/services/`, `apps/agent/` |
| APIs designed, consumed, authenticated | `POST /api/chat/` (API key), Twilio webhook (signature), OpenAI API |
| User interaction | WhatsApp (Twilio) and the staff dashboard (Django Admin) |
| Performance evaluation: accuracy, latency, memory | `evaluation/`, performance report |
| README, `.env.example`, `.gitignore`, tests | this file, repository root, `tests/` |

## 9. Known Limitations and Future Work

- No rate limiting, and Twilio retries are not de-duplicated; text messages only (images and voice notes get a polite notice).
- Similarity search runs in NumPy: fine for hundreds or thousands of chunks; for much larger knowledge bases move the
  column to pgvector with an HNSW index.
- The agent cannot act on orders (cancel, refund, change address) by design; staff do it from the dashboard.
- Future work: staff replies sent back to the customer on WhatsApp, a larger and independently written evaluation set,
  query rewriting evaluation for RAG, order actions with explicit customer confirmation and staff approval.
