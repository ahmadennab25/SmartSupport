import json
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase

from apps.agent import tools
from apps.agent.agent import SupportAgent
from apps.agent.prompts import build_system_prompt
from apps.customers.models import Customer
from apps.orders.models import Product
from apps.orders.services import product_service
from tests.test_agent import FakeClient, make_response, tool_call


class TermExtractionTests(SimpleTestCase):
    def test_stop_words_short_words_and_duplicates_are_dropped(self):
        self.assertEqual(product_service.extract_terms("do you sell iPhone iphone?"), ["iphone"])
        self.assertEqual(product_service.extract_terms("هل عندكم سماعات بلوتوث"), ["سماعات", "بلوتوث"])
        self.assertEqual(product_service.extract_terms("is it ok"), [])
        self.assertEqual(product_service.extract_terms(""), [])

    def test_score_counts_matching_terms(self):
        self.assertEqual(product_service.score_text(["wireless", "mouse"], "Wireless Mouse"), 2)
        self.assertEqual(product_service.score_text(["wireless", "keyboard"], "Wireless Mouse"), 1)

    def test_availability_labels(self):
        self.assertEqual(product_service.availability_label(0), "out_of_stock")
        self.assertEqual(product_service.availability_label(3), "low_stock")
        self.assertEqual(product_service.availability_label(50), "in_stock")


class ProductSearchTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(full_name="Ali", phone_number="+962791111111")
        make = lambda sku, name, ar, cat, price, stock, active=True: Product.objects.create(
            sku=sku, name=name, name_ar=ar, category=cat, price=Decimal(price), stock_quantity=stock, is_active=active
        )
        self.mouse = make("SKU-1", "Wireless Mouse", "ماوس لاسلكي", "Computers", "15.75", 150)
        self.keyboard = make("SKU-2", "Mechanical Keyboard", "لوحة مفاتيح ميكانيكية", "Computers", "59.90", 3)
        self.earbuds = make("SKU-3", "Wireless Earbuds Pro", "سماعات لاسلكية برو", "Electronics", "39.90", 0)
        make("SKU-4", "Hidden Gadget", "جهاز مخفي", "Electronics", "9.00", 10, active=False)

    def test_finds_by_english_name_arabic_name_and_category(self):
        self.assertEqual(product_service.search_products("wireless mouse")[0], self.mouse)
        self.assertEqual(product_service.search_products("لوحة مفاتيح")[0], self.keyboard)
        self.assertEqual({p.sku for p in product_service.search_products("computers")}, {"SKU-1", "SKU-2"})

    def test_best_match_comes_first(self):
        results = product_service.search_products("wireless mouse")
        self.assertEqual(results[0], self.mouse)  # matches 2 terms; earbuds only 1
        self.assertIn(self.earbuds, results)

    def test_unknown_product_returns_nothing(self):
        self.assertEqual(product_service.search_products("iphone"), [])
        self.assertEqual(product_service.search_products("do you sell iPhone?"), [])

    def test_inactive_products_are_hidden(self):
        self.assertEqual(product_service.search_products("hidden gadget"), [])

    def test_limit(self):
        self.assertEqual(len(product_service.search_products("wireless computers", limit=2)), 2)

    def test_tool_found(self):
        result = tools.execute_tool("search_products", json.dumps({"query": "mouse"}), self.customer)
        self.assertTrue(result["found"])
        item = result["products"][0]
        self.assertEqual((item["name"], item["price"], item["currency"], item["availability"]),
                         ("Wireless Mouse", "15.75", "JOD", "in_stock"))

    def test_tool_not_found_tells_the_model_not_to_claim_it_sells_it(self):
        result = tools.execute_tool("search_products", json.dumps({"query": "iphone"}), self.customer)
        self.assertFalse(result["found"])
        self.assertIn("Do not say or imply", result["message"])

    def test_agent_receives_the_tool_and_its_result(self):
        client = FakeClient(
            [
                make_response(tool_calls=[tool_call("c1", "search_products", {"query": "iphone"})]),
                make_response(content="We do not have it in our catalog."),
            ]
        )
        result = SupportAgent(client=client).run(self.customer, "هل تبيعون ايفون؟", history=[])
        self.assertEqual(result.tool_calls, ["search_products"])
        self.assertIn("search_products", [t["function"]["name"] for t in client.requests[0]["tools"]])
        self.assertFalse(json.loads(client.requests[1]["messages"][-1]["content"])["found"])


class PromptGroundingTests(SimpleTestCase):
    customer = SimpleNamespace(full_name="Ali", preferred_language="ar")

    def test_prompt_forbids_inventing_store_facts(self):
        prompt = build_system_prompt(self.customer, ["search_products", "search_policies"])
        for phrase in ("NOT a general-knowledge assistant", "Never mention a website", "Never guess", "search_products", "search_policies"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, prompt)

    def test_prompt_without_tools_tells_the_model_not_to_answer_from_memory(self):
        prompt = build_system_prompt(self.customer, [])
        self.assertIn("You have no product catalog tool", prompt)
        self.assertIn("You do not have a policy search tool", prompt)
        self.assertNotIn("call search_products", prompt)

    def test_registered_tools_include_the_catalog_tool(self):
        self.assertIn("search_products", tools.get_tool_names())
