from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import TimeStampedModel


class OrderItem(TimeStampedModel):
    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        "orders.Product", on_delete=models.PROTECT, related_name="order_items"
    )
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)], default=1)
    unit_price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["order", "product"], name="unique_product_per_order")
        ]

    def __str__(self) -> str:
        return f"{self.quantity} x {self.product.name}"

    @property
    def line_total(self):
        return self.quantity * self.unit_price
