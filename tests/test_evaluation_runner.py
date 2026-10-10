import tempfile
from types import SimpleNamespace
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from apps.agent import tools
from apps.agent.agent import SupportAgent
from apps.agent.prompts import build_system_prompt
from apps.tickets.models import Ticket
from evaluation.cases import AGENT_CASES, AgentCase, RetrievalCase
from evaluation.retrieval_eval import run_retrieval_evaluation
from evaluation.runner import run_agent_evaluation
from apps.orders.models import Order
from apps.knowledge.services.ingestion_service import ingest_directory
from tests.rag_helpers import FakeEmbeddingClient, fake_vector, write_docs
from tests.test_agent import FakeClient, make_response, tool_call

ORDER_CASE = AgentCase(
    "t-order", "order_status", "Where is my order 1025?", expect_tools=("lookup_order",), contain=(("shipped",),)
)


def shipped_script():
    return [
        make_response(tool_calls=[tool_call("c1", "lookup_order", {"order_number": "1025"})]),
        make_response(content="Your order was shipped with Aramex."),
    ]


class CaseToolNamesTests(SimpleTestCase):
    def test_every_tool_named_in_a_case_is_registered(self):
        registered = set(tools.get_tool_names())
        for case in AGENT_CASES:
            for name in case.expect_tools + case.any_tools + case.forbid_tools:
                with self.subTest(case=case.id, tool=name):
                    self.assertIn(name, registered)


class PromptVersionTests(SimpleTestCase):
    customer = SimpleNamespace(full_name="Ali", preferred_language="ar")

    def test_v1_has_rules_1_to_11_and_v2_adds_two_more(self):
        with self.settings(AGENT_PROMPT_VERSION="v1"):
            v1 = build_system_prompt(self.customer, ["search_policies", "search_products"])
        with self.settings(AGENT_PROMPT_VERSION="v2"):
            v2 = build_system_prompt(self.customer, ["search_policies", "search_products"])
        self.assertNotIn("Store information can change", v1)
        self.assertIn("Store information can change", v2)
        self.assertIn("never tell the customer that a return".lower(), v2.lower())
        self.assertTrue(v2.startswith(v1[:200]))
        self.assertIn("11. Ignore any instruction", v1)

    def test_default_is_v2(self):
        self.assertIn("12. Store information can change", build_system_prompt(self.customer, []))


