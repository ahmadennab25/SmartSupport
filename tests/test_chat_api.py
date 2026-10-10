from unittest import mock

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.agent.agent import AgentResult
from apps.chat.models import ChatMessage
from apps.customers.models import Customer

RUN = "apps.agent.agent.SupportAgent.run"


def agent_result(reply="مرحباً"):
    return AgentResult(
        reply=reply,
        tool_calls=["lookup_order"],
        latency_ms=120,
        prompt_tokens=100,
        completion_tokens=20,
        model="gpt-4o-mini",
    )


@override_settings(CHAT_API_KEY="test-key")
class ChatApiTests(TestCase):
    url = "/api/chat/"

    def setUp(self):
        self.api = APIClient()

    def post(self, data, key="test-key"):
        headers = {"HTTP_X_API_KEY": key} if key is not None else {}
        return self.api.post(self.url, data, format="json", **headers)

    def test_missing_key_is_rejected(self):
        self.assertEqual(self.post({"phone": "+962791112233", "message": "hi"}, key=None).status_code, 403)

    def test_wrong_key_is_rejected(self):
        self.assertEqual(self.post({"phone": "+962791112233", "message": "hi"}, key="nope").status_code, 403)

    @override_settings(CHAT_API_KEY="")
    def test_unconfigured_key_fails_closed(self):
        self.assertEqual(self.post({"phone": "+962791112233", "message": "hi"}, key="").status_code, 403)

    def test_invalid_phone(self):
        self.assertEqual(self.post({"phone": "0791112233", "message": "hi"}).status_code, 400)

    def test_empty_message(self):
        self.assertEqual(self.post({"phone": "+962791112233", "message": ""}).status_code, 400)

    @mock.patch(RUN)
    def test_success_creates_customer_and_logs_both_messages(self, run):
        run.return_value = agent_result()
        response = self.post({"phone": "+962791112233", "message": "وين طلبي؟", "display_name": "Ali"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["reply"], "مرحباً")
        self.assertEqual(body["tool_calls"], ["lookup_order"])
        self.assertEqual(Customer.objects.get(phone_number="+962791112233").full_name, "Ali")
        messages = list(ChatMessage.objects.order_by("id"))
        self.assertEqual([m.role for m in messages], ["user", "assistant"])
        self.assertEqual(messages[1].latency_ms, 120)
        self.assertEqual(messages[1].tool_calls, ["lookup_order"])

    @mock.patch(RUN)
    def test_history_is_passed_to_the_agent(self, run):
        run.return_value = agent_result("first")
        self.post({"phone": "+962791112233", "message": "one"})
        run.return_value = agent_result("second")
        self.post({"phone": "+962791112233", "message": "two"})

        history = run.call_args.args[2]
        self.assertEqual([m["content"] for m in history], ["one", "first"])

    @mock.patch(RUN)
    def test_inactive_customer_does_not_reach_the_agent(self, run):
        Customer.objects.create(full_name="Blocked", phone_number="+962791112233", is_active=False)
        response = self.post({"phone": "+962791112233", "message": "hi"})
        self.assertEqual(response.status_code, 200)
        run.assert_not_called()
