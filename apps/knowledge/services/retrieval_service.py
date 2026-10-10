"""Semantic search over the policy chunks: cosine similarity computed with NumPy."""
from dataclasses import dataclass

import numpy as np
from django.conf import settings

from apps.knowledge.models import KnowledgeChunk

from .embedding_service import embed_query


@dataclass(frozen=True)
class RetrievedChunk:
    slug: str
    title: str
    language: str
    section: str
    content: str
    score: float  # cosine similarity: 1.0 = identical direction, ~0 = unrelated


def rank_by_cosine(query_vector, rows, top_k: int, threshold: float) -> list[tuple[int, float]]:
    """rows: [(chunk_id, embedding), ...]. Returns [(chunk_id, score), ...] best first,
    keeping at most top_k results whose score is >= threshold. Pure function, no database."""
    if not rows:
        return []
    query = np.asarray(query_vector, dtype=np.float64)
    query_norm = np.linalg.norm(query)
    if query_norm == 0:
        return []
    ids = [chunk_id for chunk_id, _ in rows]
    matrix = np.asarray([embedding for _, embedding in rows], dtype=np.float64)
    norms = np.linalg.norm(matrix, axis=1)
    norms[norms == 0] = 1.0
    scores = (matrix @ query) / (norms * query_norm)
    best = np.argsort(-scores, kind="stable")[:top_k]
    return [(ids[i], float(scores[i])) for i in best if scores[i] >= threshold]


def search(query: str, top_k=None, language=None, min_score=None, client=None) -> list[RetrievedChunk]:
    """Return the most relevant chunks above `min_score`.

    If `language` is given, that language is searched first; when it yields nothing relevant,
    all languages are searched (the embedding model is multilingual).
    """
    query = (query or "").strip()
    if not query:
        return []
    top_k = max(1, min(int(top_k or getattr(settings, "RAG_TOP_K", 4)), 10))
    threshold = getattr(settings, "RAG_MIN_SCORE", 0.2) if min_score is None else min_score

    vector = embed_query(query, client)
    base = KnowledgeChunk.objects.filter(document__is_active=True)

    def run(queryset) -> list[RetrievedChunk]:
        ranked = rank_by_cosine(vector, list(queryset.values_list("id", "embedding")), top_k, threshold)
        if not ranked:
            return []
        chunks = KnowledgeChunk.objects.select_related("document").in_bulk([chunk_id for chunk_id, _ in ranked])
        return [
            RetrievedChunk(
                slug=chunks[chunk_id].document.slug,
                title=chunks[chunk_id].document.title,
                language=chunks[chunk_id].document.language,
                section=chunks[chunk_id].section,
                content=chunks[chunk_id].content,
                score=score,
            )
            for chunk_id, score in ranked
        ]

    if language:
        results = run(base.filter(document__language=language))
        if results:
            return results
    return run(base)
