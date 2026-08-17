"""In-memory exact and semantic response caches for chat orchestration."""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class CacheItem:
    value: Any
    expiry: float


@dataclass
class SemanticCacheEntry:
    """A semantically indexed chat response."""

    query: str
    embedding: list[float]
    value: Any
    context_key: str
    expiry: float


class CacheManager:
    """Thread-safe singleton cache with optional semantic similarity lookup."""

    _instance: CacheManager | None = None
    _lock = threading.Lock()

    def __new__(cls) -> CacheManager:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._cache: dict[str, CacheItem] = {}
                    instance._semantic_cache: list[SemanticCacheEntry] = []
                    instance._hits = 0
                    instance._misses = 0
                    instance._semantic_hits = 0
                    instance._semantic_misses = 0
                    cls._instance = instance
        return cls._instance

    @classmethod
    def reset_for_testing(cls) -> None:
        """Clear the singleton so tests start from a clean cache."""
        with cls._lock:
            cls._instance = None

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """Store an exact-match cache entry."""
        expiry = time.time() + ttl
        self._cache[key] = CacheItem(value, expiry)

    def get(self, key: str) -> Any | None:
        """Return an exact-match cache entry when present and not expired."""
        item = self._cache.get(key)
        if item is None:
            self._misses += 1
            return None
        if item.expiry < time.time():
            del self._cache[key]
            self._misses += 1
            return None
        self._hits += 1
        return item.value

    def lookup_semantic(
        self,
        embedding: list[float],
        context_key: str,
        threshold: float,
    ) -> tuple[Any, float] | None:
        """Return the best matching cached response above the similarity threshold."""
        now = time.time()
        best_match: SemanticCacheEntry | None = None
        best_score = 0.0

        for entry in self._semantic_cache:
            if entry.context_key != context_key or entry.expiry < now:
                continue
            score = self._cosine_similarity(embedding, entry.embedding)
            if score >= threshold and score > best_score:
                best_match = entry
                best_score = score

        if best_match is None:
            self._semantic_misses += 1
            return None

        self._semantic_hits += 1
        return best_match.value, best_score

    def store_semantic(
        self,
        query: str,
        embedding: list[float],
        value: Any,
        context_key: str,
        ttl: int,
        max_entries: int,
    ) -> None:
        """Persist a response for future semantic lookup."""
        self.cleanup()
        expiry = time.time() + ttl
        self._semantic_cache.append(
            SemanticCacheEntry(
                query=query,
                embedding=embedding,
                value=value,
                context_key=context_key,
                expiry=expiry,
            )
        )
        self._enforce_semantic_limit(max_entries)

    def delete(self, key: str) -> None:
        """Remove a single exact-match cache entry."""
        self._cache.pop(key, None)

    def clear(self) -> None:
        """Remove all cached entries."""
        self._cache.clear()
        self._semantic_cache.clear()

    def exists(self, key: str) -> bool:
        return self.get(key) is not None

    def cleanup(self) -> None:
        """Remove expired exact-match and semantic entries."""
        now = time.time()
        expired_keys = [key for key, item in self._cache.items() if item.expiry < now]
        for key in expired_keys:
            del self._cache[key]
        self._semantic_cache = [
            entry for entry in self._semantic_cache if entry.expiry >= now
        ]

    def stats(self) -> dict[str, Any]:
        total = self._hits + self._misses
        semantic_total = self._semantic_hits + self._semantic_misses
        return {
            "cache_size": len(self._cache),
            "semantic_cache_size": len(self._semantic_cache),
            "hits": self._hits,
            "misses": self._misses,
            "hit_ratio": round(self._hits / total, 2) if total else 0,
            "semantic_hits": self._semantic_hits,
            "semantic_misses": self._semantic_misses,
            "semantic_hit_ratio": round(
                self._semantic_hits / semantic_total, 2
            ) if semantic_total else 0,
        }

    def _enforce_semantic_limit(self, max_entries: int) -> None:
        if max_entries <= 0:
            self._semantic_cache.clear()
            return
        overflow = len(self._semantic_cache) - max_entries
        if overflow <= 0:
            return
        self._semantic_cache.sort(key=lambda entry: entry.expiry)
        del self._semantic_cache[:overflow]

    @staticmethod
    def _cosine_similarity(left: list[float], right: list[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        dot = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return dot / (left_norm * right_norm)
