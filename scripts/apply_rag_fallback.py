"""Small, guarded text fixes after switching the RAG store from pgvector to native PostgreSQL arrays.

Changes requirements.txt (pgvector -> numpy) and corrects README sentences that mention pgvector.
Each replacement happens only if the exact old text is found. Safe to run twice.

Usage (from the project root):  python scripts/apply_rag_fallback.py
"""
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent

README_FIXES = [
    ("PostgreSQL + pgvector,", "PostgreSQL, NumPy,"),
    ("Requires Python 3.10+ and PostgreSQL with the pgvector extension available.", "Requires Python 3.10+ and PostgreSQL."),
    (
        "stores them in PostgreSQL with pgvector (`KnowledgeDocument`, `KnowledgeChunk`).",
        "stores them in PostgreSQL as native `double precision[]` arrays (`KnowledgeDocument`, `KnowledgeChunk`).",
    ),
    (
        "and compared with the chunks by cosine similarity.",
        "and compared with the chunks by cosine similarity (computed with NumPy; a few hundred chunks take milliseconds).",
    ),
    (
        "# 5. Database: creates the database, schema and pgvector extension if missing",
        "# 5. Database: creates the database and schema if missing",
    ),
    (
        "# makes sure the pgvector extension exists (safe to repeat)",
        "# creates the database and schema if missing (safe to repeat)",
    ),
    (
        "For large knowledge bases add an HNSW index on `KnowledgeChunk.embedding`; it is not needed at this size.",
        "For a much larger knowledge base, switch the column to pgvector (`vector` type with an HNSW index) and let "
        "PostgreSQL run the search; it is not needed at this size.",
    ),
]


def fix_requirements() -> None:
    path = BASE / "requirements.txt"
    if not path.exists():
        print("! requirements.txt not found, skipped")
        return
    text = path.read_text(encoding="utf-8")
    if "numpy" in text.lower() and "pgvector" not in text.lower():
        print("= requirements.txt: already patched")
        return
    lines = [line for line in text.splitlines() if not line.lower().startswith("pgvector")]
    if not any(line.lower().startswith("numpy") for line in lines):
        lines.append("numpy>=1.26")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("+ requirements.txt: pgvector replaced by numpy")


SETTINGS_OLD = (
    '# The schema is put first in the search_path. "public" stays second so the\n'
    "# pgvector extension (installed in public) remains visible.\n"
)
SETTINGS_NEW = '# The schema is put first in the search_path; "public" stays second as a fallback.\n'


def fix_settings_comment() -> None:
    path = BASE / "config" / "settings.py"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    if SETTINGS_OLD in text:
        path.write_text(text.replace(SETTINGS_OLD, SETTINGS_NEW, 1), encoding="utf-8")
        print("+ config/settings.py: outdated pgvector comment updated (comment only)")
    else:
        print("= config/settings.py: nothing to change")


def fix_readme() -> None:
    path = BASE / "README.md"
    if not path.exists():
        print("! README.md not found, skipped")
        return
    text = path.read_text(encoding="utf-8")
    changed = 0
    for old, new in README_FIXES:
        if old in text:
            text = text.replace(old, new)
            changed += 1
    if changed:
        path.write_text(text, encoding="utf-8")
    print(f"+ README.md: {changed} of {len(README_FIXES)} sentences updated" if changed else "= README.md: nothing to change")


if __name__ == "__main__":
    fix_requirements()
    fix_settings_comment()
    fix_readme()
    print("\nNext: python manage.py makemigrations && python manage.py migrate && python manage.py test tests")
