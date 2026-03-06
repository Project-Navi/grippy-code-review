# SPDX-License-Identifier: MIT
"""CLI for running retrieval quality benchmarks."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

log = logging.getLogger(__name__)

_DEFAULT_DATASETS = ["cosqa"]
_DEFAULT_K = 5
_DEFAULT_GROUND_TRUTH = Path("benchmarks/fixtures/graph_ground_truth.json")


def main() -> None:
    """Parse args and dispatch benchmark suites."""
    parser = argparse.ArgumentParser(
        description="Grippy retrieval quality benchmarks",
    )
    parser.add_argument(
        "suite",
        choices=["search", "graph", "all"],
        help="Which benchmark suite to run",
    )
    parser.add_argument(
        "--output-dir",
        default="benchmarks/output",
        help="Directory for JSON results (default: benchmarks/output)",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=_DEFAULT_K,
        help=f"Cutoff for @k metrics (default: {_DEFAULT_K})",
    )
    parser.add_argument(
        "--datasets",
        nargs="+",
        default=_DEFAULT_DATASETS,
        help=f"CoIR dataset names (default: {_DEFAULT_DATASETS})",
    )
    parser.add_argument(
        "--ground-truth",
        type=Path,
        default=_DEFAULT_GROUND_TRUTH,
        help=f"Path to graph ground truth fixture (default: {_DEFAULT_GROUND_TRUTH})",
    )
    parser.add_argument(
        "--graph-db",
        type=Path,
        default=None,
        help="Path to SQLite graph DB (default: GRIPPY_DATA_DIR/graph.db)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(name)s %(levelname)s %(message)s",
    )

    output_dir = Path(args.output_dir)

    if args.suite in ("search", "all"):
        _run_search(args, output_dir)

    if args.suite in ("graph", "all"):
        _run_graph(args, output_dir)


def _run_search(args: argparse.Namespace, output_dir: Path) -> None:
    """Run search benchmark suite."""
    import os

    from grippy.embedder import create_embedder

    transport = os.environ.get("GRIPPY_TRANSPORT", "local")
    model = os.environ.get("GRIPPY_EMBEDDING_MODEL", "text-embedding-qwen3-embedding-4b")
    base_url = os.environ.get("GRIPPY_BASE_URL", "http://localhost:1234/v1")
    api_key = os.environ.get("GRIPPY_API_KEY", "lm-studio")

    try:
        embedder = create_embedder(transport, model, base_url, api_key)
    except Exception:
        log.exception("Failed to create embedder — is the embedding server running?")
        sys.exit(1)

    from benchmarks.search.runner import SearchBenchmark

    bench = SearchBenchmark(
        embedder=embedder,
        datasets=args.datasets,
        k=args.k,
        output_dir=output_dir,
    )
    bench.run()


def _run_graph(args: argparse.Namespace, output_dir: Path) -> None:
    """Run graph benchmark suite."""
    import os

    from grippy.graph_store import SQLiteGraphStore

    if args.graph_db:
        db_path = args.graph_db
    else:
        data_dir = Path(os.environ.get("GRIPPY_DATA_DIR", "./grippy-data"))
        db_path = data_dir / "graph.db"

    if not db_path.exists():
        log.error("Graph DB not found at %s — run a review first to populate it", db_path)
        sys.exit(1)

    if not args.ground_truth.exists():
        log.error("Ground truth fixture not found at %s", args.ground_truth)
        sys.exit(1)

    store = SQLiteGraphStore(db_path=db_path)
    from benchmarks.graph.runner import GraphBenchmark

    bench = GraphBenchmark(
        store=store,
        ground_truth_path=args.ground_truth,
        output_dir=output_dir,
    )
    bench.run()
