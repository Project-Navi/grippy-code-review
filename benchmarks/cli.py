# SPDX-License-Identifier: MIT
"""CLI for running retrieval quality benchmarks."""

from __future__ import annotations

import argparse
import logging
import sys

log = logging.getLogger(__name__)


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

    log.info("Benchmark suite %r not yet implemented", args.suite)
    sys.exit(1)
