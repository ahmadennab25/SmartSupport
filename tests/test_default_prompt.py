from types import SimpleNamespace

from django.conf import settings
from django.test import SimpleTestCase

from apps.agent.prompts import build_system_prompt


class DefaultPromptVersionTests(SimpleTestCase):
    customer = SimpleNamespace(full_name="Ali", preferred_language="ar")

    def test_default_prompt_is_v3(self):
        prompt = build_system_prompt(self.customer, ["search_policies", "search_products"])
        self.assertIn("14. If the customer asks to speak to a person", prompt)
        self.assertIn("15. Before telling the customer that you do not have information", prompt)
        self.assertNotIn("opening hours", prompt)

    def test_settings_expose_the_version(self):
        self.assertEqual(getattr(settings, "AGENT_PROMPT_VERSION", "v3"), "v3")
