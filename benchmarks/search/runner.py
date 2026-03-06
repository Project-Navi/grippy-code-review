# SPDX-License-Identifier: MIT
"""Search benchmark runner — evaluates retrieval quality via CoIR datasets."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from benchmarks.results import BenchmarkRun, SearchMetrics, SearchModeResult
from benchmarks.search.adapter import GrippyRetriever
from benchmarks.search.metrics import aggregate_metrics, format_search_table

log = logging.getLogger(__name__)


class SearchBenchmark:
    """Evaluates grippy's embedder against CoIR code retrieval datasets.

    Runs vector-only search for all datasets. Computes NDCG@k, MRR, Recall@k.
    """

    def __init__(
        self,
        *,
        embedder: Any,
        datasets: list[str],
        k: int = 5,
        output_dir: Path,
        use_batch: bool = False,
    ) -> None:
        self._embedder = embedder
        self._datasets = datasets
        self._k = k
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._retriever = GrippyRetriever(embedder=embedder, use_batch=use_batch)

    def run(self) -> list[SearchModeResult]:
        """Run all datasets and return results."""
        all_results: list[SearchModeResult] = []

        for dataset_name in self._datasets:
            log.info("Evaluating dataset: %s", dataset_name)
            queries, corpus, qrels = self._load_dataset(dataset_name)

            # Encode everything once
            query_ids = list(queries.keys())
            query_texts = [queries[qid] for qid in query_ids]
            corpus_ids = list(corpus.keys())
            corpus_docs = [corpus[cid] for cid in corpus_ids]

            query_vecs = self._retriever.encode_queries(query_texts)
            corpus_vecs = self._retriever.encode_corpus(corpus_docs)

            # Vector search: cosine similarity ranking
            vector_metrics = self._evaluate_vector(
                query_ids, query_vecs, corpus_ids, corpus_vecs, qrels
            )
            all_results.append(
                SearchModeResult(
                    mode="vector",
                    dataset=dataset_name,
                    metrics=vector_metrics,
                    query_count=len(query_ids),
                )
            )
            log.info(
                "  vector — NDCG@%d: %.4f  MRR: %.4f  Recall@%d: %.4f",
                self._k,
                vector_metrics.ndcg_at_k,
                vector_metrics.mrr,
                self._k,
                vector_metrics.recall_at_k,
            )

        # Print summary table
        table = format_search_table(all_results)
        log.info("\n%s", table)

        # Write results
        self._write_results(all_results)
        return all_results

    def _evaluate_vector(
        self,
        query_ids: list[str],
        query_vecs: np.ndarray,
        corpus_ids: list[str],
        corpus_vecs: np.ndarray,
        qrels: dict[str, dict[str, int]],
    ) -> SearchMetrics:
        """Evaluate vector-only retrieval via cosine similarity."""
        # Normalize for cosine similarity
        q_norms = np.linalg.norm(query_vecs, axis=1, keepdims=True)
        c_norms = np.linalg.norm(corpus_vecs, axis=1, keepdims=True)
        q_normed = query_vecs / np.maximum(q_norms, 1e-10)
        c_normed = corpus_vecs / np.maximum(c_norms, 1e-10)

        # Similarity matrix: (num_queries, num_corpus)
        sims = q_normed @ c_normed.T

        per_query: list[SearchMetrics] = []
        for i, qid in enumerate(query_ids):
            relevant = {cid for cid, score in qrels.get(qid, {}).items() if score > 0}
            if not relevant:
                continue

            # Rank corpus by similarity
            top_indices = np.argsort(sims[i])[::-1][: self._k]
            ranked = [corpus_ids[idx] for idx in top_indices]
            per_query.append(SearchMetrics.from_relevance(relevant, ranked, k=self._k))

        return aggregate_metrics(per_query)

    def _load_dataset(
        self, dataset_name: str
    ) -> tuple[dict[str, str], dict[str, dict[str, str]], dict[str, dict[str, int]]]:
        """Load a CoIR dataset. Returns (queries, corpus, qrels).

        queries: {query_id: query_text}
        corpus: {doc_id: {"title": ..., "text": ...}}
        qrels: {query_id: {doc_id: relevance_score}}
        """
        try:
            import coir
            from coir.data_loader import get_tasks

            tasks = get_tasks(tasks=[dataset_name])
            task = tasks[0]
            return task.queries, task.corpus, task.qrels
        except ImportError:
            log.warning("coir-eval not installed — install with: uv sync --extra benchmarks")
            raise

    def _write_results(self, results: list[SearchModeResult]) -> None:
        """Write results to JSON file."""
        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        run = BenchmarkRun(
            suite="search",
            timestamp=datetime.now(UTC).isoformat(),
            config={
                "k": self._k,
                "datasets": self._datasets,
                "embedder": str(type(self._embedder).__name__),
            },
            search_results=results,
            graph_results=[],
        )
        out_path = self._output_dir / f"search_{ts}.json"
        out_path.write_text(run.model_dump_json(indent=2))
        log.info("Results written to %s", out_path)
