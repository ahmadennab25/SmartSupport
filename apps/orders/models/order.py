from decimal import Decimal

from django.db import IntegrityError, models, transaction
from django.db.models import DecimalField, ExpressionWrapper, F, Max, Sum
from django.utils import timezone

from apps.core.models import TimeStampedModel


class Order(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        PROCESSING = "processing", "Processing"
        SHIPPED = "shipped", "Shipped"
        OUT_FOR_DELIVERY = "out_for_delivery", "Out for delivery"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"
        RETURNED = "returned", "Returned"

    class PaymentMethod(models.TextChoices):
        CARD = "card", "Credit/debit card"
        CASH_ON_DELIVERY = "cod", "Cash on delivery"
        BANK_TRANSFER = "bank_transfer", "Bank transfer"
        WALLET = "wallet", "E-wallet"

    class PaymentStatus(models.TextChoices):
        UNPAID = "unpaid", "Unpaid"
        PAID = "paid", "Paid"
        REFUND_PENDING = "refund_pending", "Refund pending"
        REFUNDED = "refunded", "Refunded"

    CANCELLABLE_STATUSES = (Status.PENDING, Status.CONFIRMED, Status.PROCESSING)

    # The number customers quote in WhatsApp (e.g. "order 1025").
    order_number = models.PositiveIntegerField(unique=True, blank=True)
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="orders"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    payment_method = models.CharField(
        max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CARD
    )
    payment_status = models.CharField(
        max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID
    )
    shipping_address = models.TextField(blank=True)
    carrier = models.CharField(max_length=100, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=3, default="JOD")
    placed_at = models.DateTimeField(default=timezone.now)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    estimated_delivery_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-placed_at"]
        indexes = [models.Index(fields=["customer", "status"])]

    def __str__(self) -> str:
        return f"Order #{self.order_number}"

    NUMBER_RETRIES = 5

    @staticmethod
    def _next_order_number() -> int:
        last = Order.objects.aggregate(last=Max("order_number"))["last"]
        return (last or 1000) + 1

    def save(self, *args, **kwargs):
        """A new order gets the next free number. If two orders are saved at the same moment and pick the same
        number, the unique constraint rejects the second insert and it is retried with a fresh number."""
        if self.order_number is not None:
            return super().save(*args, **kwargs)
        for attempt in range(1, self.NUMBER_RETRIES + 1):
            self.order_number = self._next_order_number()
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError as exc:
                if "order_number" not in str(exc) or attempt == self.NUMBER_RETRIES:
                    raise
                self.order_number = None

    @property
    def is_cancellable(self) -> bool:
        return self.status in self.CANCELLABLE_STATUSES

    @property
    def days_since_delivery(self) -> int | None:
        if not self.delivered_at:
            return None
        return (timezone.now() - self.delivered_at).days

    @property
    def is_delayed(self) -> bool:
        """True when an active shipment is past its estimated delivery date."""
        active = self.status in (self.Status.SHIPPED, self.Status.OUT_FOR_DELIVERY)
        return bool(
            active
            and self.estimated_delivery_date
            and self.estimated_delivery_date < timezone.localdate()
        )

    def recalculate_total(self, commit: bool = True) -> Decimal:
        total = Decimal("0.00")
        if self.pk:
            line = ExpressionWrapper(
                F("quantity") * F("unit_price"),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
            total = self.items.aggregate(total=Sum(line))["total"] or Decimal("0.00")
        self.total_amount = total
        if commit and self.pk:
            self.save(update_fields=["total_amount", "updated_at"])
        return total
