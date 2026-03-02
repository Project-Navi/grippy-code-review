# SPDX-License-Identifier: MIT
"""Integration test — full graph pipeline round-trip."""

from __future__ import annotations

from pathlib import Path

import pytest

from grippy.graph_context import build_context_pack
from grippy.graph_store import SQLiteGraphStore
from grippy.graph_types import EdgeType, NodeType, _record_id


@pytest.fixture()
def store(tmp_path: Path) -> SQLiteGraphStore:
    return SQLiteGraphStore(db_path=tmp_path / "navi-graph.db")


class TestFullPipelineRoundTrip:
    """Simulate: index codebase -> review PR -> query context for next PR."""

    def test_round_trip(self, store: SQLiteGraphStore) -> None:
        # Phase 1: Codebase indexing — file nodes + import edges
        files = ["src/grippy/review.py", "src/grippy/schema.py", "src/grippy/agent.py"]
        file_ids = {}
        for path in files:
            fid = _record_id(NodeType.FILE, path)
            file_ids[path] = fid
            store.upsert_node(fid, NodeType.FILE, {"path": path, "lang": "python"})

        # review.py imports schema and agent
        store.upsert_edge(
            file_ids["src/grippy/review.py"],
            file_ids["src/grippy/schema.py"],
            EdgeType.IMPORTS,
        )
        store.upsert_edge(
            file_ids["src/grippy/review.py"],
            file_ids["src/grippy/agent.py"],
            EdgeType.IMPORTS,
        )

        # Phase 2: Review start
        review_id = _record_id(NodeType.REVIEW, "repo", "42", "abc123")
        author_id = _record_id(NodeType.AUTHOR, "ndspence")
        store.upsert_node(
            review_id,
            NodeType.REVIEW,
            {
                "repo": "repo",
                "pr": 42,
                "status": "running",
            },
        )
        store.upsert_node(author_id, NodeType.AUTHOR, {"login": "ndspence"})
        store.upsert_edge(author_id, review_id, EdgeType.AUTHORED)
        store.upsert_edge(review_id, file_ids["src/grippy/schema.py"], EdgeType.TOUCHED)

        # Phase 3: Post-review — persist findings
        finding_id = _record_id(NodeType.FINDING, review_id, "F-001")
        store.upsert_node(
            finding_id,
            NodeType.FINDING,
            {
                "finding_id": "F-001",
                "severity": "HIGH",
                "severity_rank": 3,
                "confidence": 0.85,
                "category": "security",
                "title": "SQL injection risk",
                "fingerprint": "abc123def456",  # pragma: allowlist secret
            },
        )
        store.upsert_edge(finding_id, file_ids["src/grippy/schema.py"], EdgeType.FOUND_IN)
        store.upsert_edge(review_id, finding_id, EdgeType.PRODUCED)

        # Update review to success
        store.upsert_node(
            review_id,
            NodeType.REVIEW,
            {
                "repo": "repo",
                "pr": 42,
                "status": "success",
                "score": 72,
                "findings_count": 1,
            },
        )

        # Phase 4: Next PR — query context for schema.py changes
        pack = build_context_pack(
            store,
            touched_files=["src/grippy/schema.py"],
            author_login="ndspence",
        )

        # Blast radius: review.py imports schema.py
        assert len(pack.blast_radius_files) >= 1

        # Recurring finding: prior HIGH finding in schema.py
        assert len(pack.recurring_findings) >= 1
        assert pack.recurring_findings[0]["severity"] == "HIGH"

        # Author history: 1 HIGH finding
        assert pack.author_risk_summary.get("HIGH", 0) >= 1

    def test_dependency_walk_blast_radius(self, store: SQLiteGraphStore) -> None:
        """Walk IMPORTS inbound to find all dependents (direction='incoming')."""
        # Build: b imports a, c imports b, d imports c
        nodes = ["a.py", "b.py", "c.py", "d.py"]
        ids = {}
        for n in nodes:
            nid = _record_id(NodeType.FILE, n)
            ids[n] = nid
            store.upsert_node(nid, NodeType.FILE, {"path": n})

        store.upsert_edge(ids["b.py"], ids["a.py"], EdgeType.IMPORTS)
        store.upsert_edge(ids["c.py"], ids["b.py"], EdgeType.IMPORTS)
        store.upsert_edge(ids["d.py"], ids["c.py"], EdgeType.IMPORTS)

        # Walk incoming from a.py — "who depends on a.py?"
        result = store.walk(
            [ids["a.py"]],
            max_depth=3,
            max_nodes=50,
            rel_allow=["IMPORTS"],
            direction="incoming",
        )
        node_ids = {n.id for n in result.nodes}
        # a.py + b (imports a) + c (imports b) + d (imports c)
        assert ids["a.py"] in node_ids
        assert ids["b.py"] in node_ids
        assert ids["c.py"] in node_ids
        assert ids["d.py"] in node_ids

    def test_observations_round_trip(self, store: SQLiteGraphStore) -> None:
        """Observations survive pipeline lifecycle: add, query, accumulate."""
        fid = _record_id(NodeType.FILE, "src/grippy/schema.py")
        store.upsert_node(fid, NodeType.FILE, {"path": "src/grippy/schema.py"})

        # First review: add history observation
        store.add_observations(
            fid,
            ["PR #42: score 72, 3 findings (FAIL)"],
            source="pipeline",
            kind="history",
        )
        # Second review: add another
        store.add_observations(
            fid,
            ["PR #43: score 91, 0 findings (PASS)"],
            source="pipeline",
            kind="history",
        )
        # Tag the file
        store.add_observations(
            fid,
            ["high-churn"],
            source="pipeline",
            kind="tag",
        )

        # Query all
        all_obs = store.get_observations(fid)
        assert len(all_obs) == 3

        # Query just history
        history = store.get_observations(fid, kind="history")
        assert len(history) == 2

        # Query just tags
        tags = store.get_observations(fid, kind="tag")
        assert tags == ["high-churn"]

    def test_subgraph_pr_diff_files(self, store: SQLiteGraphStore) -> None:
        """Subgraph of touched files shows inter-file relationships."""
        files = ["src/grippy/review.py", "src/grippy/schema.py", "src/grippy/agent.py"]
        file_ids = {}
        for path in files:
            fid = _record_id(NodeType.FILE, path)
            file_ids[path] = fid
            store.upsert_node(fid, NodeType.FILE, {"path": path})

        store.upsert_edge(
            file_ids["src/grippy/review.py"],
            file_ids["src/grippy/schema.py"],
            EdgeType.IMPORTS,
        )
        store.upsert_edge(
            file_ids["src/grippy/review.py"],
            file_ids["src/grippy/agent.py"],
            EdgeType.IMPORTS,
        )

        sg = store.subgraph(list(file_ids.values()))
        assert len(sg.nodes) == 3
        assert len(sg.edges) == 2
        # Nodes sorted by id ASC
        assert sg.nodes == sorted(sg.nodes, key=lambda n: n.id)
