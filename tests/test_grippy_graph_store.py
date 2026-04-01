# SPDX-License-Identifier: MIT
"""Tests for SQLiteGraphStore — schema, init, and pragma enforcement."""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from grippy.graph_store import SQLiteGraphStore
from grippy.graph_types import MissingNodeError


@pytest.fixture()
def store(tmp_path: Path) -> SQLiteGraphStore:
    return SQLiteGraphStore(db_path=tmp_path / "navi-graph.db")


class TestInit:
    def test_creates_db_file(self, tmp_path: Path) -> None:
        db_path = tmp_path / "navi-graph.db"
        SQLiteGraphStore(db_path=db_path)
        assert db_path.exists()

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        db_path = tmp_path / "subdir" / "deep" / "navi-graph.db"
        SQLiteGraphStore(db_path=db_path)
        assert db_path.exists()


class TestSchema:
    def test_nodes_table_columns(self, store: SQLiteGraphStore) -> None:
        cur = store._conn.cursor()
        cur.execute("PRAGMA table_info(nodes)")
        columns = {row[1] for row in cur.fetchall()}
        assert columns == {
            "id",
            "type",
            "data",
            "created_at",
            "updated_at",
            "accessed_at",
            "access_count",
        }

    def test_edges_table_columns(self, store: SQLiteGraphStore) -> None:
        cur = store._conn.cursor()
        cur.execute("PRAGMA table_info(edges)")
        columns = {row[1] for row in cur.fetchall()}
        assert columns == {
            "id",
            "source",
            "target",
            "relationship",
            "weight",
            "properties",
            "created_at",
            "updated_at",
        }

    def test_observations_table_columns(self, store: SQLiteGraphStore) -> None:
        cur = store._conn.cursor()
        cur.execute("PRAGMA table_info(observations)")
        columns = {row[1] for row in cur.fetchall()}
        assert columns == {
            "id",
            "node_id",
            "source",
            "kind",
            "content",
            "created_at",
        }

    def test_nodes_type_default(self, store: SQLiteGraphStore) -> None:
        """Node type defaults to 'node' if not specified."""
        cur = store._conn.cursor()
        cur.execute(
            "INSERT INTO nodes (id, data, created_at, updated_at, accessed_at) "
            "VALUES ('test', '{}', 0, 0, 0)"
        )
        cur.execute("SELECT type FROM nodes WHERE id = 'test'")
        assert cur.fetchone()[0] == "node"
        store._conn.rollback()

    def test_edge_weight_default(self, store: SQLiteGraphStore) -> None:
        """Edge weight defaults to 1.0."""
        cur = store._conn.cursor()
        # Need nodes for FK
        cur.execute(
            "INSERT INTO nodes (id, type, data, created_at, updated_at, accessed_at) "
            "VALUES ('a', 'FILE', '{}', 0, 0, 0)"
        )
        cur.execute(
            "INSERT INTO nodes (id, type, data, created_at, updated_at, accessed_at) "
            "VALUES ('b', 'FILE', '{}', 0, 0, 0)"
        )
        cur.execute(
            "INSERT INTO edges (id, source, target, relationship, properties, "
            "created_at, updated_at) VALUES ('e1', 'a', 'b', 'R', '{}', 0, 0)"
        )
        cur.execute("SELECT weight FROM edges WHERE id = 'e1'")
        assert cur.fetchone()[0] == 1.0
        store._conn.rollback()


class TestPragmas:
    def test_wal_mode(self, store: SQLiteGraphStore) -> None:
        cur = store._conn.cursor()
        cur.execute("PRAGMA journal_mode")
        assert cur.fetchone()[0] == "wal"

    def test_foreign_keys_on(self, store: SQLiteGraphStore) -> None:
        cur = store._conn.cursor()
        cur.execute("PRAGMA foreign_keys")
        assert cur.fetchone()[0] == 1

    def test_fk_cascade_works(self, store: SQLiteGraphStore) -> None:
        """Deleting a node cascades to its edges."""
        cur = store._conn.cursor()
        cur.execute(
            "INSERT INTO nodes (id, type, data, created_at, updated_at, accessed_at) "
            "VALUES ('a', 'F', '{}', 0, 0, 0)"
        )
        cur.execute(
            "INSERT INTO nodes (id, type, data, created_at, updated_at, accessed_at) "
            "VALUES ('b', 'F', '{}', 0, 0, 0)"
        )
        cur.execute(
            "INSERT INTO edges (id, source, target, relationship, properties, "
            "created_at, updated_at) VALUES ('e', 'a', 'b', 'R', '{}', 0, 0)"
        )
        store._conn.commit()

        cur.execute("DELETE FROM nodes WHERE id = 'a'")
        store._conn.commit()

        cur.execute("SELECT COUNT(*) FROM edges")
        assert cur.fetchone()[0] == 0

    def test_fk_rejects_orphan_edge(self, store: SQLiteGraphStore) -> None:
        """Inserting an edge with missing source/target raises IntegrityError."""
        cur = store._conn.cursor()
        with pytest.raises(sqlite3.IntegrityError):
            cur.execute(
                "INSERT INTO edges (id, source, target, relationship, properties, "
                "created_at, updated_at) VALUES ('e', 'missing', 'also_missing', 'R', '{}', 0, 0)"
            )


