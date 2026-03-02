# SPDX-License-Identifier: MIT
"""SQLiteGraphStore — navi-graph-shaped graph persistence.

Deterministic, bounded, audit-grade SQLite graph store. Matches the
navi-graph schema for future extraction to Cloudflare D1.

No vectors — those stay in CodebaseIndex (codebase.py).
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections import deque
from pathlib import Path
from typing import Any, Literal

from grippy.graph_types import (
    MAX_OBSERVATION_LENGTH,
    GraphEdge,
    GraphNode,
    MissingNodeError,
    NeighborResult,
    SubgraphResult,
    TraversalReceipt,
    TraversalResult,
    _canonical_json,
    _edge_id,
    _normalize_observation,
    _now_ms,
)

log = logging.getLogger(__name__)

# --- SQLite schema ---

_PRAGMAS: list[tuple[str, str, str | None]] = [
    # (set_statement, read_statement, expected_value_or_None_for_best_effort)
    ("PRAGMA journal_mode = WAL", "PRAGMA journal_mode", "wal"),
    ("PRAGMA foreign_keys = ON", "PRAGMA foreign_keys", "1"),
    ("PRAGMA busy_timeout = 5000", "PRAGMA busy_timeout", None),
    ("PRAGMA synchronous = NORMAL", "PRAGMA synchronous", None),
    ("PRAGMA temp_store = MEMORY", "PRAGMA temp_store", None),
    ("PRAGMA cache_size = -20000", "PRAGMA cache_size", None),
]

_NODES_TABLE = """
CREATE TABLE IF NOT EXISTS nodes (
    id           TEXT PRIMARY KEY,
    type         TEXT NOT NULL DEFAULT 'node',
    data         TEXT NOT NULL DEFAULT '{}',
    created_at   INTEGER NOT NULL,
    updated_at   INTEGER NOT NULL,
    accessed_at  INTEGER NOT NULL,
    access_count INTEGER NOT NULL DEFAULT 1
)
"""

_EDGES_TABLE = """
CREATE TABLE IF NOT EXISTS edges (
    id           TEXT PRIMARY KEY,
    source       TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    target       TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    relationship TEXT NOT NULL,
    weight       REAL NOT NULL DEFAULT 1.0,
    properties   TEXT NOT NULL DEFAULT '{}',
    created_at   INTEGER NOT NULL,
    updated_at   INTEGER NOT NULL,
    UNIQUE(source, relationship, target)
)
"""

_OBSERVATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS observations (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id    TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    source     TEXT NOT NULL,
    kind       TEXT NOT NULL,
    content    TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    UNIQUE(node_id, source, content)
)
"""

_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_nodes_type        ON nodes(type)",
    "CREATE INDEX IF NOT EXISTS idx_nodes_accessed_at ON nodes(accessed_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_edges_src_rel_dst ON edges(source, relationship, target)",
    "CREATE INDEX IF NOT EXISTS idx_edges_dst_rel_src ON edges(target, relationship, source)",
    "CREATE INDEX IF NOT EXISTS idx_obs_node          ON observations(node_id)",
]


