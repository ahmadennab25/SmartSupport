"""Tests for the fixes made after the instructor's code review."""
from types import SimpleNamespace
from unittest import mock

from django.db import IntegrityError
from django.test import SimpleTestCase, TestCase

from apps.agent import prompts, tools
from apps.customers.models import Customer
from apps.orders.models import Order
from config import settings as project_settings


class TwilioValidationDefaultTests(SimpleTestCase):
    """The webhook must not accept unsigned requests unless a developer switches validation off on purpose."""

    check = staticmethod(project_settings.twilio_validation_enabled)

    def test_production_always_validates(self):
        self.assertTrue(self.check(False, None))
        self.assertTrue(self.check(False, "False"))
        self.assertTrue(self.check(False, "0"))

    def test_development_validates_by_default(self):
        self.assertTrue(self.check(True, None))
        self.assertTrue(self.check(True, "True"))
        self.assertTrue(self.check(True, "yes"))

    def test_development_can_switch_it_off_explicitly(self):
        self.assertFalse(self.check(True, "False"))
        self.assertFalse(self.check(True, " false "))
        self.assertFalse(self.check(True, ""))


class OrderNumberCollisionTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(full_name="Ali", phone_number="+962791111111")

    def test_numbers_are_sequential(self):
        first = Order.objects.create(customer=self.customer)
        second = Order.objects.create(customer=self.customer)
        self.assertEqual(second.order_number, first.order_number + 1)

    def test_a_collision_is_retried_with_a_fresh_number(self):
        first = Order.objects.create(customer=self.customer)
        stale = [first.order_number, first.order_number + 1]   # first guess collides, second is free
        with mock.patch.object(Order, "_next_order_number", side_effect=stale) as guess:
            second = Order.objects.create(customer=self.customer)
        self.assertEqual(second.order_number, first.order_number + 1)
        self.assertEqual(guess.call_count, 2)
        self.assertEqual(Order.objects.count(), 2)

    def test_endless_collisions_give_up_with_the_database_error(self):
        first = Order.objects.create(customer=self.customer)
        with mock.patch.object(Order, "_next_order_number", return_value=first.order_number) as guess:
            with self.assertRaises(IntegrityError):
                Order.objects.create(customer=self.customer)
        self.assertEqual(guess.call_count, Order.NUMBER_RETRIES)
        self.assertEqual(Order.objects.count(), 1)

    def test_an_explicit_number_is_kept(self):
        order = Order.objects.create(customer=self.customer, order_number=4242)
        self.assertEqual(order.order_number, 4242)


class PromptTemplateTests(SimpleTestCase):
    customer = SimpleNamespace(full_name="Ali {x}", preferred_language="en")

    def build(self, version, tool_names=("search_policies", "search_products")):
        with self.settings(AGENT_PROMPT_VERSION=version, STORE_NAME="Acme Shop"):
            return prompts.build_system_prompt(self.customer, list(tool_names))

    def test_every_version_has_its_own_template_file(self):
        for version in prompts.SUPPORTED_VERSIONS:
            self.assertTrue((prompts.TEMPLATE_DIR / f"system_{version}.md").is_file(), version)

    def test_placeholders_are_all_filled_and_names_with_braces_survive(self):
        for version in prompts.SUPPORTED_VERSIONS:
            with self.subTest(version=version):
                text = self.build(version)
                self.assertIn("Acme Shop", text)
                self.assertIn("Ali {x}", text)
                self.assertIn("use English.", text)
                self.assertNotIn("{store}", text)
                self.assertEqual(text.replace("Ali {x}", "").count("{"), 0)

    def test_versions_differ_as_documented(self):
        v1, v2, v3 = (self.build(v) for v in prompts.SUPPORTED_VERSIONS)
        self.assertIn("opening hours", v1)
        self.assertNotIn("12. Store information can change", v1)
        self.assertIn("12. Store information can change", v2)
        self.assertNotIn("14. If the customer asks to speak", v2)
        self.assertIn("14. If the customer asks to speak", v3)
        self.assertNotIn("opening hours", v3)

    def test_unknown_version_falls_back_to_v1(self):
        self.assertEqual(self.build("v9"), self.build("v1"))

    def test_rules_depend_on_the_registered_tools(self):
        with_tools = self.build("v3")
        without = self.build("v3", tool_names=())
        self.assertIn("call search_policies and answer ONLY", with_tools)
        self.assertIn("You do not have a policy search tool", without)
        self.assertNotIn("Support hours, warranty, delivery times", without)


class ToolRegistrationTests(SimpleTestCase):
    def test_all_tools_are_registered_when_the_apps_start(self):
        expected = {
            "lookup_order", "list_my_orders", "create_support_ticket", "get_ticket_status", "add_ticket_update",
            "escalate_to_human", "search_products", "search_policies",
        }
        self.assertEqual(set(tools.get_tool_names()), expected)