class TestIndexes:
    def test_expected_indexes_exist(self, store: SQLiteGraphStore) -> None:
        cur = store._conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='index'")
        index_names = {row[0] for row in cur.fetchall()}
        assert "idx_nodes_type" in index_names
        assert "idx_nodes_accessed_at" in index_names
        assert "idx_edges_src_rel_dst" in index_names
        assert "idx_edges_dst_rel_src" in index_names
        assert "idx_obs_node" in index_names


class TestIdempotentInit:
    def test_reopen_preserves_data(self, tmp_path: Path) -> None:
        """Opening the same DB twice preserves existing data."""
        db_path = tmp_path / "navi-graph.db"
        store1 = SQLiteGraphStore(db_path=db_path)
        store1._conn.execute(
            "INSERT INTO nodes (id, type, data, created_at, updated_at, accessed_at) "
            "VALUES ('n1', 'FILE', '{}', 0, 0, 0)"
        )
        store1._conn.commit()
        store1._conn.close()

        store2 = SQLiteGraphStore(db_path=db_path)
        cur = store2._conn.cursor()
        cur.execute("SELECT COUNT(*) FROM nodes")
        assert cur.fetchone()[0] == 1


# --- Write operation contracts ---


class TestUpsertNode:
    def test_insert_new_node(self, store: SQLiteGraphStore) -> None:
        store.upsert_node("FILE:abc", "FILE", {"path": "a.py"})
        node = store.get_node("FILE:abc")
        assert node is not None
        assert node.type == "FILE"
        assert node.data == {"path": "a.py"}

    def test_update_existing_preserves_created_at(self, store: SQLiteGraphStore) -> None:
        store.upsert_node("FILE:abc", "FILE", {"v": 1})
        node1 = store.get_node("FILE:abc")
        assert node1 is not None
        created = node1.created_at

        store.upsert_node("FILE:abc", "FILE", {"v": 2})
        node2 = store.get_node("FILE:abc")
        assert node2 is not None
        assert node2.created_at == created
        assert node2.data == {"v": 2}

    def test_idempotent(self, store: SQLiteGraphStore) -> None:
        store.upsert_node("FILE:abc", "FILE", {"x": 1})
        store.upsert_node("FILE:abc", "FILE", {"x": 1})
        cur = store._conn.cursor()
        cur.execute("SELECT COUNT(*) FROM nodes")
        assert cur.fetchone()[0] == 1

    def test_none_data_becomes_empty_dict(self, store: SQLiteGraphStore) -> None:
        store.upsert_node("FILE:abc", "FILE")
        node = store.get_node("FILE:abc")
        assert node is not None
        assert node.data == {}

    def test_canonical_json_in_db(self, store: SQLiteGraphStore) -> None:
        store.upsert_node("FILE:abc", "FILE", {"b": 2, "a": 1})
        cur = store._conn.cursor()
        cur.execute("SELECT data FROM nodes WHERE id = 'FILE:abc'")
        raw = cur.fetchone()[0]
        assert raw == '{"a":1,"b":2}'


class TestUpsertEdge:
    def test_insert_edge(self, store: SQLiteGraphStore) -> None:
        store.upsert_node("A:aaa", "FILE")
        store.upsert_node("B:bbb", "FILE")
        store.upsert_edge("A:aaa", "B:bbb", "IMPORTS")
        cur = store._conn.cursor()
        cur.execute("SELECT COUNT(*) FROM edges")
        assert cur.fetchone()[0] == 1

    def test_missing_source_raises(self, store: SQLiteGraphStore) -> None:
        store.upsert_node("B:bbb", "FILE")
        with pytest.raises(MissingNodeError, match="source"):
            store.upsert_edge("MISSING:xxx", "B:bbb", "IMPORTS")

    def test_missing_target_raises(self, store: SQLiteGraphStore) -> None:
        store.upsert_node("A:aaa", "FILE")
        with pytest.raises(MissingNodeError, match="target"):
            store.upsert_edge("A:aaa", "MISSING:xxx", "IMPORTS")

    def test_idempotent_upsert(self, store: SQLiteGraphStore) -> None:
        store.upsert_node("A:aaa", "FILE")
        store.upsert_node("B:bbb", "FILE")
        store.upsert_edge("A:aaa", "B:bbb", "IMPORTS", weight=0.5)
        store.upsert_edge("A:aaa", "B:bbb", "IMPORTS", weight=0.9)
        cur = store._conn.cursor()
        cur.execute("SELECT COUNT(*) FROM edges")
        assert cur.fetchone()[0] == 1
        cur.execute("SELECT weight FROM edges")
        assert cur.fetchone()[0] == 0.9  # updated

    def test_deterministic_edge_id(self, store: SQLiteGraphStore) -> None:
        store.upsert_node("A:aaa", "FILE")
        store.upsert_node("B:bbb", "FILE")
        store.upsert_edge("A:aaa", "B:bbb", "IMPORTS")
        cur = store._conn.cursor()
        cur.execute("SELECT id FROM edges")
        eid = cur.fetchone()[0]
        assert len(eid) == 64  # full sha256

    def test_edge_properties_canonical(self, store: SQLiteGraphStore) -> None:
        store.upsert_node("A:aaa", "FILE")
        store.upsert_node("B:bbb", "FILE")
        store.upsert_edge("A:aaa", "B:bbb", "IMPORTS", properties={"z": 1, "a": 2})
        cur = store._conn.cursor()
        cur.execute("SELECT properties FROM edges")
        assert cur.fetchone()[0] == '{"a":2,"z":1}'


