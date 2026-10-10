from django.test import SimpleTestCase

from apps.knowledge.services.retrieval_service import rank_by_cosine


class RankByCosineTests(SimpleTestCase):
    ROWS = [(1, [1.0, 0.0, 0.0]), (2, [0.0, 1.0, 0.0]), (3, [0.7, 0.7, 0.0])]

    def test_best_match_first_with_scores(self):
        ranked = rank_by_cosine([1.0, 0.0, 0.0], self.ROWS, top_k=3, threshold=-1)
        self.assertEqual([chunk_id for chunk_id, _ in ranked], [1, 3, 2])
        self.assertAlmostEqual(ranked[0][1], 1.0)
        self.assertAlmostEqual(ranked[1][1], 0.7071, places=3)
        self.assertAlmostEqual(ranked[2][1], 0.0)

    def test_threshold_filters_weak_matches(self):
        ranked = rank_by_cosine([1.0, 0.0, 0.0], self.ROWS, top_k=3, threshold=0.5)
        self.assertEqual([chunk_id for chunk_id, _ in ranked], [1, 3])

    def test_top_k_limits_results(self):
        self.assertEqual(len(rank_by_cosine([1.0, 0.0, 0.0], self.ROWS, top_k=1, threshold=-1)), 1)

    def test_vectors_do_not_need_to_be_normalised(self):
        ranked = rank_by_cosine([10.0, 0.0, 0.0], [(1, [5.0, 0.0, 0.0])], top_k=1, threshold=0.99)
        self.assertEqual(ranked[0][0], 1)

    def test_empty_inputs_and_zero_vectors(self):
        self.assertEqual(rank_by_cosine([1.0, 0.0], [], top_k=3, threshold=0), [])
        self.assertEqual(rank_by_cosine([0.0, 0.0], [(1, [1.0, 0.0])], top_k=3, threshold=0), [])
        self.assertEqual(rank_by_cosine([1.0, 0.0], [(1, [0.0, 0.0])], top_k=3, threshold=0.1), [])
