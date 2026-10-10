from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings
from twilio.request_validator import RequestValidator

from apps.agent.agent import AgentResult
from apps.chat.models import ChatMessage
from apps.whatsapp.services.twilio_service import build_twiml, split_message

RUN = "apps.agent.agent.SupportAgent.run"
URL = "/api/whatsapp/webhook/"
FORM = {"From": "whatsapp:+962791112233", "Body": "where is my order?", "ProfileName": "Ali"}


@override_settings(TWILIO_VALIDATE_REQUESTS=False)
class WebhookTests(TestCase):
    @mock.patch(RUN)
    def test_reply_is_returned_as_twiml_and_logged(self, run):
        run.return_value = AgentResult(reply="Your order is on the way.")
        response = self.client.post(URL, FORM)

        self.assertEqual(response.status_code, 200)
        self.assertIn("xml", response["Content-Type"])
        self.assertIn("Your order is on the way.", response.content.decode())
        self.assertEqual(ChatMessage.objects.filter(channel="whatsapp").count(), 2)

    @mock.patch(RUN)
    def test_media_only_message_gets_text_only_notice(self, run):
        response = self.client.post(URL, {"From": "whatsapp:+962791112233", "Body": "", "NumMedia": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("text", response.content.decode().lower())
        run.assert_not_called()

    def test_missing_sender_is_a_bad_request(self):
        self.assertEqual(self.client.post(URL, {"Body": "hi"}).status_code, 400)

    def test_invalid_sender_is_a_bad_request(self):
        self.assertEqual(self.client.post(URL, {"From": "whatsapp:abc", "Body": "hi"}).status_code, 400)

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(URL).status_code, 405)

    @mock.patch(RUN, side_effect=RuntimeError("boom"))
    def test_unexpected_failure_still_replies(self, run):
        # SupportAgent.run raising is not expected (it handles its own errors), but the
        # webhook must still answer Twilio instead of returning a 500.
        response = self.client.post(URL, FORM)
        self.assertEqual(response.status_code, 200)


@override_settings(TWILIO_VALIDATE_REQUESTS=True, TWILIO_AUTH_TOKEN="secret-token", TWILIO_WEBHOOK_URL="")
class SignatureTests(TestCase):
    full_url = "http://testserver" + URL

    @mock.patch(RUN)
    def test_valid_signature_is_accepted(self, run):
        run.return_value = AgentResult(reply="ok")
        signature = RequestValidator("secret-token").compute_signature(self.full_url, FORM)
        response = self.client.post(URL, FORM, HTTP_X_TWILIO_SIGNATURE=signature)
        self.assertEqual(response.status_code, 200)

    def test_invalid_signature_is_rejected(self):
        response = self.client.post(URL, FORM, HTTP_X_TWILIO_SIGNATURE="forged")
        self.assertEqual(response.status_code, 403)

    def test_missing_signature_is_rejected(self):
        self.assertEqual(self.client.post(URL, FORM).status_code, 403)

    @override_settings(TWILIO_AUTH_TOKEN="")
    def test_validation_without_token_fails_closed(self):
        self.assertEqual(self.client.post(URL, FORM, HTTP_X_TWILIO_SIGNATURE="x").status_code, 403)


class MessageSplittingTests(SimpleTestCase):
    def test_short_text_is_one_part(self):
        self.assertEqual(split_message("hello"), ["hello"])

    def test_empty_text_has_no_parts(self):
        self.assertEqual(split_message("   "), [])

    def test_long_text_is_split_within_limit(self):
        text = "\n".join(f"line {i} " + "x" * 80 for i in range(60))
        parts = split_message(text, limit=500)
        self.assertGreater(len(parts), 1)
        self.assertTrue(all(len(p) <= 500 for p in parts))
        self.assertEqual("".join(parts).replace("\n", ""), text.replace("\n", ""))

    def test_single_huge_line_is_cut(self):
        parts = split_message("y" * 1200, limit=500)
        self.assertEqual([len(p) for p in parts], [500, 500, 200])

    def test_twiml_contains_one_message_per_part(self):
        xml = build_twiml("a\n" * 1000)
        self.assertGreaterEqual(xml.count("<Message>"), 2)
