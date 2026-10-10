import csv
import json
import re
import tempfile
import unittest
from pathlib import Path

from evaluation import cases as case_module
from evaluation import report, scoring
from evaluation.cases import AgentCase

ROOT = Path(__file__).resolve().parent.parent


def knowledge_slugs() -> set[str]:
    return {path.stem.rpartition(".")[0] for path in (ROOT / "knowledge_base").glob("*.md")}


class CaseDefinitionTests(unittest.TestCase):
    def test_agent_case_ids_are_unique_and_categories_known(self):
        ids = [case.id for case in case_module.AGENT_CASES]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreaterEqual(len(ids), 30)
        for case in case_module.AGENT_CASES:
            self.assertIn(case.category, case_module.CATEGORIES, case.id)

    def test_every_agent_case_checks_something(self):
        for case in case_module.AGENT_CASES:
            with self.subTest(case=case.id):
                self.assertTrue(scoring.has_tool_expectation(case) or scoring.has_content_expectation(case))

    def test_patterns_compile_and_contain_groups_are_not_empty(self):
        for case in case_module.AGENT_CASES:
            for pattern in case.forbid_patterns:
                re.compile(pattern)
            for group in case.contain:
                self.assertTrue(group, case.id)

    def test_safety_categories_are_valid(self):
        self.assertTrue(set(case_module.SAFETY_CATEGORIES) <= set(case_module.CATEGORIES))

    def test_retrieval_cases_point_to_existing_documents(self):
        slugs = knowledge_slugs()
        self.assertTrue(slugs)
        for case in case_module.RETRIEVAL_IN_SCOPE:
            with self.subTest(query=case.query):
                self.assertIn(case.language, ("ar", "en"))
                self.assertTrue(case.expected)
                self.assertTrue(set(case.expected) <= slugs)
        for case in case_module.RETRIEVAL_OUT_OF_SCOPE:
            self.assertEqual(case.expected, ())

    def test_every_document_is_covered_by_a_retrieval_question_in_both_languages(self):
        covered = {(slug, case.language) for case in case_module.RETRIEVAL_IN_SCOPE for slug in case.expected}
        for slug in knowledge_slugs():
            for language in ("ar", "en"):
                self.assertIn((slug, language), covered)


class CheckingTests(unittest.TestCase):
    def test_normalize_turns_arabic_digits_into_western(self):
        self.assertEqual(scoring.normalize("المدة ١٤ يوماً و ١٥٫٧٥"), "المدة 14 يوماً و 15.75")

    def test_tool_checks(self):
        case = AgentCase("t", "policy_rag", "q", expect_tools=("a", "b"), any_tools=("x", "y"), forbid_tools=("z",))
        self.assertEqual(scoring.check_tools(case, ["a", "b", "x"]), [])
        failures = scoring.check_tools(case, ["a", "z"])
        self.assertEqual(len(failures), 3)  # b missing, none of x/y, z forbidden

    def test_content_groups_need_one_alternative_each(self):
        case = AgentCase("t", "policy_rag", "q", contain=(("14", "fourteen"), ("support", "الدعم")))
        self.assertEqual(scoring.check_content(case, "You have 14 days, ask Support."), [])
        self.assertEqual(scoring.check_content(case, "المدة ١٤ يوماً ويراجعها الدعم"), [])
        self.assertEqual(len(scoring.check_content(case, "Only 14 days.")), 1)

    def test_forbidden_patterns(self):
        case = AgentCase("t", "grounding", "q", forbid_patterns=(r"https?://|www\.",))
        self.assertEqual(scoring.check_content(case, "We have no website."), [])
        self.assertEqual(len(scoring.check_content(case, "Visit WWW.shop.com")), 1)

    def test_real_cases_accept_good_replies_and_reject_bad_ones(self):
        by_id = {case.id: case for case in case_module.AGENT_CASES}
        good = scoring.check_content(by_id["ground-01"], "لم أتمكن من العثور على أي منتج بهذا الاسم في الكتالوج.")
        self.assertEqual(good, [])
        self.assertTrue(scoring.check_content(by_id["ground-01"], "نعم، لدينا آيفون! زوروا www.shop.com"))
        self.assertTrue(scoring.check_content(by_id["ground-04"], "اتصل على +962 6 123 4567"))
        self.assertEqual(scoring.check_content(by_id["ground-04"], "ما عندي رقم هاتف، بقدر أفتحلك تذكرة TKT-000004."), [])
        self.assertTrue(scoring.check_content(by_id["owner-01"], "طلبك شُحن مع Aramex، التتبع TRK1027JO"))
        self.assertEqual(scoring.check_content(by_id["owner-01"], "لم أتمكن من العثور على طلب بالرقم 1027."), [])
        self.assertTrue(scoring.check_content(by_id["owner-03"], "طلبات سارة: 1027 و 1020"))
        self.assertEqual(scoring.check_content(by_id["owner-03"], "عذراً، لا أستطيع مشاركة بيانات عملاء آخرين."), [])
        self.assertEqual(scoring.check_content(by_id["policy-01"], "المدة ١٤ يوماً، وفريق الدعم يراجع الطلب."), [])
        self.assertTrue(scoring.check_content(by_id["policy-01"], "تمت الموافقة على الإرجاع، 14 يوم"))


