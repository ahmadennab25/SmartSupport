from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.agent.prompts import build_system_prompt

TOOLS = ["search_policies", "search_products"]


class PromptVersionThreeTests(SimpleTestCase):
    customer = SimpleNamespace(full_name="Ali", preferred_language="ar")

    def prompt(self, version, tool_names=TOOLS):
        with self.settings(AGENT_PROMPT_VERSION=version):
            return build_system_prompt(self.customer, tool_names)

    def test_v1_and_v2_keep_their_evaluated_wording(self):
        v1, v2 = self.prompt("v1"), self.prompt("v2")
        self.assertIn("opening hours", v1)
        self.assertIn("opening hours", v2)
        self.assertNotIn("12. Store information can change", v1)
        self.assertIn("12. Store information can change", v2)
        self.assertNotIn("14. If the customer asks to speak", v2)

    def test_v3_adds_the_escalation_and_search_first_rules(self):
        v3 = self.prompt("v3")
        self.assertIn("12. Store information can change", v3)
        self.assertIn("14. If the customer asks to speak to a person", v3)
        self.assertIn("Do not ask the customer for a reason first", v3)
        self.assertIn("15. Before telling the customer that you do not have information", v3)

    def test_v3_no_longer_calls_support_hours_unknown(self):
        v3 = self.prompt("v3")
        self.assertNotIn("opening hours", v3)
        self.assertIn("Support hours, warranty, delivery times", v3)

    def test_policy_hint_only_when_the_policy_tool_exists(self):
        self.assertNotIn("Support hours, warranty, delivery times", self.prompt("v3", []))

    def test_grounding_rules_survive_in_every_version(self):
        for version in ("v1", "v2", "v3"):
            with self.subTest(version=version):
                prompt = self.prompt(version)
                for phrase in ("NOT a general-knowledge assistant", "Never mention a website", "Never guess"):
                    self.assertIn(phrase, prompt)