class SQLiteGraphStore:
    """Navi-graph-shaped SQLite graph store."""

    def __init__(self, *, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        cur = self._conn.cursor()
        for set_stmt, read_stmt, expected in _PRAGMAS:
            try:
                cur.execute(set_stmt)
                cur.execute(read_stmt)
                actual = str(cur.fetchone()[0])
                log.debug("Pragma %s = %s", read_stmt, actual)
                if expected is not None and actual != expected:
                    log.warning(
                        "Pragma %s: expected %s, got %s",
                        read_stmt,
                        expected,
                        actual,
                    )
            except sqlite3.OperationalError:
                log.warning("Pragma not supported: %s", set_stmt)
        cur.execute(_NODES_TABLE)
        cur.execute(_EDGES_TABLE)
        cur.execute(_OBSERVATIONS_TABLE)
        for idx in _INDEXES:
            cur.execute(idx)
        self._conn.commit()

    # --- Helpers ---

    @staticmethod
    def _row_to_node(row: sqlite3.Row) -> GraphNode:
        return GraphNode(
            id=row["id"],
            type=row["type"],
            data=json.loads(row["data"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            accessed_at=row["accessed_at"],
            access_count=row["access_count"],
        )

    @staticmethod
    def _row_to_edge(row: sqlite3.Row) -> GraphEdge:
        return GraphEdge(
            id=row["id"],
            source=row["source"],
            target=row["target"],
            relationship=row["relationship"],
            weight=row["weight"],
            properties=json.loads(row["properties"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # --- Write ops (idempotent) ---

    def upsert_node(
        self,
        id: str,
        type: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Insert or update a node. Preserves created_at on update.

        Transaction: atomic — single INSERT OR UPDATE.
        """
        now = _now_ms()
        data_json = _canonical_json(data or {})
        with self._conn:
            self._conn.execute(
                """INSERT INTO nodes (id, type, data, created_at, updated_at, accessed_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    type = excluded.type,
                    data = excluded.data,
                    updated_at = excluded.updated_at""",
                (id, type, data_json, now, now, now),
            )

    def upsert_edge(
        self,
        source: str,
        target: str,
        relationship: str,
        weight: float = 1.0,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Insert or update an edge. Raises MissingNodeError if nodes absent.

        Transaction: atomic — check + upsert in same transaction.
        MissingNodeError raised BEFORE any write, so no partial state.
        """
        cur = self._conn.cursor()
        cur.execute("SELECT id FROM nodes WHERE id = ?", (source,))
        if cur.fetchone() is None:
            raise MissingNodeError(source, "source")
        cur.execute("SELECT id FROM nodes WHERE id = ?", (target,))
        if cur.fetchone() is None:
            raise MissingNodeError(target, "target")

        now = _now_ms()
        eid = _edge_id(source, relationship, target)
        props_json = _canonical_json(properties or {})
        with self._conn:
            self._conn.execute(
                """INSERT INTO edges (id, source, target, relationship, weight, properties,
                created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source, relationship, target) DO UPDATE SET
                    weight = excluded.weight,
                    properties = excluded.properties,
                    updated_at = excluded.updated_at""",
                (eid, source, target, relationship, weight, props_json, now, now),
            )

    def delete_node(self, id: str) -> bool:
        """Delete a node and cascade its edges. Returns True if existed."""
        with self._conn:
            cur = self._conn.execute("DELETE FROM nodes WHERE id = ?", (id,))
        return cur.rowcount > 0

    def delete_edge(self, source: str, target: str, relationship: str) -> bool:
        """Delete an edge by canonical triple. Returns True if existed."""
        eid = _edge_id(source, relationship, target)
        with self._conn:
            cur = self._conn.execute("DELETE FROM edges WHERE id = ?", (eid,))
        return cur.rowcount > 0

    # --- Read ops ---

    def get_node(self, id: str) -> GraphNode | None:
        """Fetch a node by ID. Touches accessed_at and access_count.

        Transaction: read is outside transaction, touch is atomic.
        Separate intentionally — reads don't need a write lock.
        """
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM nodes WHERE id = ?", (id,))
        row = cur.fetchone()
        if row is None:
            return None
        now = _now_ms()
        with self._conn:
            self._conn.execute(
                "UPDATE nodes SET accessed_at = ?, access_count = access_count + 1 WHERE id = ?",
                (now, id),
            )
        return self._row_to_node(row)

    def get_nodes(self, ids: list[str]) -> list[GraphNode]:
        """Batch fetch nodes. Touches access stats for each.

        Transaction: read outside, batch touch atomic.
        """
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        cur = self._conn.cursor()
        cur.execute(
            f"SELECT * FROM nodes WHERE id IN ({placeholders})",
            ids,
        )
        rows = cur.fetchall()
        if rows:
            now = _now_ms()
            with self._conn:
                self._conn.execute(
                    "UPDATE nodes SET accessed_at = ?, access_count = access_count + 1 "
                    f"WHERE id IN ({placeholders})",
                    [now, *ids],
                )
        return [self._row_to_node(r) for r in rows]

    def get_recent_nodes(
        self,
        limit: int = 10,
        types: list[str] | None = None,
    ) -> list[GraphNode]:
        """Most recently accessed nodes, ordered by accessed_at DESC."""
        if types:
            placeholders = ",".join("?" for _ in types)
            cur = self._conn.execute(
                f"SELECT * FROM nodes WHERE type IN ({placeholders}) "
                "ORDER BY accessed_at DESC LIMIT ?",
                [*types, limit],
            )
        else:
            cur = self._conn.execute(
                "SELECT * FROM nodes ORDER BY accessed_at DESC LIMIT ?",
                (limit,),
            )
        return [self._row_to_node(r) for r in cur.fetchall()]

    # --- Neighbor queries ---

    def neighbors(
        self,
        node_id: str,
        *,
        direction: Literal["outgoing", "incoming", "both"] = "both",
        rel_filter: list[str] | None = None,
        limit: int = 50,
    ) -> NeighborResult:
        """1-hop neighbors, deterministically ordered."""
        outgoing: list[tuple[GraphEdge, GraphNode]] = []
        incoming: list[tuple[GraphEdge, GraphNode]] = []

        if direction in ("outgoing", "both"):
            outgoing = self._fetch_neighbors(node_id, "outgoing", rel_filter, limit)

        if direction in ("incoming", "both"):
            incoming = self._fetch_neighbors(node_id, "incoming", rel_filter, limit)

        return NeighborResult(outgoing=outgoing, incoming=incoming)

    def _fetch_neighbors(
        self,
        node_id: str,
        direction: str,
        rel_filter: list[str] | None,
        limit: int,
    ) -> list[tuple[GraphEdge, GraphNode]]:
        """Fetch neighbor edges + nodes for one direction."""
        if direction == "outgoing":
            col, peer_col = "source", "target"
            order = "relationship ASC, target ASC"
        else:
            col, peer_col = "target", "source"
            order = "relationship ASC, source ASC"

        if rel_filter:
            placeholders = ",".join("?" for _ in rel_filter)
            query = (
                f"SELECT * FROM edges WHERE {col} = ? "
                f"AND relationship IN ({placeholders}) "
                f"ORDER BY {order} LIMIT ?"
            )
            params: list[Any] = [node_id, *rel_filter, limit]
        else:
            query = f"SELECT * FROM edges WHERE {col} = ? ORDER BY {order} LIMIT ?"
            params = [node_id, limit]

        cur = self._conn.execute(query, params)
        edge_rows = cur.fetchall()

        # Batch fetch peer nodes
        peer_ids = list(dict.fromkeys(row[peer_col] for row in edge_rows))
        if not peer_ids:
            return []
        ph = ",".join("?" for _ in peer_ids)
        node_cur = self._conn.execute(
            f"SELECT * FROM nodes WHERE id IN ({ph})",
            peer_ids,
        )
        nodes_by_id = {r["id"]: self._row_to_node(r) for r in node_cur.fetchall()}

        pairs: list[tuple[GraphEdge, GraphNode]] = []
        for row in edge_rows:
            edge = self._row_to_edge(row)
            peer_id = row[peer_col]
            if peer_id in nodes_by_id:
                pairs.append((edge, nodes_by_id[peer_id]))

        return pairs

    # --- Traversal ---

    def walk(
        self,
        start: list[str],
        *,
        max_depth: int = 3,
        max_nodes: int = 50,
        max_edges: int = 150,
        rel_allow: list[str] | None = None,
        node_type_filter: list[str] | None = None,
        direction: Literal["outgoing", "incoming"] = "outgoing",
    ) -> TraversalResult:
        """Bounded BFS traversal. Start nodes in caller order.

        direction="outgoing" follows source->target (default).
        direction="incoming" follows target->source (blast radius).

        Uses _get_node_readonly internally. Batch touches access stats
        after BFS completes to avoid write amplification.
        """
        visited_nodes: dict[str, GraphNode] = {}
        visited_edges: list[GraphEdge] = []
        visited_ids: set[str] = set()
        max_depth_reached = 0
        truncated = False
        reason: str | None = None

        # Queue: (node_id, depth)
        queue: deque[tuple[str, int]] = deque()
        for nid in start:
            if nid not in visited_ids:
                queue.append((nid, 0))
                visited_ids.add(nid)

        while queue:
            if len(visited_nodes) >= max_nodes:
                truncated = True
                reason = "max_nodes"
                break
            if len(visited_edges) >= max_edges:
                truncated = True
                reason = "max_edges"
                break

            current_id, depth = queue.popleft()

            node = self._get_node_readonly(current_id)
            if node is None:
                continue
            if node_type_filter and node.type not in node_type_filter:
                continue

            visited_nodes[current_id] = node
            if depth > max_depth_reached:
                max_depth_reached = depth

            if depth >= max_depth:
                continue

            # Get edges in the requested direction (deterministic order)
            edges = self._get_directed_edges(current_id, rel_allow, direction)
            for edge in edges:
                if len(visited_edges) >= max_edges:
                    truncated = True
                    reason = "max_edges"
                    break
                visited_edges.append(edge)
                peer_id = edge.target if direction == "outgoing" else edge.source
                if peer_id not in visited_ids:
                    visited_ids.add(peer_id)
                    queue.append((peer_id, depth + 1))

            if truncated:
                break

        # Batch touch all visited nodes
        if visited_nodes:
            self._batch_touch(list(visited_nodes.keys()))

        if not truncated and max_depth_reached >= max_depth and queue:
            truncated = True
            reason = "max_depth"

        receipt = TraversalReceipt(
            visited_nodes=len(visited_nodes),
            visited_edges=len(visited_edges),
            max_depth_reached=max_depth_reached,
            truncated=truncated,
            reason=reason,
        )

        return TraversalResult(
            nodes=list(visited_nodes.values()),
            edges=visited_edges,
            receipt=receipt,
        )

    def _get_node_readonly(self, id: str) -> GraphNode | None:
        """Fetch node without touching access stats (for traversal internals)."""
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM nodes WHERE id = ?", (id,))
        row = cur.fetchone()
        return self._row_to_node(row) if row else None

    def _get_directed_edges(
        self,
        node_id: str,
        rel_allow: list[str] | None,
        direction: Literal["outgoing", "incoming"],
    ) -> list[GraphEdge]:
        """Edges in the requested direction, deterministically ordered."""
        if direction == "outgoing":
            col, order = "source", "relationship ASC, target ASC"
        else:
            col, order = "target", "relationship ASC, source ASC"

        if rel_allow:
            ph = ",".join("?" for _ in rel_allow)
            cur = self._conn.execute(
                f"SELECT * FROM edges WHERE {col} = ? AND relationship IN ({ph}) ORDER BY {order}",
                [node_id, *rel_allow],
            )
        else:
            cur = self._conn.execute(
                f"SELECT * FROM edges WHERE {col} = ? ORDER BY {order}",
                (node_id,),
            )
        return [self._row_to_edge(r) for r in cur.fetchall()]

    def _batch_touch(self, node_ids: list[str]) -> None:
        """Batch update accessed_at and access_count for visited nodes."""
        now = _now_ms()
        ph = ",".join("?" for _ in node_ids)
        with self._conn:
            self._conn.execute(
                "UPDATE nodes SET accessed_at = ?, access_count = access_count + 1 "
                f"WHERE id IN ({ph})",
                [now, *node_ids],
            )

    # --- Subgraph ---

    def subgraph(self, node_ids: list[str]) -> SubgraphResult:
        """Return induced subgraph: requested nodes + all edges between them.

        Nodes sorted by id ASC for determinism. Chunks large IN lists
        to stay under SQLite variable limits.
        """
        if not node_ids:
            return SubgraphResult(nodes=[], edges=[])

        # Fetch nodes — chunked for large lists
        all_nodes: list[GraphNode] = []
        chunk_size = 500  # well under SQLite's 999 variable limit
        for i in range(0, len(node_ids), chunk_size):
            chunk = node_ids[i : i + chunk_size]
            ph = ",".join("?" for _ in chunk)
            cur = self._conn.execute(
                f"SELECT * FROM nodes WHERE id IN ({ph})",
                chunk,
            )
            all_nodes.extend(self._row_to_node(r) for r in cur.fetchall())

        # Sort by id ASC for determinism
        all_nodes.sort(key=lambda n: n.id)
        node_id_set = {n.id for n in all_nodes}

        # Fetch all edges where BOTH endpoints are in the set
        all_edges: list[GraphEdge] = []
        for i in range(0, len(node_ids), chunk_size):
            chunk = node_ids[i : i + chunk_size]
            ph = ",".join("?" for _ in chunk)
            cur = self._conn.execute(
                f"SELECT * FROM edges WHERE source IN ({ph}) "
                "ORDER BY source ASC, relationship ASC, target ASC",
                chunk,
            )
            for r in cur.fetchall():
                edge = self._row_to_edge(r)
                if edge.target in node_id_set:
                    all_edges.append(edge)

        # Stable edge order across chunks
        all_edges.sort(key=lambda e: (e.source, e.relationship, e.target))

        return SubgraphResult(nodes=all_nodes, edges=all_edges)

    # --- Observations ---

    def add_observations(
        self,
        node_id: str,
        observations: list[str],
        source: str = "system",
        kind: str = "fact",
    ) -> list[str]:
        """Append observations to a node. Returns actually added (new) ones.

        Enforces max length. Uses INSERT OR IGNORE for dedup within a
        single transaction. Raises MissingNodeError if node absent.
        """
        cur = self._conn.cursor()
        cur.execute("SELECT id FROM nodes WHERE id = ?", (node_id,))
        if cur.fetchone() is None:
            raise MissingNodeError(node_id, "node")

        now = _now_ms()
        added: list[str] = []
        with self._conn:
            for raw in observations:
                obs = _normalize_observation(raw)
                if not obs:
                    continue  # skip empty after normalization
                if len(obs) > MAX_OBSERVATION_LENGTH:
                    msg = f"Observation too long ({len(obs)} chars, max {MAX_OBSERVATION_LENGTH})"
                    raise ValueError(msg)
                cur.execute(
                    "INSERT OR IGNORE INTO observations "
                    "(node_id, source, kind, content, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (node_id, source, kind, obs, now),
                )
                if cur.rowcount > 0:
                    added.append(obs)
        return added

    def get_observations(
        self,
        node_id: str,
        *,
        source: str | None = None,
        kind: str | None = None,
    ) -> list[str]:
        """Get observations for a node, ordered by created_at ASC, id ASC.

        Optionally filter by source and/or kind.
        """
        clauses = ["node_id = ?"]
        params: list[Any] = [node_id]
        if source is not None:
            clauses.append("source = ?")
            params.append(source)
        if kind is not None:
            clauses.append("kind = ?")
            params.append(kind)
        where = " AND ".join(clauses)
        cur = self._conn.execute(
            f"SELECT content FROM observations WHERE {where} ORDER BY created_at ASC, id ASC",
            params,
        )
        return [row[0] for row in cur.fetchall()]

    def delete_observations(
        self,
        node_id: str,
        observations: list[str],
    ) -> None:
        """Delete specific observations by content."""
        if not observations:
            return
        ph = ",".join("?" for _ in observations)
        with self._conn:
            self._conn.execute(
                f"DELETE FROM observations WHERE node_id = ? AND content IN ({ph})",
                [node_id, *observations],
            )
