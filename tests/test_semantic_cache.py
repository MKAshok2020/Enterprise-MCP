import unittest

from app.application.cache_manager import CacheManager


class SemanticCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        CacheManager.reset_for_testing()
        self.cache = CacheManager()

    def tearDown(self) -> None:
        CacheManager.reset_for_testing()

    def test_stores_and_finds_semantically_similar_queries(self) -> None:
        base_embedding = [1.0, 0.0, 0.0]
        similar_embedding = [0.99, 0.01, 0.0]
        different_embedding = [0.0, 1.0, 0.0]
        response = {"answer": "The capital of France is Paris.", "tool": None}

        self.cache.store_semantic(
            query="What is the capital of France?",
            embedding=base_embedding,
            value=response,
            context_key="user-1:session-1::",
            ttl=300,
            max_entries=10,
        )

        match = self.cache.lookup_semantic(similar_embedding, "user-1:session-1::", 0.9)
        self.assertIsNotNone(match)
        cached_value, score = match
        self.assertEqual(cached_value["answer"], response["answer"])
        self.assertGreater(score, 0.9)

        self.assertIsNone(
            self.cache.lookup_semantic(different_embedding, "user-1:session-1::", 0.9)
        )

    def test_respects_context_key_isolation(self) -> None:
        embedding = [1.0, 0.0]
        response = {"answer": "Cached answer", "tool": None}

        self.cache.store_semantic(
            query="hello",
            embedding=embedding,
            value=response,
            context_key="user-1:session-a::",
            ttl=300,
            max_entries=10,
        )

        self.assertIsNone(self.cache.lookup_semantic(embedding, "user-2:session-a::", 0.9))

    def test_expires_semantic_entries(self) -> None:
        embedding = [1.0, 0.0]
        response = {"answer": "Short-lived answer", "tool": None}

        self.cache.store_semantic(
            query="hello",
            embedding=embedding,
            value=response,
            context_key="user-1:session-1::",
            ttl=0,
            max_entries=10,
        )
        self.cache.cleanup()

        self.assertIsNone(self.cache.lookup_semantic(embedding, "user-1:session-1::", 0.9))

    def test_enforces_max_entry_limit(self) -> None:
        for index in range(3):
            self.cache.store_semantic(
                query=f"query-{index}",
                embedding=[float(index), 1.0],
                value={"answer": f"answer-{index}", "tool": None},
                context_key="shared",
                ttl=300,
                max_entries=2,
            )

        stats = self.cache.stats()
        self.assertEqual(stats["semantic_cache_size"], 2)


if __name__ == "__main__":
    unittest.main()