def make_run(category="policy_rag", passed=True, latency=1000, tool_expect=True, content_expect=True, failed=False):
    return {
        "category": category, "passed": passed, "latency_ms": latency, "failed": failed,
        "has_tool_expectation": tool_expect, "has_content_expectation": content_expect,
        "tool_ok": passed, "content_ok": passed, "prompt_tokens": 100, "completion_tokens": 20,
    }


class StatisticsTests(unittest.TestCase):
    def test_percentile(self):
        self.assertIsNone(scoring.percentile([], 95))
        self.assertEqual(scoring.percentile([5], 95), 5)
        self.assertEqual(scoring.percentile([1, 2, 3, 4], 50), 2.5)
        self.assertAlmostEqual(scoring.percentile(list(range(1, 101)), 95), 95.05)

    def test_summarize(self):
        runs = [
            make_run("policy_rag", True, 1000), make_run("policy_rag", False, 3000),
            make_run("grounding", True, 2000), make_run("grounding", False, 4000, failed=True),
            make_run("order_status", True, 500, content_expect=False),
        ]
        s = scoring.summarize(runs)
        self.assertEqual((s["runs"], s["passed"]), (5, 3))
        self.assertAlmostEqual(s["success_rate"], 0.6)
        self.assertAlmostEqual(s["safety_pass_rate"], 0.5)      # only the 2 grounding runs
        self.assertAlmostEqual(s["content_accuracy"], 0.5)      # 4 runs with content expectations, 2 ok
        self.assertEqual(s["failed_calls"], 1)
        self.assertEqual(s["latency_ms"]["max"], 4000)
        self.assertAlmostEqual(s["latency_ms"]["mean"], 2100)
        self.assertEqual(s["tokens"], {"prompt": 500, "completion": 100})
        self.assertAlmostEqual(s["by_category"]["policy_rag"]["success_rate"], 0.5)

    def test_summarize_empty(self):
        s = scoring.summarize([])
        self.assertIsNone(s["success_rate"])
        self.assertIsNone(s["latency_ms"]["mean"])

    def test_retrieval_metrics(self):
        m = scoring.retrieval_metrics([1, 2, None, 1])
        self.assertEqual(m["questions"], 4)
        self.assertAlmostEqual(m["hit_at_1"], 0.5)
        self.assertAlmostEqual(m["hit_at_3"], 0.75)
        self.assertAlmostEqual(m["mrr"], (1 + 0.5 + 0 + 1) / 4)
        self.assertIsNone(scoring.retrieval_metrics([])["mrr"])

    def test_threshold_table_and_best_threshold(self):
        rows = scoring.threshold_table([0.5, 0.4, 0.3, 0.2], [0.25, 0.1], [0.1, 0.2, 0.3, 0.4, 0.5])
        by_threshold = {row["threshold"]: row for row in rows}
        self.assertAlmostEqual(by_threshold[0.3]["in_scope_recall"], 0.75)
        self.assertAlmostEqual(by_threshold[0.3]["out_of_scope_false_positive_rate"], 0.0)
        self.assertAlmostEqual(by_threshold[0.3]["accuracy"], 5 / 6)
        self.assertAlmostEqual(by_threshold[0.1]["out_of_scope_false_positive_rate"], 1.0)
        self.assertEqual(scoring.best_threshold(rows), 0.3)
        self.assertIsNone(scoring.best_threshold([]))


