# SPDX-License-Identifier: MIT
"""Tests for graph context builder (pre-review context pack)."""

from __future__ import annotations

from pathlib import Path

import pytest

from grippy.graph_context import build_context_pack, format_context_for_llm
from grippy.graph_store import SQLiteGraphStore
from grippy.graph_types import _record_id


@pytest.fixture()
def store(tmp_path: Path) -> SQLiteGraphStore:
    return SQLiteGraphStore(db_path=tmp_path / "navi-graph.db")


class TestBuildContextPack:
    def test_empty_graph(self, store: SQLiteGraphStore) -> None:
        pack = build_context_pack(store, touched_files=["src/app.py"])
        assert pack.touched_files == ["src/app.py"]
        assert pack.blast_radius_files == []
        assert pack.recurring_findings == []

    def test_blast_radius(self, store: SQLiteGraphStore) -> None:
        fid_a = _record_id("FILE", "src/a.py")
        fid_b = _record_id("FILE", "src/b.py")
        store.upsert_node(fid_a, "FILE", {"path": "src/a.py"})
        store.upsert_node(fid_b, "FILE", {"path": "src/b.py"})
        # b imports a
        store.upsert_edge(fid_b, fid_a, "IMPORTS")
        pack = build_context_pack(store, touched_files=["src/a.py"])
        assert len(pack.blast_radius_files) >= 1

    def test_recurring_findings(self, store: SQLiteGraphStore) -> None:
        fid = _record_id("FILE", "src/a.py")
        finding_id = _record_id("FINDING", "review1", "F-001")
        store.upsert_node(fid, "FILE", {"path": "src/a.py"})
        store.upsert_node(
            finding_id,
            "FINDING",
            {
                "fingerprint": "abc123",
                "severity": "HIGH",
            },
        )
        store.upsert_edge(finding_id, fid, "FOUND_IN")
        pack = build_context_pack(store, touched_files=["src/a.py"])
        assert len(pack.recurring_findings) >= 1


class TestFormatContext:
    def test_empty_pack(self, store: SQLiteGraphStore) -> None:
        pack = build_context_pack(store, touched_files=[])
        text = format_context_for_llm(pack)
        assert text == ""

    def test_max_length(self, store: SQLiteGraphStore) -> None:
        pack = build_context_pack(store, touched_files=["a.py"])
        text = format_context_for_llm(pack, max_chars=2000)
        assert len(text) <= 2000
