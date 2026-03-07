# SPDX-License-Identifier: MIT
"""Tests for benchmark result models."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from benchmarks.results import (
    BenchmarkRun,
    GraphMetrics,
    SearchMetrics,
    SearchModeResult,
)


class TestSearchMetrics:
    def test_from_relevance_scores_perfect(self) -> None:
        """Perfect ranking: all relevant docs at top positions."""
        relevant = {"doc1", "doc2", "doc3"}
        ranked = ["doc1", "doc2", "doc3", "doc4", "doc5"]
        metrics = SearchMetrics.from_relevance(relevant, ranked, k=5)
        assert metrics.recall_at_k == 1.0
        assert metrics.mrr == 1.0
        assert metrics.ndcg_at_k > 0.9

    def test_from_relevance_scores_none_found(self) -> None:
        """No relevant docs in ranking."""
        relevant = {"doc1", "doc2"}
        ranked = ["doc3", "doc4", "doc5"]
        metrics = SearchMetrics.from_relevance(relevant, ranked, k=5)
        assert metrics.recall_at_k == 0.0
        assert metrics.mrr == 0.0
        assert metrics.ndcg_at_k == 0.0

    def test_from_relevance_scores_partial(self) -> None:
        """Some relevant docs found, not at top."""
        relevant = {"doc1", "doc2", "doc3"}
        ranked = ["doc4", "doc1", "doc5", "doc3", "doc6"]
        metrics = SearchMetrics.from_relevance(relevant, ranked, k=5)
        assert 0.0 < metrics.recall_at_k < 1.0
        assert metrics.mrr > 0.0

    def test_empty_ranking(self) -> None:
        """Empty ranking returns zero metrics."""
        relevant = {"doc1"}
        metrics = SearchMetrics.from_relevance(relevant, [], k=5)
        assert metrics.recall_at_k == 0.0
        assert metrics.mrr == 0.0
        assert metrics.ndcg_at_k == 0.0

    def test_empty_relevant_set(self) -> None:
        """No relevant docs defined — recall undefined, treat as 0."""
        metrics = SearchMetrics.from_relevance(set(), ["doc1", "doc2"], k=5)
        assert metrics.recall_at_k == 0.0


class TestGraphMetrics:
    def test_perfect_precision_recall(self) -> None:
        expected = {"A", "B", "C"}
        actual = {"A", "B", "C"}
        metrics = GraphMetrics.from_sets(expected, actual)
        assert metrics.precision == 1.0
        assert metrics.recall == 1.0

    def test_partial_overlap(self) -> None:
        expected = {"A", "B", "C", "D"}
        actual = {"A", "B", "E"}
        metrics = GraphMetrics.from_sets(expected, actual)
        assert abs(metrics.precision - 2 / 3) < 1e-5
        assert metrics.recall == 0.5

    def test_no_overlap(self) -> None:
        expected = {"A", "B"}
        actual = {"C", "D"}
        metrics = GraphMetrics.from_sets(expected, actual)
        assert metrics.precision == 0.0
        assert metrics.recall == 0.0

    def test_empty_actual(self) -> None:
        expected = {"A", "B"}
        metrics = GraphMetrics.from_sets(expected, set())
        assert metrics.precision == 0.0
        assert metrics.recall == 0.0

    def test_empty_expected(self) -> None:
        metrics = GraphMetrics.from_sets(set(), {"A"})
        assert metrics.precision == 0.0
        assert metrics.recall == 0.0


class TestBenchmarkRun:
    def test_serializes_to_json(self) -> None:
        run = BenchmarkRun(
            suite="search",
            timestamp=datetime(2026, 3, 4, tzinfo=UTC).isoformat(),
            config={"model": "test-model", "k": 5},
            search_results=[
                SearchModeResult(
                    mode="hybrid",
                    dataset="CosQA",
                    metrics=SearchMetrics(
                        ndcg_at_k=0.85,
                        mrr=0.9,
                        recall_at_k=0.75,
                        k=5,
                    ),
                    query_count=100,
                ),
            ],
            graph_results=[],
        )
        data = json.loads(run.model_dump_json())
        assert data["suite"] == "search"
        assert len(data["search_results"]) == 1
        assert data["search_results"][0]["metrics"]["ndcg_at_k"] == 0.85
