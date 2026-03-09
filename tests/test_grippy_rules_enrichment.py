# SPDX-License-Identifier: MIT
"""Tests for rule result enrichment from graph store."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from grippy.graph_store import SQLiteGraphStore
from grippy.graph_types import EdgeType, NodeType, _record_id
from grippy.rules.base import RuleResult, RuleSeverity
from grippy.rules.enrichment import enrich_results


def _make_graph(tmp: str) -> SQLiteGraphStore:
    return SQLiteGraphStore(db_path=Path(tmp) / "test.db")


def _result(rule_id: str = "test-rule", file: str = "app.py") -> RuleResult:
    return RuleResult(rule_id=rule_id, severity=RuleSeverity.ERROR, message="msg", file=file)


class TestEnrichResultsPassthrough:
    def test_none_graph_returns_unchanged(self) -> None:
        results = [_result()]
        enriched = enrich_results(results, None)
        assert enriched is results  # same object, no copy

    def test_empty_results_returns_empty(self) -> None:
        with TemporaryDirectory() as tmp:
            store = _make_graph(tmp)
            assert enrich_results([], store) == []


class TestBlastRadius:
    def test_file_with_dependents(self) -> None:
        with TemporaryDirectory() as tmp:
            store = _make_graph(tmp)
            # app.py is imported by handler.py and routes.py
            app_id = _record_id(NodeType.FILE, "app.py")
            h_id = _record_id(NodeType.FILE, "handler.py")
            r_id = _record_id(NodeType.FILE, "routes.py")
            store.upsert_node(app_id, NodeType.FILE, {"path": "app.py"})
            store.upsert_node(h_id, NodeType.FILE, {"path": "handler.py"})
            store.upsert_node(r_id, NodeType.FILE, {"path": "routes.py"})
            store.upsert_edge(h_id, app_id, EdgeType.IMPORTS)
            store.upsert_edge(r_id, app_id, EdgeType.IMPORTS)

            results = enrich_results([_result(file="app.py")], store)
            assert results[0].enrichment is not None
            assert results[0].enrichment.blast_radius == 2

    def test_file_with_no_dependents(self) -> None:
        with TemporaryDirectory() as tmp:
            store = _make_graph(tmp)
            app_id = _record_id(NodeType.FILE, "leaf.py")
            store.upsert_node(app_id, NodeType.FILE, {"path": "leaf.py"})

            results = enrich_results([_result(file="leaf.py")], store)
            assert results[0].enrichment is not None
            assert results[0].enrichment.blast_radius == 0

    def test_file_not_in_graph(self) -> None:
        with TemporaryDirectory() as tmp:
            store = _make_graph(tmp)
            results = enrich_results([_result(file="unknown.py")], store)
            assert results[0].enrichment is not None
            assert results[0].enrichment.blast_radius == 0


class TestRecurrence:
    def test_recurring_finding(self) -> None:
        with TemporaryDirectory() as tmp:
            store = _make_graph(tmp)
            file_id = _record_id(NodeType.FILE, "app.py")
            store.upsert_node(file_id, NodeType.FILE, {"path": "app.py"})
            # Simulate two prior findings with same rule_id on this file
            for i in range(2):
                fid = _record_id(NodeType.FINDING, f"prior-{i}")
                store.upsert_node(
                    fid, NodeType.FINDING, {"rule_id": "sql-injection-risk", "severity": "ERROR"}
                )
                store.upsert_edge(fid, file_id, EdgeType.FOUND_IN)

            results = enrich_results([_result(rule_id="sql-injection-risk", file="app.py")], store)
            assert results[0].enrichment is not None
            assert results[0].enrichment.is_recurring is True
            assert results[0].enrichment.prior_count == 2

    def test_non_recurring_finding(self) -> None:
        with TemporaryDirectory() as tmp:
            store = _make_graph(tmp)
            file_id = _record_id(NodeType.FILE, "app.py")
            store.upsert_node(file_id, NodeType.FILE, {"path": "app.py"})

            results = enrich_results([_result(rule_id="weak-crypto", file="app.py")], store)
            assert results[0].enrichment is not None
            assert results[0].enrichment.is_recurring is False
            assert results[0].enrichment.prior_count == 0

    def test_different_rule_id_not_counted(self) -> None:
        with TemporaryDirectory() as tmp:
            store = _make_graph(tmp)
            file_id = _record_id(NodeType.FILE, "app.py")
            store.upsert_node(file_id, NodeType.FILE, {"path": "app.py"})
            fid = _record_id(NodeType.FINDING, "prior-other")
            store.upsert_node(fid, NodeType.FINDING, {"rule_id": "weak-crypto", "severity": "WARN"})
            store.upsert_edge(fid, file_id, EdgeType.FOUND_IN)

            results = enrich_results([_result(rule_id="sql-injection-risk", file="app.py")], store)
            assert results[0].enrichment is not None
            assert results[0].enrichment.is_recurring is False
            assert results[0].enrichment.prior_count == 0


class TestImportSuppression:
    def test_sql_injection_suppressed_by_sqlalchemy(self) -> None:
        with TemporaryDirectory() as tmp:
            store = _make_graph(tmp)
            app_id = _record_id(NodeType.FILE, "app.py")
            sa_id = _record_id(NodeType.FILE, "src/sqlalchemy/__init__.py")
            store.upsert_node(app_id, NodeType.FILE, {"path": "app.py"})
            store.upsert_node(sa_id, NodeType.FILE, {"path": "src/sqlalchemy/__init__.py"})
            store.upsert_edge(app_id, sa_id, EdgeType.IMPORTS)

            results = enrich_results([_result(rule_id="sql-injection-risk", file="app.py")], store)
            assert results[0].enrichment is not None
            assert results[0].enrichment.suppressed is True
            assert "sqlalchemy" in results[0].enrichment.suppression_reason

    def test_weak_crypto_suppressed_by_cache_path(self) -> None:
        with TemporaryDirectory() as tmp:
            store = _make_graph(tmp)
            results = enrich_results([_result(rule_id="weak-crypto", file="utils/cache.py")], store)
            assert results[0].enrichment is not None
            assert results[0].enrichment.suppressed is True
            assert "cache" in results[0].enrichment.suppression_reason

    def test_no_suppression_without_matching_imports(self) -> None:
        with TemporaryDirectory() as tmp:
            store = _make_graph(tmp)
            app_id = _record_id(NodeType.FILE, "app.py")
            store.upsert_node(app_id, NodeType.FILE, {"path": "app.py"})

            results = enrich_results([_result(rule_id="sql-injection-risk", file="app.py")], store)
            assert results[0].enrichment is not None
            assert results[0].enrichment.suppressed is False


class TestVelocity:
    def test_velocity_with_prior_reviews(self) -> None:
        with TemporaryDirectory() as tmp:
            store = _make_graph(tmp)
            # Create 3 reviews, each with a sql-injection-risk finding
            for i in range(3):
                rid = _record_id(NodeType.REVIEW, f"review-{i}")
                store.upsert_node(rid, NodeType.REVIEW, {"pr": i, "score": 50})
                fid = _record_id(NodeType.FINDING, f"vel-{i}")
                store.upsert_node(
                    fid, NodeType.FINDING, {"rule_id": "sql-injection-risk", "severity": "ERROR"}
                )
                store.upsert_edge(rid, fid, EdgeType.PRODUCED)

            results = enrich_results([_result(rule_id="sql-injection-risk")], store)
            assert results[0].enrichment is not None
            assert "3" in results[0].enrichment.velocity
            assert "sql-injection-risk" in results[0].enrichment.velocity

    def test_velocity_empty_when_no_history(self) -> None:
        with TemporaryDirectory() as tmp:
            store = _make_graph(tmp)
            results = enrich_results([_result(rule_id="sql-injection-risk")], store)
            assert results[0].enrichment is not None
            assert results[0].enrichment.velocity == ""


class TestRuleFindingPersistence:
    def test_persisted_rule_finding_detected_as_recurring(self) -> None:
        """Simulate: persist a rule finding, then check recurrence on next run."""
        from grippy.rules.enrichment import persist_rule_findings

        with TemporaryDirectory() as tmp:
            store = _make_graph(tmp)
            # Set up file node
            file_id = _record_id(NodeType.FILE, "app.py")
            store.upsert_node(file_id, NodeType.FILE, {"path": "app.py"})
            # Set up review node
            review_id = _record_id(NodeType.REVIEW, "test-review-1")
            store.upsert_node(review_id, NodeType.REVIEW, {"pr": 1, "score": 50})

            # Persist a rule finding
            findings = [_result(rule_id="sql-injection-risk", file="app.py")]
            persist_rule_findings(store, findings, review_id)

            # Now enrich — should detect recurrence
            new_findings = [_result(rule_id="sql-injection-risk", file="app.py")]
            enriched = enrich_results(new_findings, store)
            assert enriched[0].enrichment is not None
            assert enriched[0].enrichment.is_recurring is True
            assert enriched[0].enrichment.prior_count == 1


class TestMultipleResults:
    def test_multiple_files_enriched_independently(self) -> None:
        with TemporaryDirectory() as tmp:
            store = _make_graph(tmp)
            a_id = _record_id(NodeType.FILE, "a.py")
            b_id = _record_id(NodeType.FILE, "b.py")
            dep_id = _record_id(NodeType.FILE, "dep.py")
            store.upsert_node(a_id, NodeType.FILE, {"path": "a.py"})
            store.upsert_node(b_id, NodeType.FILE, {"path": "b.py"})
            store.upsert_node(dep_id, NodeType.FILE, {"path": "dep.py"})
            store.upsert_edge(dep_id, a_id, EdgeType.IMPORTS)  # dep imports a

            results = enrich_results([_result(file="a.py"), _result(file="b.py")], store)
            assert results[0].enrichment is not None
            assert results[0].enrichment.blast_radius == 1
            assert results[1].enrichment is not None
            assert results[1].enrichment.blast_radius == 0
