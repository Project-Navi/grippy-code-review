# SPDX-License-Identifier: MIT
"""Search metric aggregation and formatting."""

from __future__ import annotations

from benchmarks.results import SearchMetrics, SearchModeResult


def aggregate_metrics(metrics_list: list[SearchMetrics]) -> SearchMetrics:
    """Average metrics across multiple queries."""
    if not metrics_list:
        return SearchMetrics(ndcg_at_k=0.0, mrr=0.0, recall_at_k=0.0, k=0)

    k = metrics_list[0].k
    n = len(metrics_list)
    return SearchMetrics(
        ndcg_at_k=round(sum(m.ndcg_at_k for m in metrics_list) / n, 6),
        mrr=round(sum(m.mrr for m in metrics_list) / n, 6),
        recall_at_k=round(sum(m.recall_at_k for m in metrics_list) / n, 6),
        k=k,
    )


def format_search_table(results: list[SearchModeResult]) -> str:
    """Format search results as a readable terminal table."""
    header = (
        f"{'Dataset':<20} {'Mode':<10} {'NDCG@k':>8} {'MRR':>8} {'Recall@k':>10} {'Queries':>8}"
    )
    sep = "-" * len(header)
    lines = [sep, header, sep]
    for r in results:
        lines.append(
            f"{r.dataset:<20} {r.mode:<10} {r.metrics.ndcg_at_k:>8.4f} "
            f"{r.metrics.mrr:>8.4f} {r.metrics.recall_at_k:>10.4f} {r.query_count:>8}"
        )
    lines.append(sep)
    return "\n".join(lines)
