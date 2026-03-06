# SPDX-License-Identifier: MIT
"""Ground truth loader for graph traversal benchmarks."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from grippy.graph_types import _record_id

log = logging.getLogger(__name__)

_REQUIRED_FIELDS = {"id", "description", "query_type", "params", "expected_files"}


@dataclass(frozen=True)
class GroundTruthQuery:
    """A labeled query with expected graph traversal results."""

    id: str
    description: str
    query_type: str  # "walk", "neighbors", "blast_radius"
    params: dict[str, Any]
    expected_files: list[str]
    tags: list[str] = field(default_factory=list)

    def expected_node_ids(self) -> set[str]:
        """Convert expected file paths to deterministic node IDs."""
        return {_record_id("FILE", f) for f in self.expected_files}


def load_ground_truth(path: Path) -> list[GroundTruthQuery]:
    """Load and validate ground truth queries from a JSON fixture.

    Raises:
        ValueError: If any query is missing required fields.
    """
    data = json.loads(path.read_text())
    queries: list[GroundTruthQuery] = []
    for i, entry in enumerate(data):
        missing = _REQUIRED_FIELDS - set(entry.keys())
        if missing:
            msg = f"Ground truth query {i} missing fields: {missing}"
            raise ValueError(msg)
        queries.append(
            GroundTruthQuery(
                id=entry["id"],
                description=entry["description"],
                query_type=entry["query_type"],
                params=entry["params"],
                expected_files=entry["expected_files"],
                tags=entry.get("tags", []),
            )
        )
    log.info("Loaded %d ground truth queries from %s", len(queries), path)
    return queries
