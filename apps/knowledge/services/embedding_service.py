from django.conf import settings

from apps.agent.llm_client import get_openai_client
from apps.knowledge.models import EMBEDDING_DIMENSIONS


class EmbeddingError(RuntimeError):
    """The embedding API returned something unusable."""


def embed_texts(texts: list[str], client=None) -> list[list[float]]:
    """Embed texts in batches. Returns one vector per text, in the same order."""
    if not texts:
        return []
    client = client or get_openai_client()
    batch_size = getattr(settings, "EMBEDDING_BATCH_SIZE", 64)
    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        response = client.embeddings.create(
            model=settings.OPENAI_EMBEDDING_MODEL,
            input=batch,
            dimensions=EMBEDDING_DIMENSIONS,
        )
        ordered = sorted(response.data, key=lambda item: item.index)
        if len(ordered) != len(batch):
            raise EmbeddingError("The embedding API returned a different number of vectors.")
        vectors.extend(list(item.embedding) for item in ordered)
    for vector in vectors:
        if len(vector) != EMBEDDING_DIMENSIONS:
            raise EmbeddingError(
                f"Expected {EMBEDDING_DIMENSIONS} dimensions, got {len(vector)}. "
                "Check OPENAI_EMBEDDING_MODEL."
            )
    return vectors


def embed_query(text: str, client=None) -> list[float]:
    return embed_texts([text], client)[0]
