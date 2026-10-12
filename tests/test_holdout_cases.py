import re
import unittest

from evaluation import scoring
from evaluation.cases import AGENT_CASES, CATEGORIES, HOLDOUT_CASES

TOOLS = {
    "lookup_order", "list_my_orders", "create_support_ticket", "get_ticket_status",
    "add_ticket_update", "escalate_to_human", "search_policies", "search_products",
}
BY_ID = {case.id: case for case in HOLDOUT_CASES}


class HoldoutDefinitionTests(unittest.TestCase):
    def test_ids_are_unique_across_both_suites_and_categories_known(self):
        ids = [case.id for case in AGENT_CASES + HOLDOUT_CASES]
        self.assertEqual(len(ids), len(set(ids)))
        for case in HOLDOUT_CASES:
            self.assertIn(case.category, CATEGORIES, case.id)

    def test_holdout_does_not_reuse_a_tuning_question(self):
        tuning = {case.message.strip().lower() for case in AGENT_CASES}
        for case in HOLDOUT_CASES:
            self.assertNotIn(case.message.strip().lower(), tuning, case.id)

    def test_every_case_checks_something_with_valid_patterns_and_known_tools(self):
        self.assertGreaterEqual(len(HOLDOUT_CASES), 15)
        for case in HOLDOUT_CASES:
            with self.subTest(case=case.id):
                self.assertTrue(scoring.has_tool_expectation(case) or scoring.has_content_expectation(case))
                self.assertTrue(set(case.expect_tools + case.any_tools + case.forbid_tools) <= TOOLS)
                for pattern in case.forbid_patterns:
                    re.compile(pattern)

    def test_scoring_on_sample_replies(self):
        self.assertEqual(scoring.check_content(BY_ID["h-policy-01"], "لازم تبلغ خلال ٤٨ ساعة".replace("٤٨", "48")), [])
        self.assertTrue(scoring.check_content(BY_ID["h-ground-01"], "عندنا خصم 20% هالاسبوع"))
        self.assertEqual(scoring.check_content(BY_ID["h-ground-01"], "عذراً، ما عندي معلومات عن العروض."), [])
        self.assertTrue(scoring.check_content(BY_ID["h-scope-01"], "Bonjour!"))
        self.assertTrue(scoring.check_content(BY_ID["h-order-02"], "الطلب شُحن، التتبع TRK1020JO"))
        self.assertEqual(scoring.check_content(BY_ID["h-order-02"], "لم أتمكن من العثور على طلب بالرقم 1020."), [])


if __name__ == "__main__":
    unittest.main()
