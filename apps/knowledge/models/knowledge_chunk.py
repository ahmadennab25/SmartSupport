from django.contrib.postgres.fields import ArrayField
from django.db import models

from apps.core.models import TimeStampedModel

# text-embedding-3-small returns 1536 numbers per text. The embedding service asks the API for
# exactly this size, so other text-embedding-3 models also fit.
EMBEDDING_DIMENSIONS = 1536


class KnowledgeChunk(TimeStampedModel):
    document = models.ForeignKey(
        "knowledge.KnowledgeDocument", on_delete=models.CASCADE, related_name="chunks"
    )
    chunk_index = models.PositiveIntegerField()
    section = models.CharField(max_length=200, blank=True)
    content = models.TextField()
    # Stored as a native PostgreSQL double precision[] column. Similarity is computed with NumPy
    # (see retrieval_service), which is fast for hundreds of chunks and needs no PostgreSQL extension.
    embedding = ArrayField(models.FloatField(), size=EMBEDDING_DIMENSIONS)

    class Meta:
        ordering = ["document_id", "chunk_index"]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "chunk_index"], name="unique_chunk_index_per_document"
            )
        ]

    def __str__(self) -> str:
        return f"{self.document.slug}[{self.document.language}] #{self.chunk_index}"
