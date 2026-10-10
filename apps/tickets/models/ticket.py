from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel


class Ticket(TimeStampedModel):
    class Category(models.TextChoices):
        COMPLAINT = "complaint", "Complaint"
        DELIVERY_DELAY = "delivery_delay", "Delivery delay"
        ORDER_ISSUE = "order_issue", "Order issue"
        REFUND = "refund", "Refund"
        RETURN = "return", "Return / exchange"
        PAYMENT = "payment", "Payment problem"
        OTHER = "other", "Other"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        WAITING_CUSTOMER = "waiting_customer", "Waiting for customer"
        ESCALATED = "escalated", "Escalated to human"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"

    CLOSED_STATUSES = (Status.RESOLVED, Status.CLOSED)

    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="tickets"
    )
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tickets",
    )
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    subject = models.CharField(max_length=200)
    description = models.TextField()
    created_by_ai = models.BooleanField(default=False)
    escalated_to_human = models.BooleanField(default=False)
    escalation_reason = models.TextField(blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tickets",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["customer", "status"])]

    def __str__(self) -> str:
        return f"{self.reference} - {self.subject}"

    @property
    def reference(self) -> str:
        """Human-friendly ticket number shown to customers, e.g. TKT-000012."""
        return f"TKT-{self.pk:06d}" if self.pk else "TKT-NEW"

    @property
    def is_open(self) -> bool:
        return self.status not in self.CLOSED_STATUSES

    def clean(self):
        super().clean()
        if self.order_id and self.customer_id and self.order.customer_id != self.customer_id:
            raise ValidationError({"order": "This order does not belong to the selected customer."})

    def save(self, *args, **kwargs):
        if self.status in self.CLOSED_STATUSES and self.resolved_at is None:
            self.resolved_at = timezone.now()
        super().save(*args, **kwargs)
