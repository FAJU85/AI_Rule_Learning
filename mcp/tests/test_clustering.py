"""Tests for the semantic clustering module (Phase 3)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_rule_learning_mcp.clustering import (
    cluster_signals,
    cluster_texts,
    dedupe_similar,
)


class TestClusterTexts:
    def test_empty(self):
        assert cluster_texts([]) == []

    def test_singleton(self):
        assert cluster_texts(["only one"]) == [[0]]

    def test_similar_texts_cluster_together(self):
        texts = [
            "always add type hints",
            "please include type hints",
            "write descriptive git commit messages",
        ]
        clusters = cluster_texts(texts, threshold=0.2)
        # The two type-hint signals land in one cluster; git stands alone.
        sizes = sorted(len(c) for c in clusters)
        assert sizes == [1, 2]
        type_hint_cluster = max(clusters, key=len)
        assert set(type_hint_cluster) == {0, 1}

    def test_dissimilar_texts_stay_separate(self):
        texts = ["rust ownership", "python decorators", "sql indexes"]
        clusters = cluster_texts(texts, threshold=0.5)
        assert len(clusters) == 3

    def test_indices_are_sorted_and_deterministic(self):
        texts = ["add type hints", "type hints please", "type hints needed"]
        clusters = cluster_texts(texts, threshold=0.2)
        assert clusters == [[0, 1, 2]]


class TestDedupeSimilar:
    def test_collapses_near_duplicates_keeps_distinct(self):
        texts = [
            "always add type hints",
            "include type hints",
            "write unit tests",
        ]
        out = dedupe_similar(texts, threshold=0.2)
        # Two type-hint variants collapse to one; the unit-tests signal remains.
        assert len(out) == 2
        assert any("test" in t for t in out)

    def test_distinct_signals_all_survive(self):
        texts = ["community_signal_xyz", "acknowledge the correction", "stop being verbose"]
        out = dedupe_similar(texts, threshold=0.5)
        assert set(out) == set(texts)

    def test_preserves_first_appearance_order(self):
        texts = ["rust ownership", "python typing", "sql joins"]
        assert dedupe_similar(texts, threshold=0.6) == texts


class TestClusterSignals:
    def test_returns_sorted_by_size(self):
        signals = [
            "add type hints",
            "include type hints",
            "type hints missing",
            "unrelated signal here",
        ]
        groups = cluster_signals(signals, threshold=0.2)
        assert groups[0]["size"] == 3
        assert "type hints" in groups[0]["canonical"]
        assert groups[-1]["size"] == 1
