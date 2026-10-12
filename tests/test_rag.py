import json
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase, TestCase

from apps.agent import tools
from apps.agent.agent import SupportAgent
from apps.customers.models import Customer
from apps.knowledge.models import (
    EMBEDDING_DIMENSIONS,
    KnowledgeChunk,
    KnowledgeDocument,
)
from apps.knowledge.services import retrieval_service
from apps.knowledge.services.chunking import (
    build_chunk_text,
    chunk_markdown,
    parse_title,
)
from apps.knowledge.services.embedding_service import EmbeddingError, embed_texts
from apps.knowledge.services.ingestion_service import ingest_directory, parse_filename
from tests.rag_helpers import FakeEmbeddingClient, fake_vector, write_docs
from tests.test_agent import FakeClient, make_response, tool_call

EMBED_QUERY = "apps.knowledge.services.retrieval_service.embed_query"


def fake_embed_query(text, client=None):
    return fake_vector(text)


class ChunkingTests(SimpleTestCase):
    DOC = (
        "# Policy\n\nIntro line.\n\n## One\n- a\n- b\n\n## Two\nSecond section text.\n\nSecond paragraph.\n"
    )

    def test_title_is_parsed_and_not_chunked(self):
        self.assertEqual(parse_title(self.DOC), "Policy")
        self.assertFalse(any("# Policy" in c.text for c in chunk_markdown(self.DOC)))

    def test_chunks_never_cross_section_boundaries(self):
        chunks = chunk_markdown(self.DOC)
        self.assertEqual([c.section for c in chunks], ["", "One", "Two"])
        self.assertEqual(chunks[1].text, "- a\n- b")
        self.assertEqual(chunks[2].text, "Second section text.\n\nSecond paragraph.")

    def test_long_sections_are_split_within_the_limit(self):
        doc = "# T\n\n## S\n" + "\n\n".join(f"Paragraph {i} " + "word " * 30 for i in range(10))
        chunks = chunk_markdown(doc, max_chars=300)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(c.text) <= 300 for c in chunks))
        self.assertTrue(all(c.section == "S" for c in chunks))

    def test_single_huge_line_is_cut(self):
        chunks = chunk_markdown("# T\n\n## S\n" + "x" * 1000, max_chars=400)
        self.assertEqual([len(c.text) for c in chunks], [400, 400, 200])

    def test_chunk_text_carries_its_heading_context(self):
        self.assertEqual(build_chunk_text("Returns", "Window", "14 days"), "Returns — Window\n14 days")
        self.assertEqual(build_chunk_text("", "", "body"), "body")

    def test_real_knowledge_base_files_have_valid_names_and_content(self):
        folder = Path(__file__).resolve().parent.parent / "knowledge_base"
        files = sorted(folder.glob("*.md"))
        self.assertGreaterEqual(len(files), 10)
        for path in files:
            with self.subTest(file=path.name):
                self.assertIsNotNone(parse_filename(path))
                self.assertTrue(chunk_markdown(path.read_text(encoding="utf-8")))


class EmbeddingServiceTests(SimpleTestCase):
    def test_vectors_are_returned_in_input_order(self):
        client = FakeEmbeddingClient()
        vectors = embed_texts(["alpha beta", "gamma"], client)
        self.assertEqual(vectors, [fake_vector("alpha beta"), fake_vector("gamma")])

    def test_batches_are_used(self):
        client = FakeEmbeddingClient()
        with self.settings(EMBEDDING_BATCH_SIZE=2):
            embed_texts(["a", "b", "c", "d", "e"], client)
        self.assertEqual([len(call) for call in client.calls], [2, 2, 1])

    def test_wrong_dimensions_are_rejected(self):
        from types import SimpleNamespace as NS

        client = NS(embeddings=NS(create=lambda **kw: NS(data=[NS(index=0, embedding=[0.1, 0.2])])))
        with self.assertRaises(EmbeddingError):
            embed_texts(["x"], client)

    def test_empty_input_makes_no_call(self):
        client = FakeEmbeddingClient()
        self.assertEqual(embed_texts([], client), [])
        self.assertEqual(client.calls, [])


class IngestionTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        write_docs(self.dir)
        self.client = FakeEmbeddingClient()

    def test_first_ingest_creates_documents_and_chunks(self):
        report = ingest_directory(self.dir, client=self.client)
        self.assertEqual((report.created, report.updated, report.skipped), (4, 0, 0))
        self.assertEqual(report.chunks, 4)
        self.assertEqual(KnowledgeDocument.objects.count(), 4)
        chunk = KnowledgeChunk.objects.select_related("document").get(
            document__slug="returns", document__language="en"
        )
        self.assertEqual(len(chunk.embedding), EMBEDDING_DIMENSIONS)
        self.assertTrue(chunk.content.startswith("Returns — Window\n"))

    def test_unchanged_documents_are_skipped_without_calling_the_api(self):
        ingest_directory(self.dir, client=self.client)
        calls_before = len(self.client.calls)
        report = ingest_directory(self.dir, client=self.client)
        self.assertEqual((report.created, report.updated, report.skipped), (0, 0, 4))
        self.assertEqual(len(self.client.calls), calls_before)

    def test_changed_document_is_re_embedded_and_old_chunks_removed(self):
        ingest_directory(self.dir, client=self.client)
        (self.dir / "returns.en.md").write_text(
            "# Returns\n\n## Window\nNow 30 days.\n\n## Fees\nNo fees.\n", encoding="utf-8"
        )
        report = ingest_directory(self.dir, client=self.client)
        self.assertEqual((report.updated, report.skipped), (1, 3))
        chunks = KnowledgeChunk.objects.filter(document__slug="returns", document__language="en")
        self.assertEqual(chunks.count(), 2)
        self.assertTrue(any("30 days" in c.content for c in chunks))

    def test_force_re_embeds_everything(self):
        ingest_directory(self.dir, client=self.client)
        report = ingest_directory(self.dir, client=self.client, force=True)
        self.assertEqual(report.updated, 4)

    def test_bad_file_name_is_reported_not_fatal(self):
        (self.dir / "no-language.md").write_text("# X\n\n## Y\nz\n", encoding="utf-8")
        report = ingest_directory(self.dir, client=self.client)
        self.assertEqual(report.created, 4)
        self.assertEqual(len(report.errors), 1)
        self.assertIn("no-language.md", report.errors[0])

    def test_embedding_failure_leaves_no_partial_document(self):
        failing = FakeEmbeddingClient(fail_with=RuntimeError("API down"))
        with self.assertLogs("apps.knowledge.services.ingestion_service", level="ERROR"):
            report = ingest_directory(self.dir, client=failing)
        self.assertEqual(len(report.errors), 4)
        self.assertEqual(KnowledgeDocument.objects.count(), 0)

    def test_prune_removes_documents_whose_file_is_gone(self):
        ingest_directory(self.dir, client=self.client)
        (self.dir / "payment.en.md").unlink()
        report = ingest_directory(self.dir, client=self.client, prune=True)
        self.assertEqual(report.pruned, 1)
        self.assertFalse(KnowledgeDocument.objects.filter(slug="payment").exists())
        self.assertEqual(KnowledgeChunk.objects.filter(document__slug="payment").count(), 0)


@mock.patch(EMBED_QUERY, side_effect=fake_embed_query)
class RetrievalTests(TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        write_docs(tmp.name)
        ingest_directory(tmp.name, client=FakeEmbeddingClient())

    def test_most_relevant_chunk_comes_first(self, _):
        results = retrieval_service.search("can I return my item?")
        self.assertEqual(results[0].slug, "returns")
        self.assertIn("14 days", results[0].content)
        self.assertGreater(results[0].score, 0.2)

    def test_other_topics_are_found_by_their_own_words(self, _):
        self.assertEqual(retrieval_service.search("courier tracking number")[0].slug, "shipping")
        self.assertEqual(retrieval_service.search("pay by card")[0].slug, "payment")

    def test_unrelated_question_returns_nothing(self, _):
        self.assertEqual(retrieval_service.search("zebra quantum"), [])

    def test_empty_query_returns_nothing(self, _):
        self.assertEqual(retrieval_service.search("   "), [])

    def test_language_is_searched_first(self, _):
        results = retrieval_service.search("هل يمكنني الاسترجاع", language="ar")
        self.assertTrue(results)
        self.assertEqual({r.language for r in results}, {"ar"})

    def test_falls_back_to_all_languages(self, _):
        results = retrieval_service.search("courier tracking number", language="ar")
        self.assertEqual(results[0].slug, "shipping")
        self.assertEqual(results[0].language, "en")

    def test_inactive_documents_are_ignored(self, _):
        KnowledgeDocument.objects.filter(slug="returns").update(is_active=False)
        self.assertEqual(retrieval_service.search("can I return my item?"), [])

    def test_top_k_limits_results(self, _):
        self.assertLessEqual(len(retrieval_service.search("return courier card", top_k=1, min_score=0)), 1)


@mock.patch(EMBED_QUERY, side_effect=fake_embed_query)
class PolicyToolTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(full_name="Ali", phone_number="+962791111111")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        write_docs(tmp.name)
        ingest_directory(tmp.name, client=FakeEmbeddingClient())

    def test_tool_is_registered_with_its_schema(self, _):
        self.assertIn("search_policies", tools.get_tool_names())
        schema = next(s for s in tools.get_tool_schemas() if s["function"]["name"] == "search_policies")
        self.assertEqual(schema["function"]["parameters"]["required"], ["query"])

    def test_tool_returns_passages(self, _):
        result = tools.execute_tool(
            "search_policies", json.dumps({"query": "can I return my item?", "language": "en"}), self.customer
        )
        self.assertTrue(result["found"])
        self.assertIn("14 days", result["passages"][0]["text"])
        self.assertEqual(result["passages"][0]["source"], "Returns")

    def test_tool_says_when_nothing_is_found(self, _):
        result = tools.execute_tool("search_policies", json.dumps({"query": "zebra quantum"}), self.customer)
        self.assertFalse(result["found"])
        self.assertIn("Do not guess", result["message"])

    def test_invalid_language_falls_back_to_the_customer_language(self, _):
        result = tools.execute_tool(
            "search_policies", json.dumps({"query": "هل يمكنني الاسترجاع", "language": "fr"}), self.customer
        )
        self.assertTrue(result["found"])
        self.assertEqual(result["passages"][0]["source"], "سياسة الاسترجاع")

    def test_agent_uses_the_tool_and_receives_the_passages(self, _):
        client = FakeClient(
            [
                make_response(tool_calls=[tool_call("c1", "search_policies", {"query": "return item", "language": "en"})]),
                make_response(content="You can return it within 14 days."),
            ]
        )
        result = SupportAgent(client=client).run(self.customer, "Can I return my item?", history=[])

        self.assertEqual(result.tool_calls, ["search_policies"])
        sent_tools = [t["function"]["name"] for t in client.requests[0]["tools"]]
        self.assertIn("search_policies", sent_tools)
        self.assertIn("search_policies", client.requests[0]["messages"][0]["content"])
        payload = json.loads(client.requests[1]["messages"][-1]["content"])
        self.assertTrue(payload["found"])
