import re

from django.db import transaction

from apps.core.utils import local_date_iso
from apps.customers.models import Customer
from apps.orders.models import Order
from apps.orders.services.order_service import get_customer_order
from apps.tickets.models import Ticket, TicketMessage

URGENT_KEYWORDS = (
    "fraud",
    "unauthorized",
    "charged twice",
    "double charge",
    "احتيال",
    "خصم مرتين",
    "خصم مزدوج",
    "سحب بدون",
)
MAX_REFERENCE_DIGITS = 9


class TicketError(Exception):
    """A business-rule error. The message is safe to show to the agent."""


def classify_priority(category: str, description: str, order: Order | None = None) -> str:
    """Rule-based priority: urgent > high > medium > low."""
    text = (description or "").lower()
    if any(keyword in text for keyword in URGENT_KEYWORDS):
        return Ticket.Priority.URGENT
    if (
        category == Ticket.Category.REFUND
        and order is not None
        and order.payment_status == Order.PaymentStatus.REFUND_PENDING
    ):
        return Ticket.Priority.URGENT
    if category == Ticket.Category.DELIVERY_DELAY and order is not None and order.is_delayed:
        return Ticket.Priority.HIGH
    if category in (Ticket.Category.PAYMENT, Ticket.Category.REFUND):
        return Ticket.Priority.HIGH
    if category == Ticket.Category.OTHER and order is None:
        return Ticket.Priority.LOW
    return Ticket.Priority.MEDIUM


def parse_ticket_reference(value) -> int | None:
    """Accept 'TKT-000012', 'tkt 12', 12, '12'."""
    digits = re.sub(r"\D", "", str(value if value is not None else ""))
    if not digits or len(digits) > MAX_REFERENCE_DIGITS:
        return None
    return int(digits)


def get_customer_ticket(customer: Customer, reference) -> Ticket | None:
    pk = parse_ticket_reference(reference)
    if pk is None:
        return None
    return Ticket.objects.select_related("order").filter(customer=customer, pk=pk).first()


def list_customer_tickets(customer: Customer, only_open: bool = True, limit: int = 5) -> list[Ticket]:
    queryset = Ticket.objects.select_related("order").filter(customer=customer)
    if only_open:
        queryset = queryset.exclude(status__in=Ticket.CLOSED_STATUSES)
    return list(queryset.order_by("-created_at")[:limit])


def describe_ticket(ticket: Ticket) -> dict:
    last_staff = (
        ticket.messages.filter(sender_type=TicketMessage.SenderType.STAFF)
        .order_by("-created_at")
        .first()
    )
    return {
        "reference": ticket.reference,
        "subject": ticket.subject,
        "category": ticket.get_category_display(),
        "priority": ticket.get_priority_display(),
        "status": ticket.status,
        "status_label": ticket.get_status_display(),
        "escalated_to_human": ticket.escalated_to_human,
        "linked_order": ticket.order.order_number if ticket.order_id else None,
        "created_on": local_date_iso(ticket.created_at),
        "last_updated_on": local_date_iso(ticket.updated_at),
        "resolved_on": local_date_iso(ticket.resolved_at),
        "latest_staff_reply": last_staff.body if last_staff else None,
    }


@transaction.atomic
def create_ticket(
    customer: Customer,
    subject: str,
    description: str,
    category: str = Ticket.Category.OTHER,
    order_number=None,
    created_by_ai: bool = True,
) -> tuple[Ticket, bool]:
    """Create a ticket. Returns (ticket, created). An open ticket for the same order and
    category is reused instead of creating a duplicate."""
    subject = (subject or "").strip()[:200]
    description = (description or "").strip()
    if not subject or not description:
        raise TicketError("A subject and a description are required.")
    if category not in Ticket.Category.values:
        category = Ticket.Category.OTHER

    order = None
    if order_number not in (None, ""):
        order = get_customer_order(customer, order_number)
        if order is None:
            raise TicketError("No order with this number was found for this customer.")

    if order is not None:
        existing = (
            Ticket.objects.select_related("order")
            .filter(customer=customer, order=order, category=category)
            .exclude(status__in=Ticket.CLOSED_STATUSES)
            .first()
        )
        if existing:
            return existing, False

    ticket = Ticket.objects.create(
        customer=customer,
        order=order,
        category=category,
        priority=classify_priority(category, description, order),
        subject=subject,
        description=description,
        created_by_ai=created_by_ai,
    )
    TicketMessage.objects.create(
        ticket=ticket, sender_type=TicketMessage.SenderType.CUSTOMER, body=description
    )
    return ticket, True


@transaction.atomic
def add_customer_update(customer: Customer, reference, text: str) -> Ticket:
    ticket = get_customer_ticket(customer, reference)
    if ticket is None:
        raise TicketError("No ticket with this reference was found for this customer.")
    if not ticket.is_open:
        raise TicketError(
            "This ticket is already resolved or closed. Create a new ticket if the problem persists."
        )
    text = (text or "").strip()
    if not text:
        raise TicketError("The update text is required.")
    TicketMessage.objects.create(
        ticket=ticket, sender_type=TicketMessage.SenderType.CUSTOMER, body=text
    )
    if ticket.status == Ticket.Status.WAITING_CUSTOMER:
        ticket.status = Ticket.Status.IN_PROGRESS
        ticket.save(update_fields=["status", "updated_at"])
    return ticket


@transaction.atomic
def escalate_to_human(
    customer: Customer, reason: str, reference=None, order_number=None
) -> Ticket:
    """Hand a case to staff. Escalates an existing ticket, or opens a new escalated one."""
    reason = (reason or "").strip()
    if not reason:
        raise TicketError("A reason for the escalation is required.")

    if reference not in (None, ""):
        ticket = get_customer_ticket(customer, reference)
        if ticket is None:
            raise TicketError("No ticket with this reference was found for this customer.")
        if not ticket.is_open:
            raise TicketError("This ticket is already resolved or closed.")
    else:
        ticket, _ = create_ticket(
            customer,
            subject="Customer requested human assistance",
            description=reason,
            category=Ticket.Category.OTHER,
            order_number=order_number,
        )

    ticket.status = Ticket.Status.ESCALATED
    ticket.escalated_to_human = True
    ticket.escalation_reason = reason
    if ticket.priority in (Ticket.Priority.LOW, Ticket.Priority.MEDIUM):
        ticket.priority = Ticket.Priority.HIGH
    ticket.save()
    TicketMessage.objects.create(
        ticket=ticket,
        sender_type=TicketMessage.SenderType.SYSTEM,
        body=f"Escalated to a human agent. Reason: {reason}",
    )
    return ticket
