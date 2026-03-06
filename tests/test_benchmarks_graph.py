# SPDX-License-Identifier: MIT
"""Tests for graph benchmark infrastructure."""

from __future__ import annotations

import json
from pathlib import Path

from benchmarks.graph.ground_truth import GroundTruthQuery, load_ground_truth
from benchmarks.graph.runner import GraphBenchmark
from grippy.graph_store import SQLiteGraphStore
from grippy.graph_types import _record_id


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
        q = GroundTruthQuery(
            id="test",
            description="test query",
            query_type="walk",
            params={"start_files": ["a.py"], "direction": "incoming"},
            expected_files=["b.py", "c.py"],
        )
        ids = q.expected_node_ids()
        assert ids == {_record_id("FILE", "b.py"), _record_id("FILE", "c.py")}


class TestGraphBenchmark:
    def _populate_store(self, store: SQLiteGraphStore) -> None:
        """Populate store with a known graph: A imports B, B imports C."""
        store.upsert_node(_record_id("FILE", "a.py"), "FILE", {"path": "a.py"})
        store.upsert_node(_record_id("FILE", "b.py"), "FILE", {"path": "b.py"})
        store.upsert_node(_record_id("FILE", "c.py"), "FILE", {"path": "c.py"})
        store.upsert_edge(
            _record_id("FILE", "a.py"),
            _record_id("FILE", "b.py"),
            "IMPORTS",
        )
        store.upsert_edge(
            _record_id("FILE", "b.py"),
            _record_id("FILE", "c.py"),
            "IMPORTS",
        )

    def test_evaluates_walk_query(self, tmp_path: Path) -> None:
        """Runner evaluates walk queries against the graph store."""
        store = SQLiteGraphStore(db_path=tmp_path / "test.db")
        self._populate_store(store)

        fixture = [
            {
                "id": "deps-a",
                "description": "What does a.py import?",
                "query_type": "walk",
                "params": {
                    "start_files": ["a.py"],
                    "direction": "outgoing",
                    "rel_allow": ["IMPORTS"],
                    "max_depth": 1,
                },
                "expected_files": ["b.py"],
            }
        ]
        fixture_path = tmp_path / "gt.json"
        fixture_path.write_text(json.dumps(fixture))

        bench = GraphBenchmark(
            store=store,
            ground_truth_path=fixture_path,
            output_dir=tmp_path / "out",
        )
        results = bench.run()
        assert len(results) == 1
        assert results[0].query_id == "deps-a"
        assert results[0].metrics.precision == 1.0
        assert results[0].metrics.recall == 1.0

    def test_depth_2_walk(self, tmp_path: Path) -> None:
        """Depth-2 walk from a.py finds both b.py and c.py."""
        store = SQLiteGraphStore(db_path=tmp_path / "test.db")
        self._populate_store(store)

        fixture = [
            {
                "id": "deep-deps-a",
                "description": "Transitive deps of a.py at depth 2",
                "query_type": "walk",
                "params": {
                    "start_files": ["a.py"],
                    "direction": "outgoing",
                    "rel_allow": ["IMPORTS"],
                    "max_depth": 2,
                },
                "expected_files": ["b.py", "c.py"],
            }
        ]
        fixture_path = tmp_path / "gt.json"
        fixture_path.write_text(json.dumps(fixture))

        bench = GraphBenchmark(
            store=store,
            ground_truth_path=fixture_path,
            output_dir=tmp_path / "out",
        )
        results = bench.run()
        assert results[0].metrics.recall == 1.0

    def test_writes_json_output(self, tmp_path: Path) -> None:
        """Runner writes results JSON to output directory."""
        store = SQLiteGraphStore(db_path=tmp_path / "test.db")
        self._populate_store(store)

        fixture = [
            {
                "id": "simple",
                "description": "test",
                "query_type": "walk",
                "params": {
                    "start_files": ["a.py"],
                    "direction": "outgoing",
                    "rel_allow": ["IMPORTS"],
                    "max_depth": 1,
                },
                "expected_files": ["b.py"],
            }
        ]
        fixture_path = tmp_path / "gt.json"
        fixture_path.write_text(json.dumps(fixture))

        out = tmp_path / "out"
        bench = GraphBenchmark(store=store, ground_truth_path=fixture_path, output_dir=out)
        bench.run()
        assert len(list(out.glob("graph_*.json"))) == 1
