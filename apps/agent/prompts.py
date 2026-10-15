"""System prompt of the support agent.

Each version lives in its own readable file, apps/agent/prompt_templates/system_<version>.md, so versions can be
compared side by side. Placeholders: {store}, {customer_name}, {today}, {language}, {policy_rule}, {product_rule}
and (v3 only) {policy_hint}.

v1 = rules 1-11. v2 adds rules 12-13 after the manual tests showed the agent answering a policy question from an
earlier message (no tool call) and sounding like it approved a return. v3 (from the evaluation's failed cases) stops
listing "opening hours" as unknown, tells the agent to try the policy search before saying "I do not have that
information", and to escalate at once when the customer asks for a person. `manage.py evaluate_agent --compare`
measures the three versions.
"""
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.utils import timezone

TEMPLATE_DIR = Path(__file__).resolve().parent / "prompt_templates"
SUPPORTED_VERSIONS = ("v1", "v2", "v3")

POLICY_RULE = (
    "7. For questions about store policies (returns, refunds, shipping, payment, warranty, FAQ) call "
    "search_policies and answer ONLY from its results, mentioning the relevant conditions and "
    "exceptions. If the results do not cover the question, say so and offer a ticket."
)
NO_POLICY_RULE = (
    "7. You do not have a policy search tool. Do not guess store policies (returns, refunds, "
    "shipping, payment). Say you will pass the question to the support team and offer a ticket."
)
PRODUCT_RULE = (
    "8. For questions about products (do you sell X, price, availability) call search_products and "
    "answer ONLY from its results. If nothing matches, say the item was not found in our catalog and "
    "offer to pass the request to the team. Never say or imply that we sell something the tool did "
    "not return."
)
NO_PRODUCT_RULE = (
    "8. You have no product catalog tool. Do not say whether the store sells a product or what it "
    "costs; say you will pass the question to the team and offer a ticket."
)
POLICY_HINT = " Support hours, warranty, delivery times, fees and the other store policies are covered by the policy search tool."


@lru_cache(maxsize=None)
def load_template(version: str) -> str:
    return (TEMPLATE_DIR / f"system_{version}.md").read_text(encoding="utf-8")


def build_system_prompt(customer, tool_names: list[str]) -> str:
    version = getattr(settings, "AGENT_PROMPT_VERSION", "v3")
    if version not in SUPPORTED_VERSIONS:
        version = "v1"
    has_policies = "search_policies" in tool_names
    return load_template(version).format(
        store=getattr(settings, "STORE_NAME", "SmartSupport Store"),
        customer_name=customer.full_name,
        today=timezone.localdate().isoformat(),
        language="Arabic" if customer.preferred_language == "ar" else "English",
        policy_rule=POLICY_RULE if has_policies else NO_POLICY_RULE,
        product_rule=PRODUCT_RULE if "search_products" in tool_names else NO_PRODUCT_RULE,
        policy_hint=POLICY_HINT if has_policies else "",
    )
