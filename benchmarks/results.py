# SPDX-License-Identifier: MIT
"""Typed result models for retrieval quality benchmarks."""

from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel


class SearchMetrics(BaseModel):
    """Information retrieval metrics for a single search evaluation."""

    ndcg_at_k: float
    mrr: float
    recall_at_k: float
    k: int

    @classmethod
    def from_relevance(
        cls,
        relevant: set[str],
        ranked: list[str],
        *,
        k: int,
    ) -> SearchMetrics:
        """Compute metrics from a relevance set and a ranked result list.

        Args:
            relevant: Set of IDs that are considered relevant.
            ranked: Ordered list of returned IDs (best first).
            k: Cutoff for @k metrics.
        """
        ranked_k = ranked[:k]

        if not relevant:
            return cls(ndcg_at_k=0.0, mrr=0.0, recall_at_k=0.0, k=k)

        # Recall@k
        found = sum(1 for doc in ranked_k if doc in relevant)
        recall = found / len(relevant)

        # MRR — reciprocal rank of first relevant result
        mrr = 0.0
        for i, doc in enumerate(ranked_k):
            if doc in relevant:
                mrr = 1.0 / (i + 1)
                break

        # NDCG@k
        dcg = sum(
            1.0 / math.log2(i + 2)  # i+2 because log2(1) = 0
            for i, doc in enumerate(ranked_k)
            if doc in relevant
        )
        ideal_hits = min(len(relevant), k)
        idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))
        ndcg = dcg / idcg if idcg > 0 else 0.0

        return cls(ndcg_at_k=round(ndcg, 6), mrr=round(mrr, 6), recall_at_k=round(recall, 6), k=k)


class GraphMetrics(BaseModel):
    """Precision/recall for graph traversal results."""

    precision: float
    recall: float

    @classmethod
    def from_sets(cls, expected: set[str], actual: set[str]) -> GraphMetrics:
        """Compute precision and recall from expected vs actual node sets."""
        if not expected and not actual:
            return cls(precision=0.0, recall=0.0)
        if not actual:
            return cls(precision=0.0, recall=0.0)
        if not expected:
            return cls(precision=0.0, recall=0.0)
        overlap = expected & actual
        return cls(
            precision=round(len(overlap) / len(actual), 6),
            recall=round(len(overlap) / len(expected), 6),
        )


class SearchModeResult(BaseModel):
    """Results for one search mode (hybrid or vector) on one dataset."""

    mode: str  # "hybrid" or "vector"
    dataset: str
    metrics: SearchMetrics
    query_count: int


class GraphQueryResult(BaseModel):
    """Results for one graph ground-truth query."""

    query_id: str
    description: str
    metrics: GraphMetrics
    expected_count: int
    actual_count: int


class BenchmarkRun(BaseModel):
    """Top-level result for a complete benchmark run."""

    suite: str  # "search", "graph", or "all"
    timestamp: str
    config: dict[str, Any]
    search_results: list[SearchModeResult]
    graph_results: list[GraphQueryResult]