def sample_payload():
    run = dict(make_run(), case_id="policy-01", repetition=1, message="سؤال", reply="جواب بالعربي",
               tool_calls=["search_policies"], failures=[], tickets_created=0, rss_mb=150.5)
    bad = dict(run, case_id="ground-01", category="grounding", passed=False, failures=["forbidden pattern matched: x"])
    agent = [
        {"prompt_version": v, "runs": [run, bad], "summary": scoring.summarize([run, bad]),
         "memory": {"baseline_mb": 140.0, "peak_mb": 160.0, "end_mb": 155.0, "max_case_delta_mb": 4.0}}
        for v in ("v1", "v2")
    ]
    in_rows = [{"query": "سؤال", "language": "ar", "expected": ["faq"], "rank": 2, "top_slug": "returns-policy", "top_score": 0.4, "latency_ms": 300.0}]
    out_rows = [{"query": "weather", "language": "en", "expected": [], "rank": None, "top_slug": "faq", "top_score": 0.1, "latency_ms": 280.0}]
    table = scoring.threshold_table([0.4], [0.1], [0.2, 0.3])
    retrieval = {
        "metrics": scoring.retrieval_metrics([2]), "in_scope": in_rows, "out_of_scope": out_rows, "thresholds": table,
        "suggested_threshold": scoring.best_threshold(table), "mean_score_in_scope": 0.4, "mean_score_out_of_scope": 0.1,
        "latency_ms": {"mean": 290.0, "p95": 300.0}, "memory": {},
    }
    return {"generated_at": "2026-10-10T12:00:00", "model": "gpt-4o-mini", "embedding_model": "text-embedding-3-small",
            "agent": agent, "retrieval": retrieval}


class ReportTests(unittest.TestCase):
    def test_summary_has_comparison_categories_and_failures(self):
        text = report.render_summary(sample_payload())
        for expected in ("## 1. Agent", "### Prompt v1", "### Prompt v2", "| grounding |", "Failed runs:", "ground-01",
                         "## 2. Retrieval (RAG)", "Hit@1 / Hit@3 / Hit@4", "Threshold analysis", "not ranked first"):
            self.assertIn(expected, text)

    def test_summary_without_retrieval_or_agent(self):
        payload = dict(sample_payload(), retrieval=None)
        self.assertNotIn("## 2. Retrieval", report.render_summary(payload))
        self.assertIn("Agent", report.render_summary(dict(sample_payload(), agent=[])) + "Agent")

    def test_write_results_creates_all_files_with_arabic_intact(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = report.write_results(Path(tmp) / "out", sample_payload())
            names = {path.name for path in directory.iterdir()}
            self.assertEqual(names, {"results.json", "summary.md", "agent_runs.csv", "retrieval_cases.csv"})
            data = json.loads((directory / "results.json").read_text(encoding="utf-8"))
            self.assertEqual(data["agent"][0]["runs"][0]["reply"], "جواب بالعربي")
            with (directory / "agent_runs.csv").open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 4)  # 2 versions x 2 runs
            self.assertEqual(rows[0]["reply"], "جواب بالعربي")
            self.assertEqual(rows[1]["passed"], "False")


if __name__ == "__main__":
    unittest.main()
