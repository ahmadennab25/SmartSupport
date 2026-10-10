"""Fill the database with realistic demo data (idempotent: safe to run many times)."""
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.customers.models import Customer, phone_validator
from apps.orders.models import Order, OrderItem, Product
from apps.tickets.models import Ticket, TicketMessage

DEFAULT_DEMO_PHONE = "+962790000001"

PRODUCTS = [
    ("SKU-1001", "Wireless Earbuds Pro", "سماعات لاسلكية برو", "Electronics", "39.90", 120),
    ("SKU-1002", "Smart Watch Series X", "ساعة ذكية سيريس إكس", "Electronics", "89.00", 45),
    ("SKU-1003", "USB-C Fast Charger", "شاحن سريع USB-C", "Accessories", "19.50", 300),
    ("SKU-1004", "Clear Phone Case", "غطاء هاتف شفاف", "Accessories", "7.90", 500),
    ("SKU-1005", "Bluetooth Speaker Mini", "سماعة بلوتوث صغيرة", "Electronics", "24.99", 80),
    ("SKU-1006", "Laptop Backpack", "حقيبة ظهر للابتوب", "Bags", "34.00", 60),
    ("SKU-1007", "Mechanical Keyboard", "لوحة مفاتيح ميكانيكية", "Computers", "59.90", 35),
    ("SKU-1008", "Wireless Mouse", "ماوس لاسلكي", "Computers", "15.75", 150),
]

# index 0 is the "demo" customer: its phone is the number you chat from on WhatsApp.
CUSTOMERS = [
    ("Demo Customer", None, "ar", "Amman"),
    ("Sara Haddad", "+962790000002", "ar", "Amman"),
    ("John Miller", "+962790000003", "en", "Zarqa"),
    ("Omar Khalil", "+962790000004", "ar", "Aqaba"),
    ("Layla Nasser", "+962790000005", "ar", "Irbid"),
]

S, P, M = Order.Status, Order.PaymentStatus, Order.PaymentMethod

# number, customer idx, status, payment method, payment status,
# placed/shipped/delivered/eta (days from today), items (sku, qty)
ORDERS = [
    (1020, 1, S.DELIVERED, M.CARD, P.PAID, -25, -23, -20, None, [("SKU-1001", 1), ("SKU-1004", 2)]),
    (1021, 2, S.DELIVERED, M.CARD, P.PAID, -6, -5, -3, None, [("SKU-1008", 1)]),
    (1022, 2, S.CANCELLED, M.CARD, P.REFUNDED, -9, None, None, None, [("SKU-1006", 1)]),
    (1023, 3, S.PROCESSING, M.CARD, P.PAID, -1, None, None, 5, [("SKU-1007", 1), ("SKU-1008", 1)]),
    (1024, 3, S.PENDING, M.CASH_ON_DELIVERY, P.UNPAID, 0, None, None, 6, [("SKU-1005", 2)]),
    (1025, 0, S.SHIPPED, M.CARD, P.PAID, -3, -2, None, 2, [("SKU-1002", 1), ("SKU-1003", 1)]),
    (1026, 4, S.OUT_FOR_DELIVERY, M.WALLET, P.PAID, -4, -3, None, 0, [("SKU-1003", 2)]),
    (1027, 1, S.SHIPPED, M.CARD, P.PAID, -12, -10, None, -4, [("SKU-1006", 1), ("SKU-1004", 1)]),
    (1028, 0, S.DELIVERED, M.CARD, P.PAID, -12, -11, -10, None, [("SKU-1001", 1)]),
    (1029, 4, S.RETURNED, M.CARD, P.REFUND_PENDING, -30, -28, -25, None, [("SKU-1005", 1)]),
]


