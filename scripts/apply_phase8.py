"""One-time, NON-destructive patch: make prompt v3 the default (evaluated in phase 7).

Changes only the default value "v2" -> "v3" in three places, adds AGENT_PROMPT_VERSION to settings.py and
.env.example so it can be set from .env. Each replacement happens only if the exact old text is found.
Safe to run twice.   Usage (project root):  python scripts/apply_phase8.py
"""
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent

REPLACEMENTS = [
    ("apps/agent/prompts.py", 'getattr(settings, "AGENT_PROMPT_VERSION", "v2")', 'getattr(settings, "AGENT_PROMPT_VERSION", "v3")'),
    ("evaluation/runner.py", 'getattr(settings, "AGENT_PROMPT_VERSION", "v2")', 'getattr(settings, "AGENT_PROMPT_VERSION", "v3")'),
    ("apps/core/management/commands/evaluate_agent.py", 'choices=["v1", "v2", "v3"], default="v2"', 'choices=["v1", "v2", "v3"], default="v3"'),
]
SETTINGS_BLOCK = '''# --- Agent prompt (phase 8) ----------------------------------------------------
AGENT_PROMPT_VERSION = os.getenv("AGENT_PROMPT_VERSION", "v3")  # v1, v2 or v3 (see apps/agent/prompts.py)
'''


def patch_defaults() -> None:
    for relative, old, new in REPLACEMENTS:
        path = BASE / relative
        if not path.exists():
            print(f"! {relative} not found, skipped")
            continue
        text = path.read_text(encoding="utf-8")
        if new in text:
            print(f"= {relative}: already patched")
        elif old in text:
            path.write_text(text.replace(old, new, 1), encoding="utf-8")
            print(f"+ {relative}: default prompt version is now v3")
        else:
            print(f"! {relative}: expected text not found, nothing changed (set AGENT_PROMPT_VERSION=v3 in .env instead)")


def patch_settings() -> None:
    path = BASE / "config" / "settings.py"
    text = path.read_text(encoding="utf-8")
    if "AGENT_PROMPT_VERSION" in text:
        print("= config/settings.py: already patched")
        return
    path.write_text(text.rstrip("\n") + "\n\n" + SETTINGS_BLOCK, encoding="utf-8")
    print("+ config/settings.py: AGENT_PROMPT_VERSION added")


def patch_env_example() -> None:
    path = BASE / ".env.example"
    if not path.exists():
        print("! .env.example not found, skipped")
        return
    text = path.read_text(encoding="utf-8")
    if "AGENT_PROMPT_VERSION" in text:
        print("= .env.example: already patched")
        return
    path.write_text(text.rstrip("\n") + "\n\n# Agent system prompt version: v1, v2 or v3 (default v3)\nAGENT_PROMPT_VERSION=v3\n", encoding="utf-8")
    print("+ .env.example: AGENT_PROMPT_VERSION added")


if __name__ == "__main__":
    patch_defaults()
    patch_settings()
    patch_env_example()
    print("\nNext: python manage.py check && python manage.py test tests")
