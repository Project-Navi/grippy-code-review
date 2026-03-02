# SPDX-License-Identifier: MIT
"""Graph types, enums, and helpers for Grippy's navi-graph-shaped store.

Provides node/edge type enums, frozen dataclasses for query results,
deterministic ID generation, canonical JSON serialization, and typed
exceptions. Separated from the store so other modules can import types
without pulling in SQLite.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal

# --- Enums ---


class NodeType(StrEnum):
    FILE = "FILE"
    REVIEW = "REVIEW"
    FINDING = "FINDING"
    RULE = "RULE"
    AUTHOR = "AUTHOR"


class EdgeType(StrEnum):
    IMPORTS = "IMPORTS"
    FOUND_IN = "FOUND_IN"
    VIOLATES = "VIOLATES"
    PRODUCED = "PRODUCED"
    TOUCHED = "TOUCHED"
    AUTHORED = "AUTHORED"


# --- Dataclasses ---


@dataclass(frozen=True)
class GraphNode:
    id: str
    type: str
    data: dict[str, Any]
    created_at: int
    updated_at: int
    accessed_at: int
    access_count: int


@dataclass(frozen=True)
class GraphEdge:
    id: str
    source: str
    target: str
    relationship: str
    weight: float
    properties: dict[str, Any]
    created_at: int
    updated_at: int


@dataclass(frozen=True)
class NeighborResult:
    outgoing: list[tuple[GraphEdge, GraphNode]]
    incoming: list[tuple[GraphEdge, GraphNode]]


@dataclass(frozen=True)
class TraversalReceipt:
    visited_nodes: int
    visited_edges: int
    max_depth_reached: int
    truncated: bool
    reason: str | None


@dataclass(frozen=True)
class TraversalResult:
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    receipt: TraversalReceipt


@dataclass(frozen=True)
class SubgraphResult:
    nodes: list[GraphNode]  # sorted by id ASC for determinism
    edges: list[GraphEdge]  # all edges where both endpoints in node_ids


# --- Constants ---

MAX_OBSERVATION_LENGTH = 500


# --- Exceptions ---


class MissingNodeError(Exception):
    """Raised when upsert_edge references a node that doesn't exist."""

    def __init__(self, node_id: str, role: Literal["source", "target", "node"]) -> None:
        self.node_id = node_id
        self.role = role
        super().__init__(f"Edge {role} node not found: {node_id}")


# --- Helpers ---


def _record_id(node_type: NodeType | str, *parts: str) -> str:
    """Deterministic node ID: '{TYPE}:{sha256[:12]}'."""
    type_str = node_type.value if isinstance(node_type, StrEnum) else node_type
    raw = ":".join([type_str, *parts])
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"{type_str.upper()}:{digest}"


def _edge_id(source: str, relationship: str, target: str) -> str:
    """Deterministic edge ID: full sha256 of canonical triple."""
    canonical = f"{source}\x1f{relationship}\x1f{target}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _canonical_json(obj: dict[str, Any]) -> str:
    """Canonical JSON: sorted keys, compact separators, dict only."""
    if not isinstance(obj, dict):
        msg = f"Expected dict, got {type(obj).__name__}"
        raise TypeError(msg)
    return json.dumps(obj, separators=(",", ":"), sort_keys=True)


def _now_ms() -> int:
    """Current time as epoch milliseconds."""
    return int(time.time() * 1000)


def _normalize_observation(text: str) -> str:
    """Normalize observation content: strip + collapse internal whitespace.

    Case-sensitive (preserves "PASS" vs "pass"). Applied before dedup
    and length check so equivalent strings don't create duplicates.
    """
    return re.sub(r"\s+", " ", text.strip())
