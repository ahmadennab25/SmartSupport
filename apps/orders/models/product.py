from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import TimeStampedModel


class Product(TimeStampedModel):
    sku = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=200, help_text="English name")
    name_ar = models.CharField(max_length=200, blank=True, help_text="Arabic name")
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    stock_quantity = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.sku})"
