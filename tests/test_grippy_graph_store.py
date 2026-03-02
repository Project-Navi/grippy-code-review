# SPDX-License-Identifier: MIT
"""Tests for SQLiteGraphStore — schema, init, and pragma enforcement."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from grippy.graph_store import SQLiteGraphStore


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
