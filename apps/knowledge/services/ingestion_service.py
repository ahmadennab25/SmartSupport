"""Load knowledge_base/<slug>.<lang>.md files into PostgreSQL: chunk, embed, store."""
import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path

from django.conf import settings
from django.db import transaction

from apps.knowledge.models import KnowledgeChunk, KnowledgeDocument

from .chunking import DEFAULT_MAX_CHARS, build_chunk_text, chunk_markdown, parse_title
from .embedding_service import embed_texts

logger = logging.getLogger(__name__)

LANGUAGES = {code for code, _ in KnowledgeDocument.Language.choices}


@dataclass
class IngestReport:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    pruned: int = 0
    chunks: int = 0
    errors: list[str] = field(default_factory=list)


def parse_filename(path: Path) -> tuple[str, str] | None:
    """'returns-policy.ar.md' -> ('returns-policy', 'ar'). None if the name does not follow the pattern."""
    slug, _, language = path.stem.rpartition(".")
    if not slug or language not in LANGUAGES:
        return None
    return slug, language


def _content_hash(text: str) -> str:
    # The embedding model and chunk size are part of the hash: changing either re-embeds the document.
    payload = f"{settings.OPENAI_EMBEDDING_MODEL}\n{DEFAULT_MAX_CHARS}\n{text}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _ingest_file(path: Path, slug: str, language: str, client, force: bool, report: IngestReport) -> None:
    text = path.read_text(encoding="utf-8")
    digest = _content_hash(text)
    document = KnowledgeDocument.objects.filter(slug=slug, language=language).first()
    if document and document.content_hash == digest and not force:
        report.skipped += 1
        return

    title = parse_title(text) or slug
    chunks = chunk_markdown(text)
    if not chunks:
        report.errors.append(f"{path.name}: no content to index")
        return

    texts = [build_chunk_text(title, chunk.section, chunk.text) for chunk in chunks]
    vectors = embed_texts(texts, client)  # network call happens before the DB transaction

    with transaction.atomic():
        is_new = document is None
        if is_new:
            document = KnowledgeDocument(slug=slug, language=language)
        document.title = title
        document.source_path = path.name
        document.content_hash = digest
        document.is_active = True
        document.save()
        document.chunks.all().delete()
        KnowledgeChunk.objects.bulk_create(
            KnowledgeChunk(
                document=document,
                chunk_index=index,
                section=chunk.section,
                content=content,
                embedding=vector,
            )
            for index, (chunk, content, vector) in enumerate(zip(chunks, texts, vectors))
        )
    report.created += int(is_new)
    report.updated += int(not is_new)
    report.chunks += len(chunks)


def ingest_directory(directory, client=None, force: bool = False, prune: bool = False) -> IngestReport:
    """Index every *.md file in `directory`. Unchanged files are skipped unless force=True.
    With prune=True, documents whose file no longer exists are deleted."""
    report = IngestReport()
    seen: set[tuple[str, str]] = set()
    for path in sorted(Path(directory).glob("*.md")):
        parsed = parse_filename(path)
        if parsed is None:
            report.errors.append(f"{path.name}: file name must look like <slug>.<ar|en>.md")
            continue
        seen.add(parsed)
        try:
            _ingest_file(path, *parsed, client=client, force=force, report=report)
        except Exception as exc:
            logger.exception("Could not ingest %s", path.name)
            report.errors.append(f"{path.name}: {exc}")

    if prune:
        for document in KnowledgeDocument.objects.all():
            if (document.slug, document.language) not in seen:
                document.delete()
                report.pruned += 1
    return report
