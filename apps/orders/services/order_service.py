import re

from apps.core.utils import local_date_iso
from apps.customers.models import Customer
from apps.orders.models import Order

MAX_INT = 2_147_483_647


def parse_order_number(value) -> int | None:
    """Accept 1025, '1025', '#1025', 'order 1025'. Returns None when no usable number exists."""
    digits = re.sub(r"\D", "", str(value if value is not None else ""))
    if not digits:
        return None
    number = int(digits)
    return number if number <= MAX_INT else None


def get_customer_order(customer: Customer, order_number) -> Order | None:
    """Only returns the order if it belongs to this customer (no information leaks)."""
    number = parse_order_number(order_number)
    if number is None:
        return None
    return (
        Order.objects.filter(customer=customer, order_number=number)
        .prefetch_related("items__product")
        .first()
    )


def list_customer_orders(customer: Customer, limit: int = 5) -> list[Order]:
    return list(
        Order.objects.filter(customer=customer)
        .prefetch_related("items__product")
        .order_by("-placed_at")[:limit]
    )


def describe_order(order: Order, include_items: bool = True) -> dict:
    """JSON-safe description of an order, used as tool output for the agent."""
    data = {
        "order_number": order.order_number,
        "status": order.status,
        "status_label": order.get_status_display(),
        "payment_method": order.get_payment_method_display(),
        "payment_status": order.get_payment_status_display(),
        "total_amount": f"{order.total_amount:.2f}",
        "currency": order.currency,
        "placed_on": local_date_iso(order.placed_at),
        "shipped_on": local_date_iso(order.shipped_at),
        "delivered_on": local_date_iso(order.delivered_at),
        "estimated_delivery_date": local_date_iso(order.estimated_delivery_date),
        "is_delayed": order.is_delayed,
        "days_since_delivery": order.days_since_delivery,
        "carrier": order.carrier or None,
        "tracking_number": order.tracking_number or None,
        "can_be_cancelled_before_shipping": order.is_cancellable,
    }
    if include_items:
        data["items"] = [
            {
                "product": item.product.name,
                "product_ar": item.product.name_ar or None,
                "quantity": item.quantity,
                "unit_price": f"{item.unit_price:.2f}",
            }
            for item in order.items.all()
        ]
    return data