class TestDeleteNode:
    def test_delete_existing(self, store: SQLiteGraphStore) -> None:
        store.upsert_node("A:aaa", "FILE")
        assert store.delete_node("A:aaa") is True
        assert store.get_node("A:aaa") is None

    def test_delete_nonexistent(self, store: SQLiteGraphStore) -> None:
        assert store.delete_node("NOPE:xxx") is False

    def test_cascade_deletes_edges(self, store: SQLiteGraphStore) -> None:
        store.upsert_node("A:aaa", "FILE")
        store.upsert_node("B:bbb", "FILE")
        store.upsert_edge("A:aaa", "B:bbb", "IMPORTS")
        store.delete_node("A:aaa")
        cur = store._conn.cursor()
        cur.execute("SELECT COUNT(*) FROM edges")
        assert cur.fetchone()[0] == 0


class TestDeleteEdge:
    def test_delete_existing(self, store: SQLiteGraphStore) -> None:
        store.upsert_node("A:aaa", "FILE")
        store.upsert_node("B:bbb", "FILE")
        store.upsert_edge("A:aaa", "B:bbb", "IMPORTS")
        assert store.delete_edge("A:aaa", "B:bbb", "IMPORTS") is True

    def test_delete_nonexistent(self, store: SQLiteGraphStore) -> None:
        assert store.delete_edge("A:a", "B:b", "R") is False


# --- Read operation contracts ---


class TestGetNode:
    def test_returns_none_for_missing(self, store: SQLiteGraphStore) -> None:
        assert store.get_node("NOPE:xxx") is None

    def test_touches_access_stats(self, store: SQLiteGraphStore) -> None:
        store.upsert_node("A:aaa", "FILE")
        node1 = store.get_node("A:aaa")
        assert node1 is not None
        count1 = node1.access_count

        node2 = store.get_node("A:aaa")
        assert node2 is not None
        assert node2.access_count == count1 + 1


class TestGetNodes:
    def test_batch_fetch(self, store: SQLiteGraphStore) -> None:
        store.upsert_node("A:aaa", "FILE")
        store.upsert_node("B:bbb", "FILE")
        nodes = store.get_nodes(["A:aaa", "B:bbb"])
        assert len(nodes) == 2

    def test_empty_ids(self, store: SQLiteGraphStore) -> None:
        assert store.get_nodes([]) == []

    def test_missing_ids_skipped(self, store: SQLiteGraphStore) -> None:
        store.upsert_node("A:aaa", "FILE")
        nodes = store.get_nodes(["A:aaa", "NOPE:xxx"])
        assert len(nodes) == 1


class TestGetRecentNodes:
    def test_ordered_by_recency(self, store: SQLiteGraphStore) -> None:
        store.upsert_node("A:aaa", "FILE")
        store.upsert_node("B:bbb", "FILE")
        # Force A to have an older accessed_at, then touch B so it's definitively newer
        store._conn.execute("UPDATE nodes SET accessed_at = 1000 WHERE id = 'A:aaa'")
        store._conn.execute("UPDATE nodes SET accessed_at = 2000 WHERE id = 'B:bbb'")
        store._conn.commit()
        recent = store.get_recent_nodes(limit=2)
        assert recent[0].id == "B:bbb"

    def test_type_filter(self, store: SQLiteGraphStore) -> None:
        store.upsert_node("A:aaa", "FILE")
        store.upsert_node("B:bbb", "REVIEW")
        recent = store.get_recent_nodes(limit=10, types=["FILE"])
        assert len(recent) == 1
        assert recent[0].type == "FILE"


# --- Neighbor contracts ---


