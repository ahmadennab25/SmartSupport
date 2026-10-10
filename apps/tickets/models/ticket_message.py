from django.db import models

from apps.core.models import TimeStampedModel


class TicketMessage(TimeStampedModel):
    class SenderType(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        AI_AGENT = "ai_agent", "AI agent"
        STAFF = "staff", "Support staff"
        SYSTEM = "system", "System"

    ticket = models.ForeignKey("tickets.Ticket", on_delete=models.CASCADE, related_name="messages")
    sender_type = models.CharField(max_length=10, choices=SenderType.choices)
    body = models.TextField()

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.get_sender_type_display()}: {self.body[:40]}"
