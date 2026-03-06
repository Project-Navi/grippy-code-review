# SPDX-License-Identifier: MIT
"""Tests for graph benchmark infrastructure."""

from __future__ import annotations

import json
from pathlib import Path

from benchmarks.graph.ground_truth import GroundTruthQuery, load_ground_truth
from benchmarks.results import GraphMetrics


class TestGroundTruthLoading:
    def test_loads_fixture_file(self, tmp_path: Path) -> None:
        """Loads and validates ground truth from JSON fixture."""
        fixture = [
            {
                "id": "blast-codebase",
                "description": "What depends on codebase.py?",
                "query_type": "walk",
                "params": {
                    "start_files": ["src/grippy/codebase.py"],
                    "direction": "incoming",
                    "rel_allow": ["IMPORTS"],
                    "max_depth": 2,
                },
                "expected_files": ["src/grippy/review.py"],
            }
        ]
        path = tmp_path / "ground_truth.json"
        path.write_text(json.dumps(fixture))
        queries = load_ground_truth(path)
        assert len(queries) == 1
        assert queries[0].id == "blast-codebase"
        assert queries[0].query_type == "walk"

    def test_validates_required_fields(self, tmp_path: Path) -> None:
        """Missing required fields raise ValueError."""
        fixture = [{"id": "bad", "description": "missing fields"}]
        path = tmp_path / "ground_truth.json"
        path.write_text(json.dumps(fixture))
        try:
            load_ground_truth(path)
            assert False, "Should have raised"  # noqa: B011
        except (ValueError, KeyError):
            pass


class TestGroundTruthQuery:
    def test_expected_node_ids(self) -> None:
        """expected_node_ids() generates deterministic IDs from file paths."""
        from grippy.graph_types import _record_id

        q = GroundTruthQuery(
            id="test",
            description="test query",
            query_type="walk",
            params={"start_files": ["a.py"], "direction": "incoming"},
            expected_files=["b.py", "c.py"],
        )
        ids = q.expected_node_ids()
        assert ids == {_record_id("FILE", "b.py"), _record_id("FILE", "c.py")}