class TestNeighbors:
    def _build_chain(self, store: SQLiteGraphStore) -> None:
        """A --IMPORTS--> B --IMPORTS--> C"""
        store.upsert_node("A:aaa", "FILE")
        store.upsert_node("B:bbb", "FILE")
        store.upsert_node("C:ccc", "FILE")
        store.upsert_edge("A:aaa", "B:bbb", "IMPORTS")
        store.upsert_edge("B:bbb", "C:ccc", "IMPORTS")

    def test_outgoing(self, store: SQLiteGraphStore) -> None:
        self._build_chain(store)
        nb = store.neighbors("A:aaa", direction="outgoing")
        assert len(nb.outgoing) == 1
        assert nb.outgoing[0][1].id == "B:bbb"
        assert nb.incoming == []

    def test_incoming(self, store: SQLiteGraphStore) -> None:
        self._build_chain(store)
        nb = store.neighbors("B:bbb", direction="incoming")
        assert len(nb.incoming) == 1
        assert nb.incoming[0][1].id == "A:aaa"
        assert nb.outgoing == []

    def test_both(self, store: SQLiteGraphStore) -> None:
        self._build_chain(store)
        nb = store.neighbors("B:bbb", direction="both")
        assert len(nb.incoming) == 1
        assert len(nb.outgoing) == 1

    def test_rel_filter(self, store: SQLiteGraphStore) -> None:
        store.upsert_node("A:aaa", "FILE")
        store.upsert_node("B:bbb", "FILE")
        store.upsert_edge("A:aaa", "B:bbb", "IMPORTS")
        store.upsert_edge("A:aaa", "B:bbb", "TOUCHED")
        nb = store.neighbors("A:aaa", direction="outgoing", rel_filter=["IMPORTS"])
        assert len(nb.outgoing) == 1
        assert nb.outgoing[0][0].relationship == "IMPORTS"

    def test_deterministic_order(self, store: SQLiteGraphStore) -> None:
        """Neighbors sorted by (relationship ASC, target ASC)."""
        store.upsert_node("A:aaa", "FILE")
        store.upsert_node("B:bbb", "FILE")
        store.upsert_node("C:ccc", "FILE")
        store.upsert_node("D:ddd", "FILE")
        # Insert in non-sorted order
        store.upsert_edge("A:aaa", "D:ddd", "IMPORTS")
        store.upsert_edge("A:aaa", "B:bbb", "IMPORTS")
        store.upsert_edge("A:aaa", "C:ccc", "AUTHORED")  # A < I alphabetically
        nb = store.neighbors("A:aaa", direction="outgoing")
        rels = [(e.relationship, e.target) for e, _ in nb.outgoing]
        assert rels == [
            ("AUTHORED", "C:ccc"),
            ("IMPORTS", "B:bbb"),
            ("IMPORTS", "D:ddd"),
        ]

    def test_limit(self, store: SQLiteGraphStore) -> None:
        store.upsert_node("A:aaa", "FILE")
        for i in range(10):
            nid = f"N:{i:012d}"
            store.upsert_node(nid, "FILE")
            store.upsert_edge("A:aaa", nid, "IMPORTS")
        nb = store.neighbors("A:aaa", direction="outgoing", limit=3)
        assert len(nb.outgoing) == 3


# --- Traversal contracts ---


