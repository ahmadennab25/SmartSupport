import json
from types import SimpleNamespace as NS

from django.conf import settings
from django.test import TestCase

from apps.agent import tools
from apps.agent.agent import SupportAgent
from apps.customers.models import Customer
from apps.orders.models import Order
from apps.tickets.models import Ticket


def make_response(content=None, tool_calls=None, prompt_tokens=10, completion_tokens=5):
    message = NS(content=content, tool_calls=tool_calls)
    return NS(
        choices=[NS(message=message)],
        usage=NS(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


def tool_call(call_id, name, arguments):
    return NS(id=call_id, type="function", function=NS(name=name, arguments=json.dumps(arguments)))


class FakeClient:
    """Stands in for the OpenAI client and returns scripted responses."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.requests = []
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kwargs):
        kwargs["messages"] = list(kwargs["messages"])
        self.requests.append(kwargs)
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class AgentTestBase(TestCase):
    def setUp(self):
        self.ali = Customer.objects.create(full_name="Ali", phone_number="+962791111111")
        self.sara = Customer.objects.create(full_name="Sara", phone_number="+962792222222")
        self.ali_order = Order.objects.create(customer=self.ali, order_number=1025, status=Order.Status.SHIPPED)
        self.sara_order = Order.objects.create(customer=self.sara, order_number=1026)


class ToolExecutionTests(AgentTestBase):
    def test_unknown_tool(self):
        self.assertIn("error", tools.execute_tool("drop_database", "{}", self.ali))

    def test_invalid_json(self):
        self.assertIn("error", tools.execute_tool("lookup_order", "{not json", self.ali))

    def test_model_cannot_pass_a_customer_id(self):
        result = tools.execute_tool(
            "lookup_order", json.dumps({"order_number": "1026", "customer_id": self.sara.pk}), self.ali
        )
        self.assertIn("error", result)

    def test_order_number_given_as_string_or_int(self):
        for value in ("1025", 1025, "#1025"):
            with self.subTest(value=value):
                result = tools.execute_tool("lookup_order", json.dumps({"order_number": value}), self.ali)
                self.assertTrue(result["found"])
                self.assertEqual(result["order"]["order_number"], 1025)

    def test_other_customers_order_is_not_found(self):
        result = tools.execute_tool("lookup_order", json.dumps({"order_number": "1026"}), self.ali)
        self.assertFalse(result["found"])

    def test_create_ticket_tool_and_duplicate(self):
        args = json.dumps(
            {"subject": "Late", "description": "Not arrived", "category": "delivery_delay", "order_number": "1025"}
        )
        first = tools.execute_tool("create_support_ticket", args, self.ali)
        second = tools.execute_tool("create_support_ticket", args, self.ali)
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(Ticket.objects.count(), 1)

    def test_ticket_tool_errors_are_returned_not_raised(self):
        args = json.dumps({"subject": "x", "description": "y", "category": "other", "order_number": "1026"})
        result = tools.execute_tool("create_support_ticket", args, self.ali)
        self.assertIn("error", result)

    def test_get_ticket_status_without_reference_lists_open_tickets(self):
        tools.execute_tool(
            "create_support_ticket",
            json.dumps({"subject": "Q", "description": "d", "category": "complaint"}),
            self.ali,
        )
        result = tools.execute_tool("get_ticket_status", "{}", self.ali)
        self.assertEqual(len(result["open_tickets"]), 1)

    def test_escalate_tool(self):
        result = tools.execute_tool("escalate_to_human", json.dumps({"reason": "Wants a person"}), self.ali)
        self.assertTrue(result["escalated"])
        self.assertTrue(Ticket.objects.get().escalated_to_human)


class SupportAgentTests(AgentTestBase):
    def test_tool_call_then_final_answer(self):
        client = FakeClient(
            [
                make_response(tool_calls=[tool_call("c1", "lookup_order", {"order_number": "1025"})]),
                make_response(content="Your order is shipped."),
            ]
        )
        result = SupportAgent(client=client).run(self.ali, "Where is order 1025?", history=[])

        self.assertEqual(result.reply, "Your order is shipped.")
        self.assertEqual(result.tool_calls, ["lookup_order"])
        self.assertEqual(result.prompt_tokens, 20)
        self.assertEqual(result.completion_tokens, 10)
        self.assertFalse(result.failed)
        self.assertEqual(client.requests[0]["messages"][0]["role"], "system")

        tool_message = client.requests[1]["messages"][-1]
        self.assertEqual(tool_message["role"], "tool")
        self.assertEqual(tool_message["tool_call_id"], "c1")
        payload = json.loads(tool_message["content"])
        self.assertTrue(payload["found"])

    def test_history_is_sent_before_the_new_message(self):
        client = FakeClient([make_response(content="ok")])
        history = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
        SupportAgent(client=client).run(self.ali, "new question", history=history)
        sent = client.requests[0]["messages"]
        self.assertEqual([m["role"] for m in sent], ["system", "user", "assistant", "user"])
        self.assertEqual(sent[-1]["content"], "new question")

    def test_agent_cannot_read_another_customers_order(self):
        client = FakeClient(
            [
                make_response(tool_calls=[tool_call("c1", "lookup_order", {"order_number": "1026"})]),
                make_response(content="I could not find that order."),
            ]
        )
        SupportAgent(client=client).run(self.ali, "order 1026?", history=[])
        payload = json.loads(client.requests[1]["messages"][-1]["content"])
        self.assertFalse(payload["found"])

    def test_llm_failure_returns_default_message(self):
        client = FakeClient([RuntimeError("boom")])
        result = SupportAgent(client=client).run(self.ali, "hi", history=[])
        self.assertTrue(result.failed)
        self.assertEqual(result.reply, settings.OPENAI_DEFAULT_ERROR_MESSAGE)

    def test_tool_loop_is_capped(self):
        looping = [
            make_response(tool_calls=[tool_call(f"c{i}", "get_ticket_status", {})]) for i in range(5)
        ]
        client = FakeClient(looping)
        result = SupportAgent(client=client, max_rounds=2).run(self.ali, "hi", history=[])
        self.assertTrue(result.failed)
        self.assertEqual(len(client.requests), 2)
