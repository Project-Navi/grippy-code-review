# SPDX-License-Identifier: MIT
"""Tests for Grippy graph enums (re-exported from graph_types)."""

from __future__ import annotations

from grippy.graph import (
    EdgeType,
    NodeType,
)

# --- Enum values ---


class TestEdgeType:
    """Edge type enum values (re-exported from graph_types)."""

    def test_violates_edge_exists(self) -> None:
        assert EdgeType.VIOLATES == "VIOLATES"

    def test_found_in_edge_exists(self) -> None:
        assert EdgeType.FOUND_IN == "FOUND_IN"

    def test_imports_edge_exists(self) -> None:
        assert EdgeType.IMPORTS == "IMPORTS"

    def test_produced_edge_exists(self) -> None:
        assert EdgeType.PRODUCED == "PRODUCED"

    def test_touched_edge_exists(self) -> None:
        assert EdgeType.TOUCHED == "TOUCHED"

    def test_authored_edge_exists(self) -> None:
        assert EdgeType.AUTHORED == "AUTHORED"


class TestNodeType:
    def test_node_types(self) -> None:
        assert NodeType.REVIEW == "REVIEW"
        assert NodeType.FILE == "FILE"
        assert NodeType.AUTHOR == "AUTHOR"
        assert NodeType.RULE == "RULE"
        assert NodeType.FINDING == "FINDING"

    def test_re_export_identity(self) -> None:
        """Ensure re-exports are the same objects as graph_types originals."""
        from grippy.graph_types import EdgeType as OrigEdge
        from grippy.graph_types import NodeType as OrigNode

        assert EdgeType is OrigEdge
        assert NodeType is OrigNode
