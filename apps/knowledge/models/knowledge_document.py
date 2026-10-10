from django.db import models

from apps.core.models import TimeStampedModel


class KnowledgeDocument(TimeStampedModel):
    """One policy/FAQ document in one language, loaded from knowledge_base/<slug>.<lang>.md."""

    class Language(models.TextChoices):
        ARABIC = "ar", "Arabic"
        ENGLISH = "en", "English"

    slug = models.SlugField(max_length=80)
    language = models.CharField(max_length=2, choices=Language.choices)
    title = models.CharField(max_length=200)
    source_path = models.CharField(max_length=300, blank=True)
    content_hash = models.CharField(max_length=64, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["slug", "language"]
        constraints = [
            models.UniqueConstraint(fields=["slug", "language"], name="unique_document_slug_language")
        ]

    def __str__(self) -> str:
        return f"{self.title} [{self.language}]"
