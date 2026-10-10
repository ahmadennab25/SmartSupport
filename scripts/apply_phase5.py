"""One-time, NON-destructive patch that wires phase 5 (RAG) into an existing SmartSupport project.

It only ADDS things, plus one small guarded fix in apps/agent/tools.py. It never deletes your own
lines and is safe to run twice.

Usage (from the project root):  python scripts/apply_phase5.py
"""
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent

SETTINGS_BLOCK = '''# --- RAG / knowledge base (phase 5) ------------------------------------------
KNOWLEDGE_BASE_DIR = BASE_DIR / "knowledge_base"
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "4"))  # passages returned to the agent
RAG_MIN_SCORE = float(os.getenv("RAG_MIN_SCORE", "0.2"))  # minimum cosine similarity (0-1)
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "64"))
'''

ENV_EXAMPLE_BLOCK = """
# RAG (phase 5)
RAG_TOP_K=4
RAG_MIN_SCORE=0.2
EMBEDDING_BATCH_SIZE=64
"""

TOOLS_OLD = '''    try:
        return tool.handler(customer, **arguments)
    except TicketError as exc:
        return {"error": str(exc)}
    except TypeError:
        logger.warning("Bad arguments for tool %s: %r", name, arguments, exc_info=True)
        return {"error": "Invalid or missing tool arguments."}
'''
TOOLS_NEW = '''    try:
        inspect.signature(tool.handler).bind(customer, **arguments)
    except TypeError as exc:
        logger.warning("Bad arguments for tool %s: %s", name, exc)
        return {"error": "Invalid or missing tool arguments."}
    try:
        return tool.handler(customer, **arguments)
    except TicketError as exc:
        return {"error": str(exc)}
'''

README_MARKER = "## RAG: policy search (phase 5)"
README_BLOCK = '''
## RAG: policy search (phase 5)

**What goes where:** policies and FAQs (documents) -> RAG; orders, shipping and tickets (changing records) -> database tools.

**Pipeline**
1. `knowledge_base/<slug>.<ar|en>.md` holds the policies (one file per topic and language).
2. `python manage.py ingest_knowledge` splits each file by `##` section (chunks of at most 700 characters,
   each prefixed with the document title and section), embeds the chunks with `text-embedding-3-small`
   (1536 dimensions) and stores them in PostgreSQL with pgvector (`KnowledgeDocument`, `KnowledgeChunk`).
   Unchanged files are skipped (content hash); use `--force` to re-embed and `--prune` to drop deleted files.
3. When a customer asks about a store rule, the agent calls the `search_policies` tool. The question is embedded
   and compared with the chunks by cosine similarity. The top `RAG_TOP_K` chunks above `RAG_MIN_SCORE` are returned
   and the agent answers only from them. If nothing is relevant it says so and offers a support ticket.

**Setup**
```bash
python manage.py init_db                  # makes sure the pgvector extension exists (safe to repeat)
python manage.py makemigrations           # should print "No changes detected"
python manage.py migrate
python manage.py ingest_knowledge         # needs OPENAI_API_KEY; embeds ~64 chunks
python manage.py test tests
```
Edit a policy file, run `ingest_knowledge` again, and the agent uses the new text immediately (no prompt change).
Tune `RAG_TOP_K` and `RAG_MIN_SCORE` in `.env` using the retrieval evaluation (phase 7).
For large knowledge bases add an HNSW index on `KnowledgeChunk.embedding`; it is not needed at this size.
'''


def log(message: str) -> None:
    print(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def patch_settings() -> None:
    path = BASE / "config" / "settings.py"
    text = read(path)
    changed = False
    if '"apps.knowledge"' not in text:
        anchor = '    "apps.whatsapp",\n'
        if anchor in text:
            text = text.replace(anchor, anchor + '    "apps.knowledge",\n', 1)
            changed = True
        else:
            log('! settings.py: add "apps.knowledge" to INSTALLED_APPS manually.')
    if "RAG_TOP_K" not in text:
        text = text.rstrip("\n") + "\n\n" + SETTINGS_BLOCK
        changed = True
    if changed:
        write(path, text)
        log("+ config/settings.py: apps.knowledge registered and RAG settings added")
    else:
        log("= config/settings.py: already patched")


def patch_tools() -> None:
    path = BASE / "apps" / "agent" / "tools.py"
    if not path.exists():
        log("! apps/agent/tools.py not found, skipped")
        return
    text = read(path)
    if "inspect.signature(tool.handler).bind" in text:
        log("= apps/agent/tools.py: already patched")
        return
    if TOOLS_OLD not in text or "import json\nimport logging\n" not in text:
        log("! apps/agent/tools.py differs from the delivered version: patch skipped, nothing changed.")
        return
    text = text.replace(TOOLS_OLD, TOOLS_NEW, 1)
    if "import inspect\n" not in text:
        text = text.replace("import json\nimport logging\n", "import inspect\nimport json\nimport logging\n", 1)
    write(path, text)
    log("+ apps/agent/tools.py: argument errors are now separated from bugs inside tools")


def patch_env_example() -> None:
    path = BASE / ".env.example"
    if not path.exists():
        log("! .env.example not found, skipped")
        return
    text = read(path)
    if "RAG_TOP_K" in text:
        log("= .env.example: already patched")
        return
    write(path, text.rstrip("\n") + "\n" + ENV_EXAMPLE_BLOCK)
    log("+ .env.example: RAG variables added (all optional, defaults exist)")


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
    log("+ README.md: phase 5 section appended")


if __name__ == "__main__":
    patch_settings()
    patch_tools()
    patch_env_example()
    patch_readme()
    print("\nNext: python manage.py init_db && python manage.py makemigrations && python manage.py migrate "
          "&& python manage.py ingest_knowledge && python manage.py test tests")
