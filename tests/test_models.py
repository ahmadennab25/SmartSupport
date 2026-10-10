from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase

from apps.customers.models import Customer
from apps.orders.models import Order, OrderItem, Product
from apps.tickets.models import Ticket


class CustomerModelTests(TestCase):
    def test_phone_must_be_e164(self):
        customer = Customer(full_name="Test", phone_number="0791234567")
        with self.assertRaises(ValidationError):
            customer.full_clean()

    def test_valid_phone_passes(self):
        customer = Customer(full_name="Test", phone_number="+962791234567")
        customer.full_clean()


class OrderModelTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(full_name="Ali", phone_number="+962791111111")
        self.product = Product.objects.create(sku="T-1", name="Thing", price=Decimal("10.50"))

    def test_order_number_is_auto_generated(self):
        first = Order.objects.create(customer=self.customer)
        second = Order.objects.create(customer=self.customer)
        self.assertEqual(second.order_number, first.order_number + 1)

    def test_total_is_recalculated_from_items(self):
        order = Order.objects.create(customer=self.customer)
        OrderItem.objects.create(
            order=order, product=self.product, quantity=3, unit_price=self.product.price
        )
        self.assertEqual(order.recalculate_total(), Decimal("31.50"))

    def test_cancellable_only_before_shipping(self):
        self.assertTrue(Order(status=Order.Status.PROCESSING).is_cancellable)
        self.assertFalse(Order(status=Order.Status.SHIPPED).is_cancellable)


class TicketModelTests(TestCase):
    def setUp(self):
        self.ali = Customer.objects.create(full_name="Ali", phone_number="+962791111111")
        self.sara = Customer.objects.create(full_name="Sara", phone_number="+962792222222")
        self.order = Order.objects.create(customer=self.ali)

    def test_reference_format(self):
        ticket = Ticket.objects.create(customer=self.ali, subject="x", description="y")
        self.assertEqual(ticket.reference, f"TKT-{ticket.pk:06d}")

    def test_order_must_belong_to_ticket_customer(self):
        ticket = Ticket(customer=self.sara, order=self.order, subject="x", description="y")
        with self.assertRaises(ValidationError):
            ticket.full_clean()

    def test_resolved_ticket_gets_timestamp(self):
        ticket = Ticket.objects.create(
            customer=self.ali, subject="x", description="y", status=Ticket.Status.RESOLVED
        )
        self.assertIsNotNone(ticket.resolved_at)


class SeedCommandTests(TestCase):
    def test_seed_is_idempotent_and_consistent(self):
        call_command("seed_demo_data", verbosity=0)
        call_command("seed_demo_data", verbosity=0)
        self.assertEqual(Customer.objects.count(), 5)
        self.assertEqual(Product.objects.count(), 8)
        self.assertEqual(Order.objects.count(), 10)
        self.assertEqual(Ticket.objects.count(), 3)
        order = Order.objects.get(order_number=1025)
        expected = sum(i.quantity * i.unit_price for i in order.items.all())
        self.assertEqual(order.total_amount, expected)
        self.assertTrue(Order.objects.get(order_number=1027).is_delayed)
        self.assertFalse(Order.objects.get(order_number=1026).is_delayed)