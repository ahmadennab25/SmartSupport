from datetime import timedelta
from decimal import Decimal

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.customers.models import Customer
from apps.customers.services.customer_service import (
    InvalidPhoneNumber,
    get_or_create_customer,
    normalize_phone,
)
from apps.orders.models import Order, OrderItem, Product
from apps.orders.services import order_service
from apps.tickets.models import Ticket, TicketMessage
from apps.tickets.services import ticket_service
from apps.tickets.services.ticket_service import TicketError


class NormalizePhoneTests(SimpleTestCase):
    def test_whatsapp_prefix_and_separators_are_removed(self):
        self.assertEqual(normalize_phone("whatsapp:+962 79-000-0001"), "+962790000001")

    def test_double_zero_prefix(self):
        self.assertEqual(normalize_phone("00962790000001"), "+962790000001")

    def test_invalid_numbers_raise(self):
        for bad in ("0790000001", "abc", "", None):
            with self.subTest(bad=bad):
                with self.assertRaises(InvalidPhoneNumber):
                    normalize_phone(bad)


class CustomerServiceTests(TestCase):
    def test_unknown_number_creates_customer_once(self):
        first, created_first = get_or_create_customer("whatsapp:+962791112233", "Ali")
        second, created_second = get_or_create_customer("+962791112233")
        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(first.full_name, "Ali")


class OrderServiceTests(TestCase):
    def setUp(self):
        self.ali = Customer.objects.create(full_name="Ali", phone_number="+962791111111")
        self.sara = Customer.objects.create(full_name="Sara", phone_number="+962792222222")
        self.product = Product.objects.create(sku="P-1", name="Speaker", name_ar="سماعة", price=Decimal("20.00"))
        self.order = Order.objects.create(
            customer=self.ali,
            order_number=2001,
            status=Order.Status.SHIPPED,
            estimated_delivery_date=timezone.localdate() - timedelta(days=2),
        )
        OrderItem.objects.create(order=self.order, product=self.product, quantity=2, unit_price=Decimal("20.00"))
        self.order.recalculate_total()

    def test_customer_sees_own_order(self):
        self.assertEqual(order_service.get_customer_order(self.ali, "2001"), self.order)

    def test_customer_cannot_see_someone_elses_order(self):
        self.assertIsNone(order_service.get_customer_order(self.sara, 2001))

    def test_parse_order_number(self):
        self.assertEqual(order_service.parse_order_number("#2001"), 2001)
        self.assertEqual(order_service.parse_order_number("order 2001"), 2001)
        self.assertIsNone(order_service.parse_order_number(""))
        self.assertIsNone(order_service.parse_order_number("99999999999999"))

    def test_describe_order(self):
        data = order_service.describe_order(order_service.get_customer_order(self.ali, 2001))
        self.assertEqual(data["total_amount"], "40.00")
        self.assertTrue(data["is_delayed"])
        self.assertEqual(data["items"][0]["quantity"], 2)


class TicketServiceTests(TestCase):
    def setUp(self):
        self.ali = Customer.objects.create(full_name="Ali", phone_number="+962791111111")
        self.sara = Customer.objects.create(full_name="Sara", phone_number="+962792222222")
        self.late_order = Order.objects.create(
            customer=self.ali,
            order_number=3001,
            status=Order.Status.SHIPPED,
            estimated_delivery_date=timezone.localdate() - timedelta(days=3),
        )

    def test_delayed_order_ticket_is_high_priority_and_logged(self):
        ticket, created = ticket_service.create_ticket(
            self.ali, "Late order", "Still not here", Ticket.Category.DELIVERY_DELAY, order_number=3001
        )
        self.assertTrue(created)
        self.assertEqual(ticket.priority, Ticket.Priority.HIGH)
        self.assertEqual(ticket.order, self.late_order)
        self.assertTrue(ticket.created_by_ai)
        self.assertEqual(ticket.messages.count(), 1)

    def test_cannot_open_ticket_for_someone_elses_order(self):
        with self.assertRaises(TicketError):
            ticket_service.create_ticket(self.sara, "x", "y", Ticket.Category.ORDER_ISSUE, order_number=3001)

    def test_duplicate_open_ticket_is_reused(self):
        first, _ = ticket_service.create_ticket(self.ali, "Late", "a", Ticket.Category.DELIVERY_DELAY, 3001)
        second, created = ticket_service.create_ticket(self.ali, "Late again", "b", Ticket.Category.DELIVERY_DELAY, 3001)
        self.assertFalse(created)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Ticket.objects.count(), 1)

    def test_urgent_keywords(self):
        ticket, _ = ticket_service.create_ticket(
            self.ali, "Payment", "I was charged twice", Ticket.Category.PAYMENT
        )
        self.assertEqual(ticket.priority, Ticket.Priority.URGENT)

    def test_unknown_category_falls_back_to_other(self):
        ticket, _ = ticket_service.create_ticket(self.ali, "Hi", "Question", "nonsense")
        self.assertEqual(ticket.category, Ticket.Category.OTHER)

    def test_reference_lookup_formats_and_ownership(self):
        ticket, _ = ticket_service.create_ticket(self.ali, "Hi", "Question", Ticket.Category.COMPLAINT)
        for ref in (ticket.reference, str(ticket.pk), f"tkt {ticket.pk}"):
            with self.subTest(ref=ref):
                self.assertEqual(ticket_service.get_customer_ticket(self.ali, ref), ticket)
        self.assertIsNone(ticket_service.get_customer_ticket(self.sara, ticket.reference))

    def test_update_on_closed_ticket_is_rejected(self):
        ticket, _ = ticket_service.create_ticket(self.ali, "Hi", "Question", Ticket.Category.COMPLAINT)
        ticket.status = Ticket.Status.RESOLVED
        ticket.save()
        with self.assertRaises(TicketError):
            ticket_service.add_customer_update(self.ali, ticket.reference, "more info")

    def test_update_reopens_waiting_ticket(self):
        ticket, _ = ticket_service.create_ticket(self.ali, "Hi", "Question", Ticket.Category.COMPLAINT)
        ticket.status = Ticket.Status.WAITING_CUSTOMER
        ticket.save()
        updated = ticket_service.add_customer_update(self.ali, ticket.reference, "here is the photo")
        self.assertEqual(updated.status, Ticket.Status.IN_PROGRESS)

    def test_escalation_without_ticket_creates_escalated_high_priority_ticket(self):
        ticket = ticket_service.escalate_to_human(self.ali, "Wants to talk to a person")
        self.assertEqual(ticket.status, Ticket.Status.ESCALATED)
        self.assertTrue(ticket.escalated_to_human)
        self.assertEqual(ticket.priority, Ticket.Priority.HIGH)
        self.assertTrue(
            ticket.messages.filter(sender_type=TicketMessage.SenderType.SYSTEM).exists()
        )

    def test_escalating_existing_ticket(self):
        ticket, _ = ticket_service.create_ticket(self.ali, "Hi", "Question", Ticket.Category.COMPLAINT)
        escalated = ticket_service.escalate_to_human(self.ali, "Angry customer", reference=ticket.reference)
        self.assertEqual(escalated.pk, ticket.pk)
        self.assertEqual(escalated.status, Ticket.Status.ESCALATED)
