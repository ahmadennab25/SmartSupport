"""One-time, NON-destructive patch for phase 6 (grounded agent + product search tool).

Adds ONE import line at the end of apps/agent/tools.py (so the new search_products tool is registered)
and appends a README section. Never deletes your lines; safe to run twice.

Usage (from the project root):  python scripts/apply_phase6.py
"""
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent

IMPORT_LINE = "from . import catalog_tools  # noqa: E402,F401  (registers the search_products tool)\n"

README_MARKER = "## Grounding rules for the agent (phase 6)"
README_BLOCK = '''
## Grounding rules for the agent (phase 6)

The agent is not a general-knowledge assistant: store facts may only come from tool results.
- Orders and tickets -> database tools; policies/FAQ -> `search_policies` (RAG); products, prices and stock -> `search_products`.
- Anything no tool covers (website, branches, phone numbers, offers...) is answered with "I do not have that information"
  plus an offer to open a ticket or hand over to a human. The system prompt (`apps/agent/prompts.py`) states these
  rules and tests check that they stay in the prompt. Whether the model obeys them is measured in the evaluation (phase 7).
'''


def patch_tools() -> None:
    path = BASE / "apps" / "agent" / "tools.py"
    if not path.exists():
        print("! apps/agent/tools.py not found, skipped")
        return
    text = path.read_text(encoding="utf-8")
    if "catalog_tools" in text:
        print("= apps/agent/tools.py: already patched")
        return
    path.write_text(text.rstrip("\n") + "\n\n" + IMPORT_LINE, encoding="utf-8")
    print("+ apps/agent/tools.py: search_products tool registered")


def patch_readme() -> None:
    path = BASE / "README.md"
    if not path.exists():
        print("! README.md not found, skipped")
        return
    text = path.read_text(encoding="utf-8")
    if README_MARKER in text:
        print("= README.md: section already present")
        return
    path.write_text(text.rstrip("\n") + "\n" + README_BLOCK, encoding="utf-8")
    print("+ README.md: phase 6 section appended")


if __name__ == "__main__":
    patch_tools()
    patch_readme()
    print("\nNext: python manage.py check && python manage.py test tests")
