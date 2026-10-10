from django.db import models

from apps.core.models import TimeStampedModel


class ChatMessage(TimeStampedModel):
    """One message of a conversation. Assistant rows also store metrics used by the evaluation."""

    class Role(models.TextChoices):
        USER = "user", "Customer"
        ASSISTANT = "assistant", "AI agent"

    class Channel(models.TextChoices):
        API = "api", "API"
        WHATSAPP = "whatsapp", "WhatsApp"

    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="chat_messages"
    )
    channel = models.CharField(max_length=10, choices=Channel.choices, default=Channel.API)
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    tool_calls = models.JSONField(default=list, blank=True)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    model_name = models.CharField(max_length=50, blank=True)
    prompt_tokens = models.PositiveIntegerField(null=True, blank=True)
    completion_tokens = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["customer", "created_at"])]

    def __str__(self) -> str:
        return f"{self.role}: {self.content[:40]}"
