# SPDX-License-Identifier: MIT
"""Tests for rule result enrichment from graph store."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

from grippy.graph_store import SQLiteGraphStore
from grippy.graph_types import EdgeType, NodeType, _record_id
from grippy.rules.base import ResultEnrichment, RuleResult, RuleSeverity
from grippy.rules.config import PROFILES
from grippy.rules.engine import RuleEngine
from grippy.rules.enrichment import enrich_results, persist_rule_findings


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


# -- Suppression-gate integration (audit-critical) -------------------------


class TestSuppressionGateIntegration:
    """Prove that suppressed findings survive in the list but don't trigger the gate."""

    def test_suppressed_finding_still_in_results(self) -> None:
        """Suppressed findings must remain in the result list — not filtered out."""
        with TemporaryDirectory() as tmp:
            store = _make_graph(tmp)
            results = enrich_results([_result(rule_id="weak-crypto", file="utils/cache.py")], store)
            assert len(results) == 1
            assert results[0].enrichment is not None
            assert results[0].enrichment.suppressed is True
            # Finding is still present, just marked
            assert results[0].rule_id == "weak-crypto"

    def test_suppressed_finding_does_not_trigger_gate(self) -> None:
        """check_gate() must skip suppressed findings — the core semantic contract."""
        engine = RuleEngine(rule_classes=[])
        profile = PROFILES["security"]
        # An ERROR finding that is suppressed should NOT trigger the gate
        suppressed_result = RuleResult(
            rule_id="sql-injection-risk",
            severity=RuleSeverity.ERROR,
            message="msg",
            file="app.py",
            enrichment=ResultEnrichment(
                blast_radius=0,
                is_recurring=False,
                prior_count=0,
                suppressed=True,
                suppression_reason="file imports sqlalchemy",
                velocity="",
            ),
        )
        assert engine.check_gate([suppressed_result], profile) is False

    def test_unsuppressed_finding_triggers_gate(self) -> None:
        """Baseline: non-suppressed ERROR findings DO trigger the gate."""
        engine = RuleEngine(rule_classes=[])
        profile = PROFILES["security"]
        normal_result = RuleResult(
            rule_id="sql-injection-risk",
            severity=RuleSeverity.ERROR,
            message="msg",
            file="app.py",
            enrichment=ResultEnrichment(
                blast_radius=0,
                is_recurring=False,
                prior_count=0,
                suppressed=False,
                suppression_reason="",
                velocity="",
            ),
        )
        assert engine.check_gate([normal_result], profile) is True


# -- Evidence preservation --------------------------------------------------


class TestEvidencePreservation:
    """Prove enrichment doesn't mutate original finding fields."""

    def test_original_fields_preserved(self) -> None:
        """All original RuleResult fields must survive enrichment unchanged."""
        with TemporaryDirectory() as tmp:
            store = _make_graph(tmp)
            original = RuleResult(
                rule_id="test-rule",
                severity=RuleSeverity.ERROR,
                message="original message",
                file="app.py",
                line=42,
                evidence="some evidence",
            )
            enriched = enrich_results([original], store)
            assert enriched[0].rule_id == "test-rule"
            assert enriched[0].severity == RuleSeverity.ERROR
            assert enriched[0].message == "original message"
            assert enriched[0].file == "app.py"
            assert enriched[0].line == 42
            assert enriched[0].evidence == "some evidence"
            assert enriched[0].enrichment is not None


# -- Error resilience -------------------------------------------------------


class TestErrorResilience:
    """Prove enrichment is non-fatal — graph failures return originals unchanged."""

    def test_graph_exception_returns_originals(self) -> None:
        """If graph store raises during enrichment, original results returned."""
        broken_store = MagicMock(spec=SQLiteGraphStore)
        broken_store.neighbors.side_effect = RuntimeError("db corrupted")
        original = [_result()]
        enriched = enrich_results(original, broken_store)
        assert enriched is original  # same object — fallback path

    def test_persist_nonfatal_on_error(self) -> None:
        """persist_rule_findings must not raise on graph store errors."""
        broken_store = MagicMock(spec=SQLiteGraphStore)
        broken_store.upsert_node.side_effect = RuntimeError("db corrupted")
        findings = [_result(rule_id="sql-injection-risk", file="app.py")]
        # Should not raise
        persist_rule_findings(broken_store, findings, "review-123")


# -- Suppression specificity -----------------------------------------------


class TestSuppressionSpecificity:
    """Prove suppression maps only fire for documented rule_ids and patterns."""

    def test_unregistered_rule_not_suppressed(self) -> None:
        """Rules not in _SUPPRESSION_MAP or _PATH_SUPPRESSION_MAP should never be suppressed."""
        with TemporaryDirectory() as tmp:
            store = _make_graph(tmp)
            # Even with a sqlalchemy import, a non-mapped rule shouldn't be suppressed
            app_id = _record_id(NodeType.FILE, "app.py")
            sa_id = _record_id(NodeType.FILE, "src/sqlalchemy/__init__.py")
            store.upsert_node(app_id, NodeType.FILE, {"path": "app.py"})
            store.upsert_node(sa_id, NodeType.FILE, {"path": "src/sqlalchemy/__init__.py"})
            store.upsert_edge(app_id, sa_id, EdgeType.IMPORTS)

            results = enrich_results([_result(rule_id="secrets-in-diff", file="app.py")], store)
            assert results[0].enrichment is not None
            assert results[0].enrichment.suppressed is False

    def test_path_suppression_case_insensitive(self) -> None:
        """Path suppression uses lowercase comparison."""
        with TemporaryDirectory() as tmp:
            store = _make_graph(tmp)
            results = enrich_results([_result(rule_id="weak-crypto", file="utils/Cache.py")], store)
            assert results[0].enrichment is not None
            assert results[0].enrichment.suppressed is True

    def test_creds_suppressed_by_dynaconf_import(self) -> None:
        """hardcoded-credentials suppressed when file imports dynaconf."""
        with TemporaryDirectory() as tmp:
            store = _make_graph(tmp)
            app_id = _record_id(NodeType.FILE, "config.py")
            dy_id = _record_id(NodeType.FILE, "dynaconf/settings.py")
            store.upsert_node(app_id, NodeType.FILE, {"path": "config.py"})
            store.upsert_node(dy_id, NodeType.FILE, {"path": "dynaconf/settings.py"})
            store.upsert_edge(app_id, dy_id, EdgeType.IMPORTS)

            results = enrich_results(
                [_result(rule_id="hardcoded-credentials", file="config.py")], store
            )
            assert results[0].enrichment is not None
            assert results[0].enrichment.suppressed is True
            assert "dynaconf" in results[0].enrichment.suppression_reason