class TestWalk:
    def _build_tree(self, store: SQLiteGraphStore) -> None:
        """A -> B -> C -> D (linear chain)."""
        for nid in ["A:aaa", "B:bbb", "C:ccc", "D:ddd"]:
            store.upsert_node(nid, "FILE")
        store.upsert_edge("A:aaa", "B:bbb", "IMPORTS")
        store.upsert_edge("B:bbb", "C:ccc", "IMPORTS")
        store.upsert_edge("C:ccc", "D:ddd", "IMPORTS")

    def test_basic_walk(self, store: SQLiteGraphStore) -> None:
        self._build_tree(store)
        result = store.walk(["A:aaa"], max_depth=3, max_nodes=50)
        assert len(result.nodes) == 4
        assert result.receipt.truncated is False

    def test_depth_limit(self, store: SQLiteGraphStore) -> None:
        self._build_tree(store)
        result = store.walk(["A:aaa"], max_depth=1, max_nodes=50)
        node_ids = {n.id for n in result.nodes}
        assert "A:aaa" in node_ids
        assert "B:bbb" in node_ids
        assert "C:ccc" not in node_ids

    def test_node_limit_truncates(self, store: SQLiteGraphStore) -> None:
        self._build_tree(store)
        result = store.walk(["A:aaa"], max_depth=10, max_nodes=2)
        assert len(result.nodes) == 2
        assert result.receipt.truncated is True
        assert result.receipt.reason == "max_nodes"

    def test_edge_limit_truncates(self, store: SQLiteGraphStore) -> None:
        self._build_tree(store)
        result = store.walk(["A:aaa"], max_depth=10, max_nodes=50, max_edges=1)
        assert result.receipt.truncated is True
        assert result.receipt.reason == "max_edges"

    def test_rel_allow_filter(self, store: SQLiteGraphStore) -> None:
        store.upsert_node("A:aaa", "FILE")
        store.upsert_node("B:bbb", "FILE")
        store.upsert_node("C:ccc", "FILE")
        store.upsert_edge("A:aaa", "B:bbb", "IMPORTS")
        store.upsert_edge("A:aaa", "C:ccc", "TOUCHED")
        result = store.walk(["A:aaa"], rel_allow=["IMPORTS"])
        node_ids = {n.id for n in result.nodes}
        assert "B:bbb" in node_ids
        assert "C:ccc" not in node_ids

    def test_cycle_prevention(self, store: SQLiteGraphStore) -> None:
        store.upsert_node("A:aaa", "FILE")
        store.upsert_node("B:bbb", "FILE")
        store.upsert_edge("A:aaa", "B:bbb", "IMPORTS")
        store.upsert_edge("B:bbb", "A:aaa", "IMPORTS")
        result = store.walk(["A:aaa"], max_depth=10, max_nodes=50)
        assert len(result.nodes) == 2  # not infinite

    def test_multiple_start_nodes(self, store: SQLiteGraphStore) -> None:
        store.upsert_node("A:aaa", "FILE")
        store.upsert_node("B:bbb", "FILE")
        store.upsert_node("C:ccc", "FILE")
        store.upsert_edge("A:aaa", "C:ccc", "IMPORTS")
        store.upsert_edge("B:bbb", "C:ccc", "IMPORTS")
        result = store.walk(["A:aaa", "B:bbb"])
        assert len(result.nodes) == 3

    def test_start_order_preserved(self, store: SQLiteGraphStore) -> None:
        """Start nodes processed in caller order."""
        store.upsert_node("B:bbb", "FILE")
        store.upsert_node("A:aaa", "FILE")
        result = store.walk(["B:bbb", "A:aaa"], max_depth=0)
        assert result.nodes[0].id == "B:bbb"
        assert result.nodes[1].id == "A:aaa"

    def test_node_type_filter(self, store: SQLiteGraphStore) -> None:
        store.upsert_node("A:aaa", "FILE")
        store.upsert_node("B:bbb", "REVIEW")
        store.upsert_edge("A:aaa", "B:bbb", "TOUCHED")
        result = store.walk(["A:aaa"], node_type_filter=["FILE"])
        node_ids = {n.id for n in result.nodes}
        assert "A:aaa" in node_ids
        assert "B:bbb" not in node_ids

    def test_receipt_metadata(self, store: SQLiteGraphStore) -> None:
        self._build_tree(store)
        result = store.walk(["A:aaa"], max_depth=2)
        assert result.receipt.visited_nodes == 3  # A, B, C
        assert result.receipt.visited_edges >= 2
        assert result.receipt.max_depth_reached == 2

    def test_batch_touch_after_walk(self, store: SQLiteGraphStore) -> None:
        """Walk batch-touches all visited nodes."""
        self._build_tree(store)
        # Record initial access counts
        initial = store._get_node_readonly("A:aaa")
        assert initial is not None
        initial_count = initial.access_count

        store.walk(["A:aaa"], max_depth=1)

        updated = store._get_node_readonly("A:aaa")
        assert updated is not None
        assert updated.access_count == initial_count + 1

    def test_empty_start(self, store: SQLiteGraphStore) -> None:
        result = store.walk([])
        assert result.nodes == []
        assert result.receipt.truncated is False

    def test_missing_start_node(self, store: SQLiteGraphStore) -> None:
        result = store.walk(["NOPE:xxx"])
        assert result.nodes == []

    def test_incoming_direction(self, store: SQLiteGraphStore) -> None:
        """walk(direction='incoming') follows target->source."""
        self._build_tree(store)
        # D is the leaf — walk incoming from D should find C, B, A
        result = store.walk(["D:ddd"], max_depth=3, direction="incoming")
        node_ids = {n.id for n in result.nodes}
        assert "D:ddd" in node_ids
        assert "C:ccc" in node_ids
        assert "B:bbb" in node_ids
        assert "A:aaa" in node_ids

    def test_incoming_depth_limit(self, store: SQLiteGraphStore) -> None:
        self._build_tree(store)
        result = store.walk(["D:ddd"], max_depth=1, direction="incoming")
        node_ids = {n.id for n in result.nodes}
        assert "D:ddd" in node_ids
        assert "C:ccc" in node_ids
        assert "B:bbb" not in node_ids


# --- Subgraph contracts ---


