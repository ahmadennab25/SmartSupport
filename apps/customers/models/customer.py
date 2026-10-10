from django.core.validators import RegexValidator
from django.db import models

from apps.core.models import TimeStampedModel

phone_validator = RegexValidator(
    regex=r"^\+[1-9]\d{7,14}$",
    message="Enter the phone number in international E.164 format, e.g. +962791234567.",
)


class Customer(TimeStampedModel):
    class Language(models.TextChoices):
        ARABIC = "ar", "Arabic"
        ENGLISH = "en", "English"

    full_name = models.CharField(max_length=150)
    phone_number = models.CharField(
        max_length=16,
        unique=True,
        validators=[phone_validator],
        help_text="WhatsApp number in E.164 format. Used to identify the customer.",
    )
    email = models.EmailField(blank=True)
    preferred_language = models.CharField(
        max_length=2, choices=Language.choices, default=Language.ARABIC
    )
    city = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self) -> str:
        return f"{self.full_name} ({self.phone_number})"
