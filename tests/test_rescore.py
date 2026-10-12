"""Re-scoring and the corrected checks, using real replies from the first hold-out run (2026-10-11)."""
import unittest

from evaluation import scoring
from evaluation.cases import AGENT_CASES, HOLDOUT_CASES
from evaluation.rescore import rescore_payload

BY_ID = {case.id: case for case in AGENT_CASES + HOLDOUT_CASES}

AQABA = "مدة التوصيل إلى مدينة العقبة تتراوح من 2 إلى 4 أيام عمل. إذا كان لديك أي استفسار آخر، أنا هنا للمساعدة!"
TRANSLATION_REDIRECT = "I'm here to assist you with your orders and inquiries related to the SmartSupport Store. If you have any questions about our products or services, feel free to ask!"
ESCALATED_V3 = "تم تصعيد طلبك إلى أحد وكلاء الدعم البشري. سيتواصل معك أحدهم قريبًا."
ASKS_NUMBER_V1 = "يمكنني تصعيد حالتك إلى موظف دعم بشري. هل لديك رقم تذكرة أو رقم طلب مرتبط بالمشكلة؟"


class CorrectedChecksTests(unittest.TestCase):
    def test_arabic_plural_days_is_accepted(self):
        self.assertEqual(scoring.check_content(BY_ID["h-policy-02"], AQABA), [])
        self.assertEqual(scoring.check_content(BY_ID["policy-04"], AQABA), [])

    def test_polite_redirect_counts_as_declining_but_answering_does_not(self):
        case = BY_ID["h-scope-01"]
        self.assertEqual(scoring.check_content(case, TRANSLATION_REDIRECT), [])
        self.assertTrue(scoring.check_content(case, "Bonjour! I'm here to help."))    # complied with the request
        self.assertTrue(scoring.check_content(case, "In French it is a different thing."))  # neither declined nor redirected

    def test_the_redirect_wording_was_not_added_to_the_other_scope_checks(self):
        self.assertTrue(scoring.check_content(BY_ID["scope-02"], "رئيس الوزراء شخص مهم. أنا هنا لمساعدتك."))

    def test_human_agents_wording_is_accepted_but_a_missing_tool_call_still_fails(self):
        case = BY_ID["h-escalate-01"]
        self.assertEqual(scoring.check_content(case, ESCALATED_V3), [])
        self.assertEqual(scoring.check_content(BY_ID["escalate-01"], ESCALATED_V3), [])
        self.assertTrue(scoring.check_tools(case, []))          # v1 only offered to escalate and asked a question
        self.assertEqual(scoring.check_content(case, ASKS_NUMBER_V1), [])


def run(case_id, reply, tools=(), repetition=1, passed=False, failed=False):
    case = BY_ID[case_id]
    return {
        "case_id": case_id, "category": case.category, "repetition": repetition, "message": case.message,
        "reply": reply, "tool_calls": list(tools), "latency_ms": 2000, "prompt_tokens": 100, "completion_tokens": 20,
        "failed": failed, "has_tool_expectation": True, "has_content_expectation": True,
        "tool_ok": True, "content_ok": passed, "passed": passed, "failures": [] if passed else ["old failure"],
        "tickets_created": 0, "rss_mb": 120.0, "tool_failures_placeholder": None,
    }


def sample_payload():
    def block(version, escalate_reply, escalate_tools):
        runs = []
        for rep in (1, 2, 3):
            runs.append(run("h-policy-02", AQABA, ["search_policies"], rep))
            runs.append(run("h-scope-01", TRANSLATION_REDIRECT, [], rep))
        runs.append(run("h-escalate-01", escalate_reply, escalate_tools, 1))
        runs.append(run("h-policy-01", "48 hours", ["search_policies"], 1, passed=True))
        return {"prompt_version": version, "runs": runs, "summary": scoring.summarize(runs), "memory": {}}

    return {
        "suite": "holdout",
        "agent": [
            block("v1", ASKS_NUMBER_V1, []),
            block("v2", ESCALATED_V3, ["escalate_to_human"]),
            block("v3", ESCALATED_V3, ["escalate_to_human"]),
        ],
        "retrieval": None,
    }


class RescoreTests(unittest.TestCase):
    def test_wrongly_failed_runs_are_fixed_and_real_failures_stay(self):
        payload = sample_payload()
        new, changed = rescore_payload(payload, HOLDOUT_CASES)

        # v1: 3 x h-policy-02 and 3 x h-scope-01 flip; h-escalate-01 stays failed (tool not called)
        v1 = new["agent"][0]
        self.assertEqual(sum(1 for item in changed if item["prompt_version"] == "v1"), 6)
        self.assertEqual([r["case_id"] for r in v1["runs"] if not r["passed"]], ["h-escalate-01"])
        self.assertIn("tool not called: escalate_to_human", v1["runs"][-2]["failures"])
        # v2 and v3: everything passes now
        for block in new["agent"][1:]:
            self.assertTrue(all(r["passed"] for r in block["runs"]), block["prompt_version"])
            self.assertEqual(block["summary"]["success_rate"], 1.0)
        self.assertEqual(len(changed), 6 + 7 + 7)
        self.assertTrue(all(item["now_passed"] and not item["was_passed"] for item in changed))

    def test_summaries_are_rebuilt(self):
        new, _ = rescore_payload(sample_payload(), HOLDOUT_CASES)
        self.assertAlmostEqual(new["agent"][0]["summary"]["success_rate"], 7 / 8)
        # 5 runs expect a tool (3 x h-policy-02, h-escalate-01, h-policy-01); only the escalation one failed
        self.assertAlmostEqual(new["agent"][0]["summary"]["tool_accuracy"], 4 / 5)

    def test_the_original_payload_is_not_modified(self):
        payload = sample_payload()
        rescore_payload(payload, HOLDOUT_CASES)
        self.assertFalse(payload["agent"][2]["runs"][0]["passed"])

    def test_unknown_case_id_is_an_error(self):
        payload = sample_payload()
        payload["agent"][0]["runs"][0]["case_id"] = "no-such-case"
        with self.assertRaises(KeyError):
            rescore_payload(payload, HOLDOUT_CASES)

    def test_error_fallback_runs_stay_failed(self):
        payload = sample_payload()
        payload["agent"][2]["runs"][0]["failed"] = True
        new, _ = rescore_payload(payload, HOLDOUT_CASES)
        self.assertFalse(new["agent"][2]["runs"][0]["passed"])


if __name__ == "__main__":
    unittest.main()