class TestSubgraph:
    def test_induced_subgraph(self, store: SQLiteGraphStore) -> None:
        """Returns nodes + all edges where both endpoints in set."""
        for nid in ["A:aaa", "B:bbb", "C:ccc"]:
            store.upsert_node(nid, "FILE")
        store.upsert_edge("A:aaa", "B:bbb", "IMPORTS")
        store.upsert_edge("B:bbb", "C:ccc", "IMPORTS")
        store.upsert_edge("A:aaa", "C:ccc", "TOUCHED")

        # Subgraph of A and B — should include A->B edge but not B->C or A->C
        sg = store.subgraph(["A:aaa", "B:bbb"])
        assert len(sg.nodes) == 2
        assert len(sg.edges) == 1
        assert sg.edges[0].relationship == "IMPORTS"

    def test_deterministic_node_order(self, store: SQLiteGraphStore) -> None:
        """Nodes sorted by id ASC."""
        store.upsert_node("C:ccc", "FILE")
        store.upsert_node("A:aaa", "FILE")
        store.upsert_node("B:bbb", "FILE")
        sg = store.subgraph(["C:ccc", "A:aaa", "B:bbb"])
        ids = [n.id for n in sg.nodes]
        assert ids == sorted(ids)

    def test_empty_input(self, store: SQLiteGraphStore) -> None:
        sg = store.subgraph([])
        assert sg.nodes == []
        assert sg.edges == []

    def test_missing_nodes_skipped(self, store: SQLiteGraphStore) -> None:
        store.upsert_node("A:aaa", "FILE")
        sg = store.subgraph(["A:aaa", "NOPE:xxx"])
        assert len(sg.nodes) == 1


# --- Observation contracts ---


class TestObservations:
    def test_add_and_get(self, store: SQLiteGraphStore) -> None:
        store.upsert_node("A:aaa", "FILE")
        added = store.add_observations(
            "A:aaa",
            ["PR #42: score 72"],
            source="pipeline",
            kind="history",
        )
        assert added == ["PR #42: score 72"]
        obs = store.get_observations("A:aaa")
        assert obs == ["PR #42: score 72"]

    def test_dedup_same_source(self, store: SQLiteGraphStore) -> None:
        """UNIQUE(node_id, source, content) prevents duplicates."""
        store.upsert_node("A:aaa", "FILE")
        store.add_observations(
            "A:aaa",
            ["fact1"],
            source="pipeline",
            kind="history",
        )
        added = store.add_observations(
            "A:aaa",
            ["fact1"],
            source="pipeline",
            kind="history",
        )
        assert added == []  # already exists
        assert len(store.get_observations("A:aaa")) == 1

    def test_different_sources_both_stored(self, store: SQLiteGraphStore) -> None:
        """Same content from different sources = both stored."""
        store.upsert_node("A:aaa", "FILE")
        store.add_observations(
            "A:aaa",
            ["shared fact"],
            source="pipeline",
            kind="history",
        )
        store.add_observations(
            "A:aaa",
            ["shared fact"],
            source="llm",
            kind="note",
        )
        assert len(store.get_observations("A:aaa")) == 2

    def test_missing_node_raises(self, store: SQLiteGraphStore) -> None:
        with pytest.raises(MissingNodeError):
            store.add_observations(
                "NOPE:xxx",
                ["fact"],
                source="pipeline",
                kind="history",
            )

    def test_max_length_enforced(self, store: SQLiteGraphStore) -> None:
        store.upsert_node("A:aaa", "FILE")
        with pytest.raises(ValueError, match="too long"):
            store.add_observations(
                "A:aaa",
                ["x" * 501],
                source="pipeline",
                kind="history",
            )

    def test_cascade_delete(self, store: SQLiteGraphStore) -> None:
        store.upsert_node("A:aaa", "FILE")
        store.add_observations(
            "A:aaa",
            ["fact1"],
            source="pipeline",
            kind="history",
        )
        store.delete_node("A:aaa")
        # Observations should be gone (FK cascade)
        cur = store._conn.execute("SELECT COUNT(*) FROM observations")
        assert cur.fetchone()[0] == 0

    def test_delete_specific(self, store: SQLiteGraphStore) -> None:
        store.upsert_node("A:aaa", "FILE")
        store.add_observations(
            "A:aaa",
            ["fact1", "fact2"],
            source="pipeline",
            kind="history",
        )
        store.delete_observations("A:aaa", ["fact1"])
        assert store.get_observations("A:aaa") == ["fact2"]

    def test_ordered_by_creation(self, store: SQLiteGraphStore) -> None:
        """Observations ordered by (created_at ASC, id ASC)."""
        store.upsert_node("A:aaa", "FILE")
        # Insert with small time gaps to avoid same-timestamp flakiness
        # Even if timestamps collide, id ASC (autoincrement) is the tiebreaker
        store.add_observations(
            "A:aaa",
            ["first", "second", "third"],
            source="pipeline",
            kind="history",
        )
        obs = store.get_observations("A:aaa")
        assert obs == ["first", "second", "third"]

    def test_filter_by_source(self, store: SQLiteGraphStore) -> None:
        store.upsert_node("A:aaa", "FILE")
        store.add_observations(
            "A:aaa",
            ["from pipeline"],
            source="pipeline",
            kind="history",
        )
        store.add_observations(
            "A:aaa",
            ["from llm"],
            source="llm",
            kind="note",
        )
        assert store.get_observations("A:aaa", source="pipeline") == ["from pipeline"]
        assert store.get_observations("A:aaa", source="llm") == ["from llm"]

    def test_filter_by_kind(self, store: SQLiteGraphStore) -> None:
        store.upsert_node("A:aaa", "FILE")
        store.add_observations(
            "A:aaa",
            ["metric1"],
            source="pipeline",
            kind="metric",
        )
        store.add_observations(
            "A:aaa",
            ["tag1"],
            source="pipeline",
            kind="tag",
        )
        assert store.get_observations("A:aaa", kind="metric") == ["metric1"]
        assert store.get_observations("A:aaa", kind="tag") == ["tag1"]

    def test_normalization_dedup(self, store: SQLiteGraphStore) -> None:
        """Whitespace-different strings normalize to same content = dedup."""
        store.upsert_node("A:aaa", "FILE")
        store.add_observations(
            "A:aaa",
            ["PR #42: score 72"],
            source="pipeline",
            kind="history",
        )
        added = store.add_observations(
            "A:aaa",
            ["  PR #42:  score  72  "],
            source="pipeline",
            kind="history",
        )
        assert added == []  # normalized to same string, deduped
        assert len(store.get_observations("A:aaa")) == 1

    def test_empty_after_normalization_skipped(self, store: SQLiteGraphStore) -> None:
        """Whitespace-only observations are silently skipped."""
        store.upsert_node("A:aaa", "FILE")
        added = store.add_observations(
            "A:aaa",
            ["   ", "real fact"],
            source="pipeline",
            kind="history",
        )
        assert added == ["real fact"]
        assert store.get_observations("A:aaa") == ["real fact"]