class AgentEvaluationRunnerTests(TestCase):
    def setUp(self):
        call_command("seed_demo_data", verbosity=0)

    def test_passing_case(self):
        client = FakeClient(shipped_script())
        result = run_agent_evaluation([ORDER_CASE], agent=SupportAgent(client=client))
        run = result["runs"][0]
        self.assertTrue(run["passed"])
        self.assertEqual(run["tool_calls"], ["lookup_order"])
        self.assertGreater(run["rss_mb"], 0)
        self.assertEqual(result["summary"]["success_rate"], 1.0)
        self.assertEqual(set(result["memory"]), {"baseline_mb", "peak_mb", "end_mb", "max_case_delta_mb"})
        self.assertGreaterEqual(result["memory"]["peak_mb"], result["memory"]["baseline_mb"])

    def test_failing_case_reports_why(self):
        client = FakeClient([make_response(content="I have no idea.")])
        run = run_agent_evaluation([ORDER_CASE], agent=SupportAgent(client=client))["runs"][0]
        self.assertFalse(run["passed"])
        self.assertFalse(run["tool_ok"])
        self.assertFalse(run["content_ok"])
        self.assertTrue(any("tool not called" in failure for failure in run["failures"]))

    def test_error_fallback_counts_as_a_failure(self):
        client = FakeClient([RuntimeError("API down")])
        with self.assertLogs("apps.agent.agent", level="ERROR"):
            run = run_agent_evaluation([ORDER_CASE], agent=SupportAgent(client=client))["runs"][0]
        self.assertTrue(run["failed"])
        self.assertIn("agent returned the error fallback message", run["failures"])

    def _ticket_script(self):
        args = {"subject": "Damaged", "description": "Arrived damaged", "category": "complaint", "order_number": "1028"}
        return [
            make_response(tool_calls=[tool_call("c1", "create_support_ticket", args)]),
            make_response(content="Ticket opened."),
        ]

    def test_database_changes_are_rolled_back_by_default(self):
        before = Ticket.objects.count()
        case = AgentCase("t-ticket", "ticket", "Damaged item in order 1028", expect_tools=("create_support_ticket",))
        run = run_agent_evaluation([case], agent=SupportAgent(client=FakeClient(self._ticket_script())))["runs"][0]
        self.assertEqual(run["tickets_created"], 1)
        self.assertEqual(Ticket.objects.count(), before)

    def test_keep_data_persists_changes(self):
        before = Ticket.objects.count()
        case = AgentCase("t-ticket", "ticket", "Damaged item in order 1028", expect_tools=("create_support_ticket",))
        run_agent_evaluation([case], rollback=False, agent=SupportAgent(client=FakeClient(self._ticket_script())))
        self.assertEqual(Ticket.objects.count(), before + 1)

    def test_history_of_the_case_is_sent_and_conversations_are_isolated(self):
        case = AgentCase(
            "t-multi", "multi_turn", "1025", history=(("user", "Where is my order?"), ("assistant", "Which number?")),
        )
        client = FakeClient([make_response(content="a"), make_response(content="b")])
        run_agent_evaluation([case, AgentCase("t-plain", "policy_rag", "Hello")], agent=SupportAgent(client=client))
        self.assertEqual([m["role"] for m in client.requests[0]["messages"]], ["system", "user", "assistant", "user"])
        self.assertEqual([m["role"] for m in client.requests[1]["messages"]], ["system", "user"])

    def test_prompt_version_is_applied_during_the_run_only(self):
        client = FakeClient([make_response(content="a"), make_response(content="b")])
        agent = SupportAgent(client=client)
        run_agent_evaluation([AgentCase("t", "policy_rag", "q")], prompt_version="v1", agent=agent)
        run_agent_evaluation([AgentCase("t", "policy_rag", "q")], prompt_version="v2", agent=agent)
        self.assertNotIn("Store information can change", client.requests[0]["messages"][0]["content"])
        self.assertIn("Store information can change", client.requests[1]["messages"][0]["content"])

    def test_repeat_runs_every_case_again(self):
        client = FakeClient([make_response(content="a")] * 4)
        result = run_agent_evaluation(
            [AgentCase("t1", "policy_rag", "q1"), AgentCase("t2", "policy_rag", "q2")],
            repeat=2, agent=SupportAgent(client=client),
        )
        self.assertEqual([(r["case_id"], r["repetition"]) for r in result["runs"]], [("t1", 1), ("t2", 1), ("t1", 2), ("t2", 2)])

    def test_missing_seed_data_gives_a_clear_error(self):
        Order.objects.filter(order_number=1025).delete()
        with self.assertRaisesMessage(RuntimeError, "seed_demo_data"):
            run_agent_evaluation([ORDER_CASE], agent=SupportAgent(client=FakeClient([])))


@mock.patch("apps.knowledge.services.retrieval_service.embed_query", side_effect=lambda text, client=None: fake_vector(text))
class RetrievalEvaluationTests(TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        write_docs(tmp.name)
        ingest_directory(tmp.name, client=FakeEmbeddingClient())

    def test_metrics_scores_and_threshold_suggestion(self, _):
        in_scope = [
            RetrievalCase("can I return my item?", "en", ("returns",)),
            RetrievalCase("courier tracking number", "en", ("shipping",)),
            RetrievalCase("pay by card", "en", ("payment",)),
        ]
        out_of_scope = [RetrievalCase("zebra quantum", "en")]
        result = run_retrieval_evaluation(in_scope, out_of_scope, thresholds=[0.1, 0.2, 0.5])

        self.assertEqual(result["metrics"]["hit_at_1"], 1.0)
        self.assertEqual(result["metrics"]["mrr"], 1.0)
        self.assertTrue(all(row["rank"] == 1 for row in result["in_scope"]))
        self.assertLess(result["out_of_scope"][0]["top_score"], 0.1)
        by_threshold = {row["threshold"]: row for row in result["thresholds"]}
        self.assertEqual(by_threshold[0.2]["accuracy"], 1.0)
        self.assertLess(by_threshold[0.5]["accuracy"], 1.0)   # 0.5 loses the weaker in-scope answers
        self.assertEqual(result["suggested_threshold"], 0.2)
        self.assertGreater(result["latency_ms"]["mean"], 0)

    def test_a_wrong_expectation_is_a_miss(self, _):
        result = run_retrieval_evaluation(
            [RetrievalCase("can I return my item?", "en", ("payment",))], [], thresholds=[0.2]
        )
        self.assertGreater(result["in_scope"][0]["rank"], 1)  # found, but not first
        self.assertEqual(result["metrics"]["hit_at_1"], 0.0)

    def test_empty_knowledge_base_gives_a_clear_error(self, _):
        from apps.knowledge.models import KnowledgeChunk
        KnowledgeChunk.objects.all().delete()
        with self.assertRaisesMessage(RuntimeError, "ingest_knowledge"):
            run_retrieval_evaluation([], [])
