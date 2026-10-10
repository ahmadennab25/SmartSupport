import re

from apps.customers.models import Customer

E164_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")
DEFAULT_CUSTOMER_NAME = "WhatsApp Customer"


class InvalidPhoneNumber(ValueError):
    """Raised when a phone number cannot be converted to E.164 format."""


def normalize_phone(raw: str) -> str:
    """'whatsapp:+962 79-000-0001' -> '+962790000001'."""
    value = (raw or "").strip()
    if value.lower().startswith("whatsapp:"):
        value = value[len("whatsapp:"):]
    value = re.sub(r"[\s\-().]", "", value)
    if value.startswith("00"):
        value = "+" + value[2:]
    if not E164_PATTERN.match(value):
        raise InvalidPhoneNumber(f"Invalid phone number: {raw!r}")
    return value


def get_or_create_customer(phone_number: str, display_name: str = "") -> tuple[Customer, bool]:
    """Identify a customer by phone number; unknown numbers get a new customer record."""
    phone = normalize_phone(phone_number)
    name = (display_name or "").strip() or DEFAULT_CUSTOMER_NAME
    return Customer.objects.get_or_create(phone_number=phone, defaults={"full_name": name[:150]})