# --- Edge cases ---


class TestEdgeCases:
    def test_walk_max_edges_inner_truncation(self, store: SQLiteGraphStore) -> None:
        """Walk truncates when inner edge loop hits max_edges mid-expansion.

        A has 3 outgoing edges. With max_edges=2, the inner for-loop
        breaks after collecting 2 edges (lines 430-433), then the
        outer while loop breaks via `if truncated` (line 440-441).
        """
        store.upsert_node("A:aaa", "FILE")
        for label in ["B:bbb", "C:ccc", "D:ddd"]:
            store.upsert_node(label, "FILE")
            store.upsert_edge("A:aaa", label, "IMPORTS")
        result = store.walk(["A:aaa"], max_depth=3, max_nodes=100, max_edges=2)
        assert result.receipt.truncated is True
        assert result.receipt.reason == "max_edges"
        assert len(result.edges) == 2

    def test_walk_max_depth_does_not_explore_beyond(self, store: SQLiteGraphStore) -> None:
        """Walk at max_depth visits boundary nodes but does not expand them.

        Exercises the `depth >= max_depth: continue` path (line 424-425)
        and the post-loop max_depth check (line 447).
        """
        for nid in ["A:aaa", "B:bbb", "C:ccc", "D:ddd"]:
            store.upsert_node(nid, "FILE")
        store.upsert_edge("A:aaa", "B:bbb", "IMPORTS")
        store.upsert_edge("B:bbb", "C:ccc", "IMPORTS")
        store.upsert_edge("C:ccc", "D:ddd", "IMPORTS")
        result = store.walk(["A:aaa"], max_depth=1, max_nodes=100, max_edges=200)
        node_ids = {n.id for n in result.nodes}
        # A (depth 0) and B (depth 1) are visited; C, D are not
        assert "A:aaa" in node_ids
        assert "B:bbb" in node_ids
        assert "C:ccc" not in node_ids
        assert result.receipt.max_depth_reached == 1
        # BFS drains the queue fully — no truncation from depth alone
        assert result.receipt.truncated is False

    def test_delete_observations_empty_list(self, store: SQLiteGraphStore) -> None:
        """delete_observations with empty list is a no-op."""
        store.upsert_node("A:aaa", "FILE")
        store.add_observations("A:aaa", ["keep me"], source="pipeline", kind="history")
        store.delete_observations("A:aaa", [])
        assert store.get_observations("A:aaa") == ["keep me"]

    def test_pragma_mismatch_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Pragma mismatch logs a warning but init still succeeds.

        Patches _PRAGMAS so the expected value doesn't match what SQLite returns,
        triggering the mismatch warning on lines 114-119.
        """
        fake_pragmas = [
            # synchronous returns "1" (NORMAL) — expect "999" to force mismatch
            ("PRAGMA synchronous = NORMAL", "PRAGMA synchronous", "999"),
            ("PRAGMA journal_mode = WAL", "PRAGMA journal_mode", "wal"),
            ("PRAGMA foreign_keys = ON", "PRAGMA foreign_keys", "1"),
        ]
        with caplog.at_level(logging.WARNING, logger="grippy.graph_store"):
            with patch("grippy.graph_store._PRAGMAS", fake_pragmas):
                SQLiteGraphStore(db_path=tmp_path / "warn.db")
        assert any("expected" in r.message for r in caplog.records)

    def test_pragma_operational_error(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """OperationalError during pragma is caught and logged.

        Patches _PRAGMAS to include a malformed SQL statement,
        triggering the OperationalError handler on lines 120-121.
        """
        fake_pragmas = [
            # Malformed SQL triggers OperationalError
            ("NOT_SQL bad", "PRAGMA journal_mode", None),
            ("PRAGMA foreign_keys = ON", "PRAGMA foreign_keys", "1"),
        ]
        with caplog.at_level(logging.WARNING, logger="grippy.graph_store"):
            with patch("grippy.graph_store._PRAGMAS", fake_pragmas):
                SQLiteGraphStore(db_path=tmp_path / "operr.db")
        assert any("not supported" in r.message.lower() for r in caplog.records)


# --- Concurrent access (IN-S01) ---


class TestConcurrentAccess:
    """Verify WAL mode enables concurrent reads during writes.

    Uses separate SQLiteGraphStore instances on the same DB path — essential
    because a shared-connection test only proves Python/SQLite thread locking,
    not WAL behavior across independent connections.
    """

    def test_concurrent_reads_during_write(self, tmp_path: Path) -> None:
        """Writer inserts nodes while reader queries concurrently. No OperationalError.

        Store instances are created inside their respective threads because
        SQLite connections are thread-bound by default. This tests true WAL
        concurrency: two independent connections to the same DB file.
        """
        db_path = tmp_path / "concurrent.db"
        # Pre-create the DB so both threads can open it
        SQLiteGraphStore(db_path=db_path)

        errors: list[Exception] = []
        write_started = threading.Event()
        node_count = 50

        def writer_thread() -> None:
            try:
                writer = SQLiteGraphStore(db_path=db_path)
                for i in range(node_count):
                    writer.upsert_node(f"N:{i:06d}", "FILE", {"idx": i})
                    if i == 5:
                        write_started.set()
            except Exception as e:
                errors.append(e)
            finally:
                write_started.set()  # ensure reader unblocks even on error

        def reader_thread() -> None:
            write_started.wait(timeout=5)
            try:
                reader = SQLiteGraphStore(db_path=db_path)
                for _ in range(20):
                    reader.get_recent_nodes(limit=10)
                    reader.neighbors("N:000000", direction="outgoing")
            except Exception as e:
                errors.append(e)

        t_write = threading.Thread(target=writer_thread)
        t_read = threading.Thread(target=reader_thread)
        t_write.start()
        t_read.start()
        t_write.join(timeout=10)
        t_read.join(timeout=10)

        assert not errors, f"Concurrent access errors: {errors}"
        # Verify all nodes were written (check from main thread)
        checker = SQLiteGraphStore(db_path=db_path)
        nodes = checker.get_recent_nodes(limit=node_count + 10)
        assert len(nodes) == node_count


# --- Data encoding edge cases (KRC-01) ---


class TestDataEncodingEdgeCases:
    """Verify graph store handles non-ASCII and unusual data safely."""

    def test_unicode_in_node_data(self, store: SQLiteGraphStore) -> None:
        """Unicode content in node data round-trips correctly."""
        data = {"path": "src/日本語.py", "desc": "emoji 🔒 and CJK 漢字"}
        store.upsert_node("FILE:unicode", "FILE", data)
        node = store.get_node("FILE:unicode")
        assert node is not None
        assert node.data["path"] == "src/日本語.py"
        assert "🔒" in node.data["desc"]

    def test_unicode_in_observation_content(self, store: SQLiteGraphStore) -> None:
        """Observations with non-ASCII content stored and retrieved."""
        store.upsert_node("FILE:obs", "FILE")
        added = store.add_observations(
            "FILE:obs",
            ["PR #1: fixed ñ-handling — résumé upload"],
            source="pipeline",
            kind="history",
        )
        assert len(added) == 1
        obs = store.get_observations("FILE:obs")
        assert "ñ" in obs[0]
        assert "résumé" in obs[0]

    def test_special_chars_in_edge_properties(self, store: SQLiteGraphStore) -> None:
        """Edge properties with quotes, backslashes, newlines survive JSON round-trip."""
        store.upsert_node("A:aaa", "FILE")
        store.upsert_node("B:bbb", "FILE")
        props = {"note": 'path with "quotes" and \\backslash', "multi": "line\nbreak"}
        store.upsert_edge("A:aaa", "B:bbb", "IMPORTS", properties=props)
        cur = store._conn.cursor()
        cur.execute("SELECT properties FROM edges")
        raw = cur.fetchone()[0]
        restored = json.loads(raw)
        assert restored["note"] == props["note"]
        assert restored["multi"] == props["multi"]

    def test_empty_string_node_type(self, store: SQLiteGraphStore) -> None:
        """Empty string node type is accepted (schema has DEFAULT 'node')."""
        store.upsert_node("TEST:empty-type", "", {"x": 1})
        node = store.get_node("TEST:empty-type")
        assert node is not None