class Command(BaseCommand):
    help = "Create demo customers, products, orders and tickets for testing the agent."

    def add_arguments(self, parser):
        parser.add_argument(
            "--phone",
            default=DEFAULT_DEMO_PHONE,
            help="Your own WhatsApp number (E.164, e.g. +962791234567). It becomes the "
            "'Demo Customer' who owns orders 1025 and 1028.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        phone = options["phone"].strip().replace(" ", "")
        try:
            phone_validator(phone)
        except ValidationError as exc:
            raise CommandError(exc.messages[0]) from exc

        now = timezone.now()
        products = self._seed_products()
        customers = self._seed_customers(phone)
        self._seed_orders(now, products, customers)
        self._seed_tickets(now, customers)

        self.stdout.write(self.style.SUCCESS("Demo data is ready."))
        self.stdout.write(f"  Demo customer phone: {phone}  (orders 1025 and 1028)")
        self.stdout.write(
            f"  Customers={Customer.objects.count()} Products={Product.objects.count()} "
            f"Orders={Order.objects.count()} Tickets={Ticket.objects.count()}"
        )

    def _seed_products(self) -> dict[str, Product]:
        result = {}
        for sku, name, name_ar, category, price, stock in PRODUCTS:
            product, _ = Product.objects.update_or_create(
                sku=sku,
                defaults={
                    "name": name,
                    "name_ar": name_ar,
                    "category": category,
                    "price": Decimal(price),
                    "stock_quantity": stock,
                    "description": f"{name} - demo product.",
                },
            )
            result[sku] = product
        return result

    def _seed_customers(self, demo_phone: str) -> list[Customer]:
        result = []
        for name, phone, language, city in CUSTOMERS:
            customer, _ = Customer.objects.update_or_create(
                phone_number=phone or demo_phone,
                defaults={"full_name": name, "preferred_language": language, "city": city},
            )
            result.append(customer)
        return result

    def _seed_orders(self, now, products, customers) -> None:
        for number, cidx, status, method, pay, placed, shipped, delivered, eta, items in ORDERS:
            customer = customers[cidx]
            order, _ = Order.objects.update_or_create(
                order_number=number,
                defaults={
                    "customer": customer,
                    "status": status,
                    "payment_method": method,
                    "payment_status": pay,
                    "placed_at": now + timedelta(days=placed),
                    "shipped_at": now + timedelta(days=shipped) if shipped is not None else None,
                    "delivered_at": now + timedelta(days=delivered) if delivered is not None else None,
                    "estimated_delivery_date": timezone.localdate() + timedelta(days=eta)
                    if eta is not None
                    else None,
                    "carrier": "Aramex" if shipped is not None else "",
                    "tracking_number": f"TRK{number}JO" if shipped is not None else "",
                    "shipping_address": f"Building 12, Main St, {customer.city}, Jordan",
                },
            )
            for sku, qty in items:
                OrderItem.objects.update_or_create(
                    order=order,
                    product=products[sku],
                    defaults={"quantity": qty, "unit_price": products[sku].price},
                )
            order.recalculate_total()

    def _seed_tickets(self, now, customers) -> None:
        specs = [
            {
                "customer": customers[1],
                "order": Order.objects.get(order_number=1027),
                "category": Ticket.Category.DELIVERY_DELAY,
                "priority": Ticket.Priority.HIGH,
                "status": Ticket.Status.OPEN,
                "subject": "Order 1027 is delayed",
                "description": "My order was supposed to arrive 4 days ago and I have no update.",
                "created_by_ai": True,
                "messages": [
                    (TicketMessage.SenderType.CUSTOMER, "Where is my order 1027? It is late."),
                    (TicketMessage.SenderType.AI_AGENT, "I created a ticket for the support team."),
                ],
            },
            {
                "customer": customers[4],
                "order": Order.objects.get(order_number=1029),
                "category": Ticket.Category.REFUND,
                "priority": Ticket.Priority.URGENT,
                "status": Ticket.Status.ESCALATED,
                "subject": "Refund not received for returned order 1029",
                "description": "I returned the speaker 5 days ago and the refund is still pending.",
                "created_by_ai": True,
                "escalated_to_human": True,
                "escalation_reason": "Refund pending for more than 5 days; needs staff approval.",
                "messages": [
                    (TicketMessage.SenderType.CUSTOMER, "I still did not get my refund."),
                    (TicketMessage.SenderType.SYSTEM, "Escalated to a human agent."),
                ],
            },
            {
                "customer": customers[2],
                "order": None,
                "category": Ticket.Category.COMPLAINT,
                "priority": Ticket.Priority.MEDIUM,
                "status": Ticket.Status.RESOLVED,
                "subject": "Wrong colour received",
                "description": "I received a black case instead of a clear one.",
                "created_by_ai": False,
                "resolved_at": now - timedelta(days=2),
                "messages": [
                    (TicketMessage.SenderType.STAFF, "We sent a replacement. Sorry for the mix-up."),
                ],
            },
        ]
        for spec in specs:
            messages = spec.pop("messages")
            customer, subject = spec.pop("customer"), spec.pop("subject")
            ticket, created = Ticket.objects.get_or_create(
                customer=customer, subject=subject, defaults=spec
            )
            if created:
                for sender, body in messages:
                    TicketMessage.objects.create(ticket=ticket, sender_type=sender, body=body)

