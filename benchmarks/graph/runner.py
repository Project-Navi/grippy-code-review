# SPDX-License-Identifier: MIT
"""Graph benchmark runner — evaluates traversal accuracy against ground truth."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from benchmarks.graph.ground_truth import GroundTruthQuery, load_ground_truth
from benchmarks.results import BenchmarkRun, GraphMetrics, GraphQueryResult
from grippy.graph_store import SQLiteGraphStore
from grippy.graph_types import _record_id

log = logging.getLogger(__name__)


class GraphBenchmark:
    """Evaluates graph traversal accuracy against hand-labeled ground truth."""

    def __init__(
        self,
        *,
        store: SQLiteGraphStore,
        ground_truth_path: Path,
        output_dir: Path,
    ) -> None:
        self._store = store
        self._ground_truth_path = ground_truth_path
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def run(self) -> list[GraphQueryResult]:
        """Run all ground truth queries and return results."""
        queries = load_ground_truth(self._ground_truth_path)
        results: list[GraphQueryResult] = []

        for query in queries:
            log.info("Evaluating: %s", query.description)
            if query.query_type == "walk":
                result = self._evaluate_walk(query)
            elif query.query_type == "neighbors":
                result = self._evaluate_neighbors(query)
            else:
                log.warning("Unknown query type: %s, skipping", query.query_type)
                continue

            results.append(result)
            log.info(
                "  P=%.4f  R=%.4f  (expected=%d, actual=%d)",
                result.metrics.precision,
                result.metrics.recall,
                result.expected_count,
                result.actual_count,
            )

        # Print summary
        table = self._format_table(results)
        log.info("\n%s", table)

        # Write results
        self._write_results(results)
        return results

    def _evaluate_walk(self, query: GroundTruthQuery) -> GraphQueryResult:
        """Evaluate a walk query against ground truth."""
        params = query.params
        start_ids = [_record_id("FILE", f) for f in params["start_files"]]
        start_set = set(start_ids)

        walk_result = self._store.walk(
            start_ids,
            max_depth=params.get("max_depth", 2),
            rel_allow=params.get("rel_allow"),
            direction=params.get("direction", "outgoing"),
        )

        # Actual result: all discovered nodes except start nodes
        actual_ids = {n.id for n in walk_result.nodes if n.id not in start_set}
        expected_ids = query.expected_node_ids()

        metrics = GraphMetrics.from_sets(expected_ids, actual_ids)
        return GraphQueryResult(
            query_id=query.id,
            description=query.description,
            metrics=metrics,
            expected_count=len(expected_ids),
            actual_count=len(actual_ids),
        )

    def _evaluate_neighbors(self, query: GroundTruthQuery) -> GraphQueryResult:
        """Evaluate a neighbors query against ground truth."""
        params = query.params
        start_id = _record_id("FILE", params["start_files"][0])

        nb_result = self._store.neighbors(
            start_id,
            direction=params.get("direction", "both"),
            rel_filter=params.get("rel_allow"),
        )

        actual_ids: set[str] = set()
        for _edge, node in nb_result.outgoing:
            actual_ids.add(node.id)
        for _edge, node in nb_result.incoming:
            actual_ids.add(node.id)

        expected_ids = query.expected_node_ids()
        metrics = GraphMetrics.from_sets(expected_ids, actual_ids)
        return GraphQueryResult(
            query_id=query.id,
            description=query.description,
            metrics=metrics,
            expected_count=len(expected_ids),
            actual_count=len(actual_ids),
        )

    def _format_table(self, results: list[GraphQueryResult]) -> str:
        """Format graph results as a readable terminal table."""
        header = f"{'Query':<40} {'P':>8} {'R':>8} {'Exp':>6} {'Act':>6}"
        sep = "-" * len(header)
        lines = [sep, header, sep]
        for r in results:
            desc = r.description[:38] + ".." if len(r.description) > 40 else r.description
            lines.append(
                f"{desc:<40} {r.metrics.precision:>8.4f} {r.metrics.recall:>8.4f} "
                f"{r.expected_count:>6} {r.actual_count:>6}"
            )
        lines.append(sep)
        return "\n".join(lines)

    def _write_results(self, results: list[GraphQueryResult]) -> None:
        """Write results to JSON file."""
        now = datetime.now(UTC)
        ts = now.strftime("%Y%m%d_%H%M%S")
        run = BenchmarkRun(
            suite="graph",
            timestamp=now.isoformat(),
            config={"ground_truth": str(self._ground_truth_path)},
            search_results=[],
            graph_results=results,
        )
        out_path = self._output_dir / f"graph_{ts}.json"
        out_path.write_text(run.model_dump_json(indent=2))
        log.info("Results written to %s", out_path)
