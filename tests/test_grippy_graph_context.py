# SPDX-License-Identifier: MIT
"""Tests for graph context builder (pre-review context pack)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from grippy.graph_context import ContextPack, build_context_pack, format_context_for_llm
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

    def test_file_history_from_observations(self, store: SQLiteGraphStore) -> None:
        fid = _record_id("FILE", "src/app.py")
        store.upsert_node(fid, "FILE", {"path": "src/app.py"})
        store.add_observations(fid, ["PR #1: passed"], source="pipeline", kind="history")
        pack = build_context_pack(store, touched_files=["src/app.py"])
        assert "src/app.py" in pack.file_history
        assert "PR #1: passed" in pack.file_history["src/app.py"]

    def test_author_risk_summary(self, store: SQLiteGraphStore) -> None:
        author_id = _record_id("AUTHOR", "octocat")
        review_id = _record_id("REVIEW", "pr-99")
        finding_id = _record_id("FINDING", "pr-99", "F-001")
        store.upsert_node(author_id, "AUTHOR", {"login": "octocat"})
        store.upsert_node(review_id, "REVIEW", {"pr": 99})
        store.upsert_node(finding_id, "FINDING", {"severity": "HIGH"})
        store.upsert_edge(author_id, review_id, "AUTHORED")
        store.upsert_edge(review_id, finding_id, "PRODUCED")
        pack = build_context_pack(store, touched_files=[], author_login="octocat")
        assert pack.author_risk_summary.get("HIGH", 0) >= 1


class TestFormatContext:
    def test_empty_pack(self, store: SQLiteGraphStore) -> None:
        pack = build_context_pack(store, touched_files=[])
        text = format_context_for_llm(pack)
        assert text == ""

    def test_max_length(self, store: SQLiteGraphStore) -> None:
        pack = build_context_pack(store, touched_files=["a.py"])
        text = format_context_for_llm(pack, max_chars=2000)
        assert len(text) <= 2000

    def test_format_all_sections(self) -> None:
        pack = ContextPack(
            touched_files=["src/a.py"],
            blast_radius_files=[("src/b.py", 3)],
            recurring_findings=[{"file": "src/a.py", "severity": "HIGH", "title": "SQL injection"}],
            file_history={"src/a.py": ["PR #10: refactored"]},
            author_risk_summary={"HIGH": 2, "LOW": 1},
        )
        text = format_context_for_llm(pack)
        assert "Files with downstream dependents:" in text
        assert "Prior findings in changed files:" in text
        assert "File history:" in text
        assert "Author history:" in text

    def test_format_truncation(self) -> None:
        pack = ContextPack(
            touched_files=["src/a.py"],
            blast_radius_files=[(f"src/file_{i}.py", i) for i in range(20)],
            recurring_findings=[],
            file_history={},
            author_risk_summary={},
        )
        text = format_context_for_llm(pack, max_chars=100)
        assert "truncated" in text
        assert len(text) <= 100


# --- Error resilience (IN-C01, IN-C02) ---


class TestContextErrorResilience:
    """Verify build_context_pack fails gracefully on graph errors."""

    def test_build_context_pack_graph_exception_propagates(self, tmp_path: Path) -> None:
        """Graph store exception propagates — no internal try/except wrapper.

        Note: build_context_pack docstring says 'Non-fatal — empty on errors'
        but the function itself has no try/except. The non-fatal wrapper is
        in review.py:577-587. This test documents actual behavior.
        """
        store = SQLiteGraphStore(db_path=tmp_path / "err.db")
        store._conn.close()
        with pytest.raises(sqlite3.ProgrammingError):
            build_context_pack(store, touched_files=["src/a.py"])

    def test_build_context_pack_no_touched_files(self, tmp_path: Path) -> None:
        """Empty touched_files list returns pack with empty blast/findings."""
        store = SQLiteGraphStore(db_path=tmp_path / "empty.db")
        pack = build_context_pack(store, touched_files=[])
        assert pack.touched_files == []
        assert pack.blast_radius_files == []
        assert pack.recurring_findings == []
        assert pack.file_history == {}


# --- Sanitization (prompt-safety) ---


class TestContextSanitization:
    """Verify format_context_for_llm sanitizes dangerous graph data."""

    def test_format_context_sanitizes_invisible_chars(self) -> None:
        """navi_sanitize.clean() strips invisible/zero-width chars from severity/title."""
        pack = ContextPack(
            touched_files=["src/a.py"],
            blast_radius_files=[],
            recurring_findings=[
                {
                    "file": "src/a.py",
                    "severity": "HI\u200bGH",  # zero-width space
                    "title": "SQL\u200d injection",  # zero-width joiner
                }
            ],
            file_history={},
            author_risk_summary={},
        )
        text = format_context_for_llm(pack)
        assert "\u200b" not in text
        assert "\u200d" not in text
        assert "HIGH" in text
        assert "SQL injection" in text

    def test_format_context_sanitizes_bidi_override(self) -> None:
        """navi_sanitize.clean() strips bidi control chars used for text reordering."""
        pack = ContextPack(
            touched_files=["src/a.py"],
            blast_radius_files=[],
            recurring_findings=[
                {
                    "file": "src/a.py",
                    "severity": "\u202eCRITICAL",  # RTL override
                    "title": "Payload\u202a test",  # LTR embedding
                }
            ],
            file_history={},
            author_risk_summary={},
        )
        text = format_context_for_llm(pack)
        assert "\u202e" not in text
        assert "\u202a" not in text
        assert "CRITICAL" in text

    def test_format_context_truncation_boundary(self) -> None:
        """Truncation applies at exact boundary: at-limit passes, one-over truncates."""
        short_pack = ContextPack(
            touched_files=["a.py"],
            blast_radius_files=[("b.py", 1)],
            recurring_findings=[],
            file_history={},
            author_risk_summary={},
        )
        text = format_context_for_llm(short_pack)
        exact_len = len(text)
        # At exactly the text length: no truncation
        at_boundary = format_context_for_llm(short_pack, max_chars=exact_len)
        assert "truncated" not in at_boundary
        # One char less: truncation kicks in
        over_boundary = format_context_for_llm(short_pack, max_chars=exact_len - 1)
        assert "truncated" in over_boundary
        assert len(over_boundary) <= exact_len - 1


# --- Determinism ---


class TestContextDeterminism:
    """Verify format_context_for_llm produces identical output across calls."""

    def test_output_ordering_deterministic(self, store: SQLiteGraphStore) -> None:
        """Same graph state + same inputs = identical output across multiple calls."""
        fid_a = _record_id("FILE", "src/a.py")
        fid_b = _record_id("FILE", "src/b.py")
        finding_id = _record_id("FINDING", "r1", "F-001")
        store.upsert_node(fid_a, "FILE", {"path": "src/a.py"})
        store.upsert_node(fid_b, "FILE", {"path": "src/b.py"})
        store.upsert_node(finding_id, "FINDING", {"severity": "HIGH", "title": "Test"})
        store.upsert_edge(fid_b, fid_a, "IMPORTS")
        store.upsert_edge(finding_id, fid_a, "FOUND_IN")
        store.add_observations(fid_a, ["PR #1: reviewed"], source="pipeline", kind="history")

        results = set()
        for _ in range(5):
            pack = build_context_pack(store, touched_files=["src/a.py"], author_login=None)
            text = format_context_for_llm(pack)
            results.add(text)
        assert len(results) == 1, f"Non-deterministic output: got {len(results)} distinct results"
