"""Tests for hybrid retriever and keyword search."""

from __future__ import annotations

from codereviewmate.core.context.retriever import KeywordRetriever


class TestKeywordRetriever:
    def test_exact_match(self):
        retriever = KeywordRetriever()
        chunks = [
            ("c1", "Python is great for data science"),
            ("c2", "JavaScript runs in the browser"),
            ("c3", "Rust is a systems programming language"),
        ]
        results = retriever.search("python data science", chunks, top_k=2)
        assert len(results) > 0
        assert results[0][0] == "c1"  # Best match

    def test_no_match(self):
        retriever = KeywordRetriever()
        chunks = [("c1", "Python programming"), ("c2", "Java development")]
        results = retriever.search("rust cargo", chunks)
        assert results == []

    def test_empty_query(self):
        retriever = KeywordRetriever()
        chunks = [("c1", "Some content")]
        results = retriever.search("", chunks)
        assert results == []

    def test_score_ordering(self):
        retriever = KeywordRetriever()
        chunks = [
            ("c1", "database migration schema SQL"),
            ("c2", "database database database"),
            ("c3", "something else entirely"),
        ]
        results = retriever.search("database", chunks, top_k=3)
        scores = [s for _, s in results]
        # Should be sorted descending by score
        assert scores == sorted(scores, reverse=True)
        assert len(results) >= 2  # At least c1 and c2 should match

    def test_partial_word_match(self):
        retriever = KeywordRetriever()
        chunks = [("c1", "authentication and authorization module")]
        results = retriever.search("auth", chunks)
        # "auth" is a substring of "authentication" and "authorization"
        assert len(results) == 1
