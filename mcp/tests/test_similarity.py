"""Tests for the lightweight TF-IDF cosine similarity module (Phase 1)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_rule_learning_mcp.similarity import (
    cosine,
    rank_by_relevance,
    rank_documents,
    tokenize,
)


class TestTokenize:
    def test_lowercases_and_splits(self):
        assert tokenize("Add Type Hints") == ["add", "type", "hints"]

    def test_drops_stopwords_and_single_chars(self):
        # "always", "the", "to", "a" are stopwords; "x" is a single char.
        assert tokenize("always add the type hints to a x function") == [
            "add",
            "type",
            "hints",
            "function",
        ]

    def test_empty(self):
        assert tokenize("") == []


class TestCosine:
    def test_identical_vectors(self):
        v = {"a": 1.0, "b": 2.0}
        assert cosine(v, v) == pytest.approx(1.0)

    def test_disjoint_vectors(self):
        assert cosine({"a": 1.0}, {"b": 1.0}) == 0.0

    def test_empty_vector(self):
        assert cosine({}, {"a": 1.0}) == 0.0


class TestRankDocuments:
    def test_relevant_document_ranks_first(self):
        docs = [
            "use rust ownership and borrowing",
            "always add python type hints to functions",
            "write descriptive git commit messages",
        ]
        ranking = rank_documents("python type hints for this function", docs)
        assert ranking[0][0] == 1  # the python doc
        assert ranking[0][1] > 0.0

    def test_top_k_trims(self):
        docs = ["python hints", "rust borrow", "git commit"]
        assert len(rank_documents("python", docs, top_k=1)) == 1

    def test_query_with_no_overlap_scores_zero(self):
        docs = ["python type hints", "rust ownership"]
        ranking = rank_documents("completely unrelated terms", docs)
        assert all(score == 0.0 for _, score in ranking)


class TestRankByRelevance:
    def test_reorders_items_by_relevance(self):
        items = [
            {"id": "git", "text": "write descriptive git commit messages"},
            {"id": "py", "text": "always add python type hints to functions"},
        ]
        ordered = rank_by_relevance("python type hints", items, text_of=lambda r: r["text"])
        assert ordered[0]["id"] == "py"

    def test_stable_when_no_query_overlap(self):
        # Zero relevance for all -> incoming order preserved (stable sort),
        # which gives callers "priority order as the tiebreak" for free.
        items = [{"id": "a", "text": "rust"}, {"id": "b", "text": "go"}]
        ordered = rank_by_relevance("python", items, text_of=lambda r: r["text"])
        assert [r["id"] for r in ordered] == ["a", "b"]

    def test_empty_query_returns_input_order(self):
        items = [{"id": "a", "text": "x"}, {"id": "b", "text": "y"}]
        assert rank_by_relevance("", items, text_of=lambda r: r["text"]) == items
