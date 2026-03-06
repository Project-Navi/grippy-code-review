# SPDX-License-Identifier: MIT
"""Tests for search benchmark infrastructure."""

from __future__ import annotations

from benchmarks.results import SearchMetrics
from benchmarks.search.metrics import aggregate_metrics, format_search_table


class TestAggregateMetrics:
    def test_averages_multiple_queries(self) -> None:
        """Aggregate averages metrics across queries."""
        m1 = SearchMetrics(ndcg_at_k=0.8, mrr=0.5, recall_at_k=1.0, k=5)
        m2 = SearchMetrics(ndcg_at_k=0.6, mrr=1.0, recall_at_k=0.5, k=5)
        avg = aggregate_metrics([m1, m2])
        assert avg.ndcg_at_k == 0.7
        assert avg.mrr == 0.75
        assert avg.recall_at_k == 0.75

    def test_single_query(self) -> None:
        m = SearchMetrics(ndcg_at_k=0.9, mrr=0.9, recall_at_k=0.9, k=5)
        avg = aggregate_metrics([m])
        assert avg.ndcg_at_k == 0.9

    def test_empty_list_returns_zeros(self) -> None:
        avg = aggregate_metrics([])
        assert avg.ndcg_at_k == 0.0
        assert avg.mrr == 0.0
        assert avg.recall_at_k == 0.0


class TestFormatSearchTable:
    def test_produces_readable_table(self) -> None:
        from benchmarks.results import SearchModeResult

        results = [
            SearchModeResult(
                mode="hybrid",
                dataset="CosQA",
                metrics=SearchMetrics(ndcg_at_k=0.85, mrr=0.9, recall_at_k=0.75, k=5),
                query_count=100,
            ),
            SearchModeResult(
                mode="vector",
                dataset="CosQA",
                metrics=SearchMetrics(ndcg_at_k=0.72, mrr=0.8, recall_at_k=0.6, k=5),
                query_count=100,
            ),
        ]
        table = format_search_table(results)
        assert "hybrid" in table
        assert "vector" in table
        assert "CosQA" in table
        assert "NDCG" in table


from unittest.mock import MagicMock

from benchmarks.search.adapter import GrippyRetriever


class TestGrippyRetriever:
    def test_encode_queries_returns_embeddings(self) -> None:
        """Adapter encodes queries via the embedder."""
        embedder = MagicMock()
        embedder.get_embedding.return_value = [0.1, 0.2, 0.3]
        retriever = GrippyRetriever(embedder=embedder)
        result = retriever.encode_queries(["hello world", "test query"])
        assert result.shape == (2, 3)
        assert embedder.get_embedding.call_count == 2

    def test_encode_corpus_returns_embeddings(self) -> None:
        """Adapter encodes corpus documents via the embedder."""
        embedder = MagicMock()
        embedder.get_embedding.return_value = [0.1, 0.2, 0.3]
        retriever = GrippyRetriever(embedder=embedder)
        corpus = [
            {"title": "func", "text": "def hello(): pass"},
            {"title": "var", "text": "x = 1"},
        ]
        result = retriever.encode_corpus(corpus)
        assert result.shape == (2, 3)

    def test_uses_batch_embedder_when_available(self) -> None:
        """Adapter uses get_embedding_batch when embedder supports it."""
        embedder = MagicMock()
        embedder.get_embedding_batch.return_value = [[0.1, 0.2], [0.3, 0.4]]
        retriever = GrippyRetriever(embedder=embedder, use_batch=True)
        result = retriever.encode_queries(["q1", "q2"])
        assert result.shape == (2, 2)
        embedder.get_embedding_batch.assert_called_once()


from pathlib import Path
from unittest.mock import patch

from benchmarks.search.runner import SearchBenchmark


class TestSearchBenchmark:
    def _make_fake_embedder(self, dim: int = 8) -> MagicMock:
        embedder = MagicMock()
        embedder.get_embedding.return_value = [0.1] * dim
        return embedder

    def test_run_returns_results_for_each_mode(self, tmp_path: Path) -> None:
        """Runner produces results for both hybrid and vector modes."""
        embedder = self._make_fake_embedder()
        bench = SearchBenchmark(
            embedder=embedder,
            datasets=["test-dataset"],
            k=5,
            output_dir=tmp_path,
        )
        fake_queries = {"q1": "find hello function", "q2": "path traversal"}
        fake_corpus = {
            "d1": {"title": "hello", "text": "def hello(): pass"},
            "d2": {"title": "traversal", "text": "os.path.join(user_input)"},
        }
        fake_qrels = {"q1": {"d1": 1}, "q2": {"d2": 1}}

        with patch.object(
            bench, "_load_dataset", return_value=(fake_queries, fake_corpus, fake_qrels)
        ):
            results = bench.run()

        assert len(results) >= 1
        modes = {r.mode for r in results}
        assert "vector" in modes
        for r in results:
            assert r.dataset == "test-dataset"
            assert r.query_count == 2

    def test_writes_json_output(self, tmp_path: Path) -> None:
        """Runner writes results JSON to output directory."""
        embedder = self._make_fake_embedder()
        bench = SearchBenchmark(
            embedder=embedder,
            datasets=["test-dataset"],
            k=5,
            output_dir=tmp_path,
        )
        fake_queries = {"q1": "test"}
        fake_corpus = {"d1": {"title": "t", "text": "x = 1"}}
        fake_qrels = {"q1": {"d1": 1}}

        with patch.object(
            bench, "_load_dataset", return_value=(fake_queries, fake_corpus, fake_qrels)
        ):
            bench.run()

        json_files = list(tmp_path.glob("search_*.json"))
        assert len(json_files) == 1
