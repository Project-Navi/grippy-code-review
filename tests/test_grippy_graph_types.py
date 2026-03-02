# SPDX-License-Identifier: MIT
"""Tests for graph type definitions and helper functions."""

from __future__ import annotations

import time

import pytest

from grippy.graph_types import (
    EdgeType,
    GraphEdge,
    GraphNode,
    MissingNodeError,
    NeighborResult,
    NodeType,
    SubgraphResult,
    TraversalReceipt,
    TraversalResult,
    _canonical_json,
    _edge_id,
    _normalize_observation,
    _now_ms,
    _record_id,
)


class TestNormalizeObservation:
    def test_strips_whitespace(self) -> None:
        assert _normalize_observation("  hello  ") == "hello"

    def test_collapses_internal_whitespace(self) -> None:
        assert _normalize_observation("a   b\t\tc") == "a b c"

    def test_preserves_case(self) -> None:
        assert _normalize_observation("PASS") == "PASS"
        assert _normalize_observation("pass") == "pass"

    def test_newlines_collapsed(self) -> None:
        assert _normalize_observation("line1\nline2\n") == "line1 line2"

    def test_empty_after_strip(self) -> None:
        assert _normalize_observation("   ") == ""


class TestNodeType:
    def test_v1_types(self) -> None:
        assert NodeType.FILE == "FILE"
        assert NodeType.REVIEW == "REVIEW"
        assert NodeType.FINDING == "FINDING"
        assert NodeType.RULE == "RULE"
        assert NodeType.AUTHOR == "AUTHOR"


class TestEdgeType:
    def test_v1_types(self) -> None:
        assert EdgeType.IMPORTS == "IMPORTS"
        assert EdgeType.FOUND_IN == "FOUND_IN"
        assert EdgeType.VIOLATES == "VIOLATES"
        assert EdgeType.PRODUCED == "PRODUCED"
        assert EdgeType.TOUCHED == "TOUCHED"
        assert EdgeType.AUTHORED == "AUTHORED"


class TestRecordId:
    def test_deterministic(self) -> None:
        id1 = _record_id("FILE", "src/app.py")
        id2 = _record_id("FILE", "src/app.py")
        assert id1 == id2

    def test_includes_type_prefix(self) -> None:
        nid = _record_id("FILE", "src/app.py")
        assert nid.startswith("FILE:")

    def test_different_inputs_different_ids(self) -> None:
        assert _record_id("FILE", "a.py") != _record_id("FILE", "b.py")

    def test_different_types_different_ids(self) -> None:
        assert _record_id("FILE", "x") != _record_id("RULE", "x")

    def test_hash_length_is_12(self) -> None:
        nid = _record_id("FILE", "src/app.py")
        digest = nid.split(":")[1]
        assert len(digest) == 12

    def test_accepts_enum(self) -> None:
        nid = _record_id(NodeType.FILE, "src/app.py")
        assert nid.startswith("FILE:")

    def test_multi_part(self) -> None:
        nid = _record_id("REVIEW", "repo", "42", "abc123")
        assert nid.startswith("REVIEW:")


class TestEdgeId:
    def test_deterministic(self) -> None:
        id1 = _edge_id("A:aaa", "IMPORTS", "B:bbb")
        id2 = _edge_id("A:aaa", "IMPORTS", "B:bbb")
        assert id1 == id2

    def test_full_sha256_length(self) -> None:
        eid = _edge_id("A:aaa", "IMPORTS", "B:bbb")
        assert len(eid) == 64

    def test_different_triples_different_ids(self) -> None:
        assert _edge_id("A:a", "R", "B:b") != _edge_id("A:a", "R", "C:c")

    def test_direction_matters(self) -> None:
        assert _edge_id("A:a", "R", "B:b") != _edge_id("B:b", "R", "A:a")

    def test_uses_unit_separator(self) -> None:
        """Different delimiters produce different IDs (proves \\x1f is used)."""
        # "A" + \x1f + "B:C" != "A:B" + \x1f + "C"
        assert _edge_id("A", "B", "C") != _edge_id("A\x1fB", "", "C")


class TestCanonicalJson:
    def test_sorted_keys(self) -> None:
        result = _canonical_json({"b": 2, "a": 1})
        assert result == '{"a":1,"b":2}'

    def test_compact_separators(self) -> None:
        result = _canonical_json({"key": "value"})
        assert " " not in result

    def test_empty_dict(self) -> None:
        assert _canonical_json({}) == "{}"

    def test_rejects_non_dict(self) -> None:
        with pytest.raises(TypeError, match="Expected dict"):
            _canonical_json([1, 2, 3])  # type: ignore[arg-type]

    def test_rejects_string(self) -> None:
        with pytest.raises(TypeError, match="Expected dict"):
            _canonical_json("hello")  # type: ignore[arg-type]


class TestNowMs:
    def test_returns_int(self) -> None:
        assert isinstance(_now_ms(), int)

    def test_reasonable_range(self) -> None:
        now = _now_ms()
        # Should be after 2026-01-01 and before 2100-01-01
        assert 1735689600000 < now < 4102444800000

    def test_monotonic_ish(self) -> None:
        t1 = _now_ms()
        time.sleep(0.002)
        t2 = _now_ms()
        assert t2 >= t1


class TestMissingNodeError:
    def test_source_role(self) -> None:
        err = MissingNodeError("FILE:abc", "source")
        assert err.node_id == "FILE:abc"
        assert err.role == "source"
        assert "source" in str(err)

    def test_target_role(self) -> None:
        err = MissingNodeError("FILE:abc", "target")
        assert err.role == "target"


class TestDataclasses:
    def test_graph_node_frozen(self) -> None:
        node = GraphNode(
            id="FILE:abc",
            type="FILE",
            data={"path": "a.py"},
            created_at=1000,
            updated_at=1000,
            accessed_at=1000,
            access_count=1,
        )
        with pytest.raises(AttributeError):
            node.id = "other"  # type: ignore[misc]

    def test_graph_edge_frozen(self) -> None:
        edge = GraphEdge(
            id="deadbeef",
            source="A:a",
            target="B:b",
            relationship="R",
            weight=1.0,
            properties={},
            created_at=1000,
            updated_at=1000,
        )
        with pytest.raises(AttributeError):
            edge.weight = 0.5  # type: ignore[misc]

    def test_traversal_receipt(self) -> None:
        receipt = TraversalReceipt(
            visited_nodes=10,
            visited_edges=15,
            max_depth_reached=2,
            truncated=True,
            reason="max_nodes",
        )
        assert receipt.truncated is True

    def test_traversal_result(self) -> None:
        receipt = TraversalReceipt(0, 0, 0, False, None)
        result = TraversalResult(nodes=[], edges=[], receipt=receipt)
        assert result.nodes == []

    def test_neighbor_result(self) -> None:
        result = NeighborResult(outgoing=[], incoming=[])
        assert result.outgoing == []

    def test_subgraph_result(self) -> None:
        result = SubgraphResult(nodes=[], edges=[])
        assert result.nodes == []
        assert result.edges == []
