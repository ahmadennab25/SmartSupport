"""Real replies from the first evaluation run (2026-10-11), kept as regression tests for the scoring."""
import unittest

from evaluation import scoring
from evaluation.cases import AGENT_CASES

BY_ID = {case.id: case for case in AGENT_CASES}

DELIVERED_REPLY = """طلبك رقم 1028 تم توصيله.

- الحالة: تم التوصيل
- الناقل: أرامكس
- رقم التتبع: TRK1028JO"""
NO_HOURS_REPLY = "عذرًا، لا أملك معلومات عن ساعات عمل فريق الدعم. يمكنني مساعدتك في فتح تذكرة دعم إذا كنت بحاجة إلى مساعدة."
ASKS_REASON_REPLY = "Could you please let me know the reason you need to speak with a human agent?"


class FirstEvaluationRegressionTests(unittest.TestCase):
    def test_delivered_wording_with_tawseel_is_accepted(self):
        self.assertEqual(scoring.check_content(BY_ID["order-03"], DELIVERED_REPLY), [])

    def test_a_refusal_never_counts_as_answering_the_support_hours_question(self):
        case = BY_ID["policy-09"]
        self.assertTrue(scoring.check_tools(case, []))                    # search_policies was not called
        self.assertTrue(scoring.check_content(case, NO_HOURS_REPLY))      # and the reply has no hours
        self.assertEqual(scoring.check_content(case, "من 9:00 صباحاً حتى 5:00 مساءً"), [])
        self.assertEqual(scoring.check_content(case, "من ٩:٠٠ صباحاً حتى ٥:٠٠ مساءً"), [])

    def test_asking_for_a_reason_instead_of_escalating_fails_the_tool_check(self):
        case = BY_ID["escalate-02"]
        self.assertTrue(scoring.check_tools(case, []))
        self.assertEqual(scoring.check_tools(case, ["escalate_to_human"]), [])
        self.assertEqual(scoring.check_content(case, ASKS_REASON_REPLY), [])  # content is fine, the tool is what matters


if __name__ == "__main__":
    unittest.main()
