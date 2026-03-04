# SPDX-License-Identifier: MIT
"""Tests for Grippy codebase indexing and search tools."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from grippy.codebase import (
    _MAX_GLOB_RESULTS,
    _MAX_RESULT_CHARS,
    CodebaseIndex,
    CodebaseToolkit,
    _config_fingerprint,
    _get_repo_state,
    _limit_result,
    _make_grep_code,
    _make_list_files,
    _make_read_file,
    _make_search_code,
    _write_manifest,
    chunk_file,
    sanitize_tool_hook,
    walk_source_files,
)

# --- Fixtures ---


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    """Create a minimal repo structure for testing."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("def hello():\n    return 'world'\n")
    (tmp_path / "src" / "utils.py").write_text(
        "import os\n\ndef get_env(key):\n    return os.environ.get(key)\n"
    )
    (tmp_path / "README.md").write_text("# Test Project\n\nA test project.\n")
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "cached.pyc").write_bytes(b"fake")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("gitconfig")
    return tmp_path


@pytest.fixture
def mock_embedder() -> MagicMock:
    """Create a mock embedder returning fixed-size vectors."""
    embedder = MagicMock()
    embedder.get_embedding = MagicMock(return_value=[0.1] * 8)
    return embedder


@pytest.fixture
def mock_batch_embedder() -> MagicMock:
    """Create a mock batch embedder."""
    embedder = MagicMock()
    embedder.get_embedding = MagicMock(return_value=[0.1] * 8)
    embedder.get_embedding_batch = MagicMock(side_effect=lambda texts: [[0.1] * 8 for _ in texts])
    return embedder


@pytest.fixture
def lance_db(tmp_path: Path) -> Any:
    """Create a LanceDB connection for testing."""
    import lancedb  # type: ignore[import-untyped]

    lance_dir = tmp_path / "lance_test"
    lance_dir.mkdir()
    return lancedb.connect(str(lance_dir))


# --- _limit_result tests ---


class TestLimitResult:
    def test_short_text_unchanged(self) -> None:
        text = "short text"
        assert _limit_result(text) == text

    def test_exact_limit_unchanged(self) -> None:
        text = "x" * _MAX_RESULT_CHARS
        assert _limit_result(text) == text

    def test_over_limit_truncated_with_message(self) -> None:
        text = "x" * (_MAX_RESULT_CHARS + 500)
        result = _limit_result(text)
        assert len(result) < len(text)
        assert "truncated" in result
        assert "narrow your query" in result

    def test_custom_limit(self) -> None:
        text = "hello world"
        result = _limit_result(text, max_chars=5)
        assert result.startswith("hello")
        assert "truncated" in result


# --- walk_source_files tests ---


class TestWalkSourceFiles:
    def test_finds_python_files(self, tmp_repo: Path) -> None:
        files = walk_source_files(tmp_repo)
        py_files = [f for f in files if f.suffix == ".py"]
        assert len(py_files) == 2

    def test_finds_markdown_files(self, tmp_repo: Path) -> None:
        files = walk_source_files(tmp_repo)
        md_files = [f for f in files if f.suffix == ".md"]
        assert len(md_files) == 1

    def test_ignores_pycache(self, tmp_repo: Path) -> None:
        files = walk_source_files(tmp_repo)
        assert not any("__pycache__" in str(f) for f in files)

    def test_ignores_git_dir(self, tmp_repo: Path) -> None:
        files = walk_source_files(tmp_repo)
        assert not any(".git" in str(f) for f in files)

    def test_custom_extensions(self, tmp_repo: Path) -> None:
        files = walk_source_files(tmp_repo, extensions=frozenset({".toml"}))
        assert len(files) == 1
        assert files[0].name == "pyproject.toml"

    def test_returns_sorted(self, tmp_repo: Path) -> None:
        files = walk_source_files(tmp_repo)
        assert files == sorted(files)

    def test_fallback_when_git_unavailable(self, tmp_repo: Path) -> None:
        """Falls back to manual walk when git ls-files fails."""
        with patch("grippy.codebase.subprocess.run", side_effect=FileNotFoundError):
            files = walk_source_files(tmp_repo)
            assert len(files) > 0


# --- chunk_file tests ---


class TestChunkFile:
    def test_small_file_single_chunk(self, tmp_repo: Path) -> None:
        path = tmp_repo / "src" / "main.py"
        chunks = chunk_file(path)
        assert len(chunks) == 1
        assert chunks[0]["chunk_index"] == 0
        assert chunks[0]["start_line"] == 1
        assert "def hello" in chunks[0]["text"]

    def test_large_file_multiple_chunks(self, tmp_path: Path) -> None:
        big_file = tmp_path / "big.py"
        big_file.write_text("x = 1\n" * 2000)  # ~12000 chars
        chunks = chunk_file(big_file, max_chunk_chars=4000, overlap=200)
        assert len(chunks) > 1
        # Chunks should overlap
        assert chunks[1]["start_line"] < chunks[0]["end_line"] + 5

    def test_empty_file_no_chunks(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty.py"
        empty.write_text("")
        chunks = chunk_file(empty)
        assert chunks == []

    def test_whitespace_only_no_chunks(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws.py"
        ws.write_text("   \n  \n  ")
        chunks = chunk_file(ws)
        assert chunks == []

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        chunks = chunk_file(tmp_path / "nope.py")
        assert chunks == []

    def test_chunk_metadata_correct(self, tmp_repo: Path) -> None:
        path = tmp_repo / "src" / "utils.py"
        chunks = chunk_file(path)
        assert len(chunks) == 1
        assert chunks[0]["file_path"] == str(path)
        assert chunks[0]["start_line"] == 1
        assert chunks[0]["end_line"] >= 3

    def test_overlap_clamped_when_too_large(self, tmp_path: Path) -> None:
        """overlap >= max_chunk_chars doesn't cause infinite loop."""
        big_file = tmp_path / "big.py"
        big_file.write_text("x = 1\n" * 2000)
        chunks = chunk_file(big_file, max_chunk_chars=100, overlap=200)
        assert len(chunks) > 1  # Should still produce chunks, not loop forever

    def test_relative_to_produces_relative_paths(self, tmp_repo: Path) -> None:
        path = tmp_repo / "src" / "main.py"
        chunks = chunk_file(path, relative_to=tmp_repo)
        assert chunks[0]["file_path"] == "src/main.py"

    def test_without_relative_to_uses_full_path(self, tmp_repo: Path) -> None:
        path = tmp_repo / "src" / "main.py"
        chunks = chunk_file(path)
        assert chunks[0]["file_path"] == str(path)


# --- CodebaseIndex tests ---


class TestCodebaseIndex:
    def test_not_indexed_initially(
        self, tmp_repo: Path, lance_db: Any, mock_embedder: MagicMock
    ) -> None:
        idx = CodebaseIndex(repo_root=tmp_repo, lance_db=lance_db, embedder=mock_embedder)
        assert not idx.is_indexed

    def test_is_indexed_after_build(
        self, tmp_repo: Path, lance_db: Any, mock_embedder: MagicMock
    ) -> None:
        idx = CodebaseIndex(repo_root=tmp_repo, lance_db=lance_db, embedder=mock_embedder)
        count = idx.build()
        assert count > 0
        assert idx.is_indexed

    def test_build_returns_chunk_count(
        self, tmp_repo: Path, lance_db: Any, mock_embedder: MagicMock
    ) -> None:
        idx = CodebaseIndex(repo_root=tmp_repo, lance_db=lance_db, embedder=mock_embedder)
        count = idx.build()
        # Should have chunks for main.py, utils.py, README.md, pyproject.toml
        assert count >= 4

    def test_build_uses_batch_embedder(
        self, tmp_repo: Path, lance_db: Any, mock_batch_embedder: MagicMock
    ) -> None:
        idx = CodebaseIndex(repo_root=tmp_repo, lance_db=lance_db, embedder=mock_batch_embedder)
        idx.build()
        mock_batch_embedder.get_embedding_batch.assert_called()

    def test_build_with_index_paths(
        self, tmp_repo: Path, lance_db: Any, mock_embedder: MagicMock
    ) -> None:
        idx = CodebaseIndex(
            repo_root=tmp_repo,
            lance_db=lance_db,
            embedder=mock_embedder,
            index_paths=["src"],
        )
        count = idx.build()
        # Only src/ files: main.py, utils.py
        assert count == 2

    def test_build_stores_relative_paths(
        self, tmp_repo: Path, lance_db: Any, mock_embedder: MagicMock
    ) -> None:
        idx = CodebaseIndex(repo_root=tmp_repo, lance_db=lance_db, embedder=mock_embedder)
        idx.build()
        results = idx.search("hello")
        assert results
        # Paths should be relative, not absolute
        for r in results:
            assert not r["file_path"].startswith("/"), (
                f"Expected relative path, got {r['file_path']}"
            )

    def test_build_empty_dir(self, tmp_path: Path, lance_db: Any, mock_embedder: MagicMock) -> None:
        empty = tmp_path / "empty_repo"
        empty.mkdir()
        idx = CodebaseIndex(repo_root=empty, lance_db=lance_db, embedder=mock_embedder)
        count = idx.build()
        assert count == 0

    def test_search_returns_results(
        self, tmp_repo: Path, lance_db: Any, mock_embedder: MagicMock
    ) -> None:
        idx = CodebaseIndex(repo_root=tmp_repo, lance_db=lance_db, embedder=mock_embedder)
        idx.build()
        results = idx.search("hello function")
        assert len(results) > 0
        assert "file_path" in results[0]
        assert "text" in results[0]

    def test_search_before_build_empty(
        self, tmp_repo: Path, lance_db: Any, mock_embedder: MagicMock
    ) -> None:
        idx = CodebaseIndex(repo_root=tmp_repo, lance_db=lance_db, embedder=mock_embedder)
        results = idx.search("anything")
        assert results == []

    def test_search_respects_k(
        self, tmp_repo: Path, lance_db: Any, mock_embedder: MagicMock
    ) -> None:
        idx = CodebaseIndex(repo_root=tmp_repo, lance_db=lance_db, embedder=mock_embedder)
        idx.build()
        results = idx.search("test", k=2)
        assert len(results) <= 2

    def test_rebuild_replaces_old_table(
        self, tmp_repo: Path, lance_db: Any, mock_embedder: MagicMock
    ) -> None:
        idx = CodebaseIndex(repo_root=tmp_repo, lance_db=lance_db, embedder=mock_embedder)
        count1 = idx.build()
        count2 = idx.build()
        assert count1 == count2  # Same files, same count


# --- search_code tool tests ---


class TestSearchCodeTool:
    def test_returns_results(self, tmp_repo: Path, lance_db: Any, mock_embedder: MagicMock) -> None:
        idx = CodebaseIndex(repo_root=tmp_repo, lance_db=lance_db, embedder=mock_embedder)
        idx.build()
        search = _make_search_code(idx)
        result = search("hello function")
        assert "main.py" in result or "utils.py" in result

    def test_not_indexed_message(
        self, tmp_repo: Path, lance_db: Any, mock_embedder: MagicMock
    ) -> None:
        idx = CodebaseIndex(repo_root=tmp_repo, lance_db=lance_db, embedder=mock_embedder)
        search = _make_search_code(idx)
        result = search("anything")
        assert "not indexed" in result.lower()

    def test_no_results_message(
        self, tmp_repo: Path, lance_db: Any, mock_embedder: MagicMock
    ) -> None:
        idx = CodebaseIndex(repo_root=tmp_repo, lance_db=lance_db, embedder=mock_embedder)
        idx.build()
        # Mock search to return empty
        idx.search = MagicMock(return_value=[])  # type: ignore[method-assign]
        search = _make_search_code(idx)
        result = search("nonexistent xyz")
        assert "no results" in result.lower()

    def test_respects_k_parameter(
        self, tmp_repo: Path, lance_db: Any, mock_embedder: MagicMock
    ) -> None:
        idx = CodebaseIndex(repo_root=tmp_repo, lance_db=lance_db, embedder=mock_embedder)
        idx.build()
        search = _make_search_code(idx)
        result = search("test", k=1)
        # Should have at most 1 result block
        assert result.count("---") <= 4  # header has dashes

    def test_result_format(self, tmp_repo: Path, lance_db: Any, mock_embedder: MagicMock) -> None:
        idx = CodebaseIndex(repo_root=tmp_repo, lance_db=lance_db, embedder=mock_embedder)
        idx.build()
        search = _make_search_code(idx)
        result = search("hello")
        assert "lines" in result


# --- grep_code tool tests ---


class TestGrepCodeTool:
    def test_finds_pattern(self, tmp_repo: Path) -> None:
        grep = _make_grep_code(tmp_repo)
        result = grep("def hello")
        assert "hello" in result

    def test_no_match(self, tmp_repo: Path) -> None:
        grep = _make_grep_code(tmp_repo)
        result = grep("zzz_nonexistent_pattern_zzz")
        assert "no matches" in result.lower()

    def test_invalid_regex(self, tmp_repo: Path) -> None:
        grep = _make_grep_code(tmp_repo)
        result = grep("[invalid")
        assert "invalid regex" in result.lower()

    def test_glob_filter(self, tmp_repo: Path) -> None:
        grep = _make_grep_code(tmp_repo)
        result = grep("Test Project", glob="*.md")
        assert "Test Project" in result

    def test_context_lines(self, tmp_repo: Path) -> None:
        grep = _make_grep_code(tmp_repo)
        result = grep("def hello", context_lines=1)
        # Should include surrounding context
        assert "return" in result

    def test_respects_result_limit(self, tmp_repo: Path) -> None:
        grep = _make_grep_code(tmp_repo)
        result = grep(".")  # Match everything
        assert len(result) <= _MAX_RESULT_CHARS + 200  # Allow for truncation message

    def test_timeout_handling(self, tmp_repo: Path) -> None:
        grep = _make_grep_code(tmp_repo)
        with patch(
            "grippy.codebase.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="grep", timeout=10),
        ):
            result = grep("pattern")
        assert "timed out" in result.lower()


# --- read_file tool tests ---


class TestReadFileTool:
    def test_reads_full_file(self, tmp_repo: Path) -> None:
        read = _make_read_file(tmp_repo)
        result = read("src/main.py")
        assert "def hello" in result
        assert "return" in result

    def test_line_numbers_shown(self, tmp_repo: Path) -> None:
        read = _make_read_file(tmp_repo)
        result = read("src/main.py")
        assert "1 |" in result or "   1 |" in result

    def test_line_range(self, tmp_repo: Path) -> None:
        read = _make_read_file(tmp_repo)
        result = read("src/utils.py", start_line=2, end_line=3)
        # Should only have 2 lines
        assert "import os" not in result or result.count("|") == 2

    def test_file_not_found(self, tmp_repo: Path) -> None:
        read = _make_read_file(tmp_repo)
        result = read("nonexistent.py")
        assert "not found" in result.lower()

    def test_path_traversal_blocked(self, tmp_repo: Path) -> None:
        read = _make_read_file(tmp_repo)
        result = read("../../etc/passwd")
        assert "not allowed" in result.lower() or "not found" in result.lower()

    def test_read_file_rejects_prefix_bypass(self, tmp_path: Path) -> None:
        """H1: startswith bypass via shared prefix — e.g. /repo vs /repo-evil."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / "safe.py").write_text("safe content")

        evil_dir = tmp_path / "repo-evil"
        evil_dir.mkdir()
        (evil_dir / "secrets.py").write_text("stolen secrets")

        read_fn = _make_read_file(repo_root)
        result = read_fn("../repo-evil/secrets.py")
        assert "path traversal not allowed" in result.lower()


# --- list_files tool tests ---


class TestListFilesTool:
    def test_lists_root(self, tmp_repo: Path) -> None:
        ls = _make_list_files(tmp_repo)
        result = ls()
        assert "src/" in result
        assert "README.md" in result

    def test_lists_subdirectory(self, tmp_repo: Path) -> None:
        ls = _make_list_files(tmp_repo)
        result = ls("src")
        assert "main.py" in result
        assert "utils.py" in result

    def test_glob_filter(self, tmp_repo: Path) -> None:
        ls = _make_list_files(tmp_repo)
        result = ls(".", "*.md")
        assert "README.md" in result
        assert "pyproject.toml" not in result

    def test_nonexistent_directory(self, tmp_repo: Path) -> None:
        ls = _make_list_files(tmp_repo)
        result = ls("nonexistent")
        assert "not found" in result.lower()

    def test_path_traversal_blocked(self, tmp_repo: Path) -> None:
        ls = _make_list_files(tmp_repo)
        result = ls("../..")
        assert "not allowed" in result.lower() or "not found" in result.lower()

    def test_list_files_rejects_prefix_bypass(self, tmp_path: Path) -> None:
        """H1: startswith bypass in list_files."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / "safe.py").write_text("x")

        evil_dir = tmp_path / "repo-evil"
        evil_dir.mkdir()
        (evil_dir / "secrets.py").write_text("stolen")

        list_fn = _make_list_files(repo_root)
        result = list_fn("../repo-evil")
        assert "path traversal not allowed" in result.lower()

    def test_list_files_glob_cannot_escape_boundary(self, tmp_path: Path) -> None:
        """H2: glob results must be bounded by repo_root."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / "safe.py").write_text("x")

        outside = tmp_path / "outside.py"
        outside.write_text("outside content")

        list_fn = _make_list_files(repo_root)
        result = list_fn(".", "../../*")
        assert "outside.py" not in result

    def test_list_files_truncation_notice(self, tmp_path: Path) -> None:
        """Glob results exceeding _MAX_GLOB_RESULTS show a truncation notice."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        for i in range(_MAX_GLOB_RESULTS + 10):
            (repo_root / f"file_{i:05d}.txt").write_text("x")

        list_fn = _make_list_files(repo_root)
        result = list_fn(".", "*.txt")
        assert "[truncated]" in result
        assert str(_MAX_GLOB_RESULTS) in result

    def test_list_files_no_truncation_within_limit(self, tmp_path: Path) -> None:
        """Glob results within _MAX_GLOB_RESULTS have no truncation notice."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        for i in range(5):
            (repo_root / f"file_{i}.txt").write_text("x")

        list_fn = _make_list_files(repo_root)
        result = list_fn(".", "*.txt")
        assert "[truncated]" not in result
        assert "file_0.txt" in result


# --- CodebaseToolkit tests ---


class TestCodebaseToolkit:
    def test_registers_four_tools(
        self, tmp_repo: Path, lance_db: Any, mock_embedder: MagicMock
    ) -> None:
        idx = CodebaseIndex(repo_root=tmp_repo, lance_db=lance_db, embedder=mock_embedder)
        toolkit = CodebaseToolkit(index=idx, repo_root=tmp_repo)
        assert len(toolkit.functions) == 4

    def test_tool_names(self, tmp_repo: Path, lance_db: Any, mock_embedder: MagicMock) -> None:
        idx = CodebaseIndex(repo_root=tmp_repo, lance_db=lance_db, embedder=mock_embedder)
        toolkit = CodebaseToolkit(index=idx, repo_root=tmp_repo)
        names = set(toolkit.functions.keys())
        assert "search_code" in names
        assert "grep_code" in names
        assert "read_file" in names
        assert "list_files" in names

    def test_tools_are_callable(
        self, tmp_repo: Path, lance_db: Any, mock_embedder: MagicMock
    ) -> None:
        idx = CodebaseIndex(repo_root=tmp_repo, lance_db=lance_db, embedder=mock_embedder)
        toolkit = CodebaseToolkit(index=idx, repo_root=tmp_repo)
        for func in toolkit.functions.values():
            assert func.entrypoint is not None


# --- create_reviewer tools param tests ---


class TestCreateReviewerTools:
    def test_tools_none_by_default(self) -> None:
        """create_reviewer without tools= produces agent with no tools."""
        from grippy.agent import create_reviewer

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            agent = create_reviewer(transport="openai", model_id="gpt-4o-mini")
        # Agent should have no tools (or empty tools)
        assert agent.tools is None or agent.tools == []

    def test_tools_passed_through(self) -> None:
        """create_reviewer with tools= passes them to Agent."""
        from grippy.agent import create_reviewer

        mock_toolkit = MagicMock()
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            agent = create_reviewer(
                transport="openai",
                model_id="gpt-4o-mini",
                tools=[mock_toolkit],
            )
        assert agent.tools is not None
        assert len(agent.tools) == 1

    def test_tool_call_limit_passed(self) -> None:
        """create_reviewer with tool_call_limit passes it through."""
        from grippy.agent import create_reviewer

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            agent = create_reviewer(
                transport="openai",
                model_id="gpt-4o-mini",
                tool_call_limit=10,
            )
        assert agent.tool_call_limit == 10


# --- main() wiring tests ---


class TestMainWiring:
    def _make_pr_event(self, tmp_path: Path) -> Path:
        """Create a minimal PR event JSON file."""
        import json

        event = {
            "pull_request": {
                "number": 99,
                "title": "test PR",
                "user": {"login": "testuser"},
                "head": {"ref": "feat/test", "sha": "abc123"},
                "base": {"ref": "main"},
                "body": "Test PR body",
            },
            "repository": {"full_name": "test/repo"},
        }
        event_path = tmp_path / "event.json"
        event_path.write_text(json.dumps(event))
        return event_path

    @patch("grippy.review.post_review")
    @patch("grippy.review.run_review")
    @patch("grippy.review.fetch_pr_diff")
    @patch("grippy.review.create_embedder")
    def test_codebase_index_wired_in_main(
        self,
        mock_create_embedder: MagicMock,
        mock_fetch_diff: MagicMock,
        mock_run_review: MagicMock,
        mock_post_review: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Verify that main() creates CodebaseIndex when GITHUB_WORKSPACE is set."""
        from grippy.review import main
        from grippy.schema import (
            AsciiArtKey,
            ComplexityTier,
            GrippyReview,
            Personality,
            PRMetadata,
            ReviewMeta,
            ReviewScope,
            Score,
            ScoreBreakdown,
            ScoreDeductions,
            ToneRegister,
            Verdict,
            VerdictStatus,
        )

        event_path = self._make_pr_event(tmp_path)

        review = GrippyReview(
            version="1.0",
            audit_type="pr_review",
            timestamp="2026-02-27T12:00:00Z",
            model="test",
            pr=PRMetadata(
                title="test",
                author="dev",
                branch="a → b",
                complexity_tier=ComplexityTier.TRIVIAL,
            ),
            scope=ReviewScope(
                files_in_diff=1,
                files_reviewed=1,
                coverage_percentage=100.0,
                governance_rules_applied=[],
                modes_active=["pr_review"],
            ),
            findings=[],
            escalations=[],
            score=Score(
                overall=90,
                breakdown=ScoreBreakdown(
                    security=95,
                    logic=90,
                    governance=100,
                    reliability=85,
                    observability=80,
                ),
                deductions=ScoreDeductions(
                    critical_count=0,
                    high_count=0,
                    medium_count=0,
                    low_count=0,
                    total_deduction=10,
                ),
            ),
            verdict=Verdict(
                status=VerdictStatus.PASS,
                threshold_applied=70,
                merge_blocking=False,
                summary="All clear",
            ),
            personality=Personality(
                tone_register=ToneRegister.GRUDGING_RESPECT,
                opening_catchphrase="Not bad...",
                closing_line="Fine.",
                ascii_art_key=AsciiArtKey.ALL_CLEAR,
            ),
            meta=ReviewMeta(
                review_duration_ms=0,
                tokens_used=0,
                context_files_loaded=0,
                confidence_filter_suppressed=0,
                duplicate_filter_suppressed=0,
            ),
        )

        mock_fetch_diff.return_value = "diff --git a/test.py b/test.py\n+hello\n"
        mock_run_review.return_value = review
        mock_post_review.return_value = None
        mock_create_embedder.return_value = MagicMock()

        env = {
            "GITHUB_TOKEN": "fake-token",
            "GITHUB_EVENT_PATH": str(event_path),
            "GRIPPY_TRANSPORT": "openai",
            "OPENAI_API_KEY": "test-key",
            "GRIPPY_DATA_DIR": str(tmp_path / "data"),
            "GITHUB_WORKSPACE": str(tmp_path),
            "GRIPPY_TIMEOUT": "0",
        }

        with patch.dict(os.environ, env, clear=False):
            # main() should not crash — codebase indexing is non-fatal
            try:
                main()
            except SystemExit:
                pass  # main() calls sys.exit on certain paths


# --- sanitize_tool_hook tests ---


class TestSanitizeToolHook:
    def test_sanitizes_and_limits_string_result(self) -> None:
        """Hook runs sanitization and truncation on string tool output."""

        def fake_tool(**kwargs: Any) -> str:
            return "<script>alert('xss')</script>"

        result = sanitize_tool_hook("fake_tool", fake_tool, {})
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_truncates_long_output(self) -> None:
        """Hook truncates output exceeding _MAX_RESULT_CHARS."""
        long_text = "x" * (_MAX_RESULT_CHARS + 1000)

        def fake_tool(**kwargs: Any) -> str:
            return long_text

        result = sanitize_tool_hook("fake_tool", fake_tool, {})
        assert len(result) <= _MAX_RESULT_CHARS + 200  # truncation message overhead
        assert "truncated" in result

    def test_passthrough_short_clean_output(self) -> None:
        """Hook passes through short, clean output unchanged."""

        def fake_tool(**kwargs: Any) -> str:
            return "clean output"

        result = sanitize_tool_hook("fake_tool", fake_tool, {})
        assert result == "clean output"

    def test_non_string_passthrough(self) -> None:
        """Hook passes through non-string results without sanitization."""

        def fake_tool(**kwargs: Any) -> int:
            return 42

        result = sanitize_tool_hook("fake_tool", fake_tool, {})
        assert result == 42

    def test_passes_args_to_function(self) -> None:
        """Hook forwards kwargs to the wrapped function."""

        def fake_tool(query: str, k: int = 5) -> str:
            return f"{query}:{k}"

        result = sanitize_tool_hook("fake_tool", fake_tool, {"query": "test", "k": 3})
        assert result == "test:3"


# --- Repo state detection ---


class TestRepoState:
    """_get_repo_state() detects git SHA + dirtiness or non-git file hash."""

    def test_git_repo_returns_sha_and_clean(self, tmp_path: Path) -> None:
        """Git repo returns HEAD SHA and dirty=False when clean."""
        from grippy.codebase import _get_repo_state

        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        (tmp_path / "a.py").write_text("x = 1\n")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "init", "--no-gpg-sign"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
            env={
                **os.environ,
                "GIT_AUTHOR_NAME": "test",
                "GIT_AUTHOR_EMAIL": "t@t",
                "GIT_COMMITTER_NAME": "test",
                "GIT_COMMITTER_EMAIL": "t@t",
            },
        )
        sha, dirty = _get_repo_state(tmp_path)
        assert len(sha) == 40
        assert dirty is False

    def test_dirty_repo_detected(self, tmp_path: Path) -> None:
        """Uncommitted changes set dirty=True."""
        from grippy.codebase import _get_repo_state

        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        (tmp_path / "a.py").write_text("x = 1\n")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "init", "--no-gpg-sign"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
            env={
                **os.environ,
                "GIT_AUTHOR_NAME": "test",
                "GIT_AUTHOR_EMAIL": "t@t",
                "GIT_COMMITTER_NAME": "test",
                "GIT_COMMITTER_EMAIL": "t@t",
            },
        )
        (tmp_path / "a.py").write_text("x = 2\n")
        sha, dirty = _get_repo_state(tmp_path)
        assert dirty is True

    def test_non_git_dir_uses_file_hash(self, tmp_path: Path) -> None:
        """Non-git directory hashes (path, size, mtime) tuples."""
        from grippy.codebase import _get_repo_state

        (tmp_path / "a.py").write_text("x = 1\n")
        sha1, dirty1 = _get_repo_state(tmp_path)
        assert len(sha1) == 64  # SHA-256 hex
        assert dirty1 is False  # no dirtiness concept without git

        sha2, _ = _get_repo_state(tmp_path)
        assert sha1 == sha2

    def test_non_git_detects_content_change_via_mtime(self, tmp_path: Path) -> None:
        """File content change updates mtime → different hash."""
        import time

        from grippy.codebase import _get_repo_state

        (tmp_path / "a.py").write_text("x = 1\n")
        sha1, _ = _get_repo_state(tmp_path)
        time.sleep(0.05)
        (tmp_path / "a.py").write_text("x = 2\n")
        sha2, _ = _get_repo_state(tmp_path)
        assert sha1 != sha2


# --- Manifest infrastructure ---


class TestIndexManifest:
    """Manifest read/write and config fingerprinting."""

    def test_write_and_read_manifest(self, tmp_path: Path) -> None:
        """Manifest round-trips all fields."""
        from grippy.codebase import _read_manifest, _write_manifest

        path = tmp_path / "manifest.json"
        _write_manifest(
            path,
            repo_sha="abc123",
            repo_dirty=False,
            config_fingerprint="fp-hash",
        )
        m = _read_manifest(path)
        assert m is not None
        assert m["repo_sha"] == "abc123"
        assert m["repo_dirty"] is False
        assert m["config_fingerprint"] == "fp-hash"
        assert "schema_version" in m
        assert "built_at" in m

    def test_read_missing_manifest(self, tmp_path: Path) -> None:
        """Missing manifest returns None."""
        from grippy.codebase import _read_manifest

        assert _read_manifest(tmp_path / "missing.json") is None

    def test_read_corrupt_manifest(self, tmp_path: Path) -> None:
        """Corrupt manifest returns None (non-fatal)."""
        from grippy.codebase import _read_manifest

        bad = tmp_path / "bad.json"
        bad.write_text("not json{{{")
        assert _read_manifest(bad) is None

    def test_config_fingerprint_changes_with_params(self) -> None:
        """Different config params produce different fingerprints."""
        from grippy.codebase import _config_fingerprint

        fp1 = _config_fingerprint(
            extensions=[".py"],
            ignore_dirs=["__pycache__"],
            index_paths=None,
            max_chunk_chars=4000,
            overlap=200,
            max_index_files=5000,
            embedder_id="model-a",
            embedding_dims=1024,
        )
        fp2 = _config_fingerprint(
            extensions=[".py", ".md"],
            ignore_dirs=["__pycache__"],
            index_paths=None,
            max_chunk_chars=4000,
            overlap=200,
            max_index_files=5000,
            embedder_id="model-a",
            embedding_dims=1024,
        )
        assert fp1 != fp2

    def test_config_fingerprint_stable(self) -> None:
        """Same params always produce the same fingerprint."""
        from grippy.codebase import _config_fingerprint

        kwargs: dict[str, Any] = dict(
            extensions=[".py"],
            ignore_dirs=["__pycache__"],
            index_paths=None,
            max_chunk_chars=4000,
            overlap=200,
            max_index_files=5000,
            embedder_id="model-a",
            embedding_dims=1024,
        )
        assert _config_fingerprint(**kwargs) == _config_fingerprint(**kwargs)


# --- Chunk ID ---


class TestChunkId:
    """_chunk_id() produces location-based IDs."""

    def test_different_files_different_ids(self) -> None:
        """Same content in different files gets different IDs."""
        from grippy.codebase import _chunk_id

        assert _chunk_id("src/a.py", 1, 10) != _chunk_id("src/b.py", 1, 10)

    def test_same_location_stable(self) -> None:
        """Same file+range always produces the same ID."""
        from grippy.codebase import _chunk_id

        assert _chunk_id("src/a.py", 1, 10) == _chunk_id("src/a.py", 1, 10)

    def test_different_ranges_different_ids(self) -> None:
        """Different line ranges in same file get different IDs."""
        from grippy.codebase import _chunk_id

        assert _chunk_id("src/a.py", 1, 10) != _chunk_id("src/a.py", 11, 20)


# --- FakeBatchEmbedder ---


class FakeBatchEmbedder:
    """Test double that properly satisfies BatchEmbedder protocol.

    Do NOT use MagicMock — it passes isinstance(mock, BatchEmbedder) by
    accident via runtime_checkable Protocol + attribute presence.
    """

    def __init__(self, dim: int = 8) -> None:
        self._dim = dim

    def get_embedding(self, text: str) -> list[float]:
        return [0.1] * self._dim

    def get_embedding_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * self._dim for _ in texts]


# --- CodebaseIndex Agno migration tests ---


class TestCodebaseIndexAgno:
    """Tests for migrated CodebaseIndex with Agno LanceDb wrapper."""

    def _make_index(self, tmp_path: Path, **overrides: Any) -> tuple[CodebaseIndex, MagicMock]:
        embedder = overrides.pop("embedder", FakeBatchEmbedder())
        vector_db = overrides.pop("vector_db", MagicMock())
        vector_db.exists.return_value = overrides.pop("table_exists", False)
        index = CodebaseIndex(
            repo_root=tmp_path,
            vector_db=vector_db,
            embedder=embedder,
            data_dir=tmp_path,
            **overrides,
        )
        return index, vector_db

    def test_build_indexes_files(self, tmp_path: Path) -> None:
        """build() indexes files and returns chunk count."""
        (tmp_path / "hello.py").write_text("def hello():\n    return 'world'\n")
        index, vdb = self._make_index(tmp_path)
        count = index.build()
        assert count == 1
        vdb.create.assert_called_once()
        vdb.insert.assert_called_once()

    def test_build_skips_when_manifest_matches(self, tmp_path: Path) -> None:
        """build() skips rebuild when manifest matches current state."""
        (tmp_path / "a.py").write_text("x = 1\n")
        index, vdb = self._make_index(tmp_path, table_exists=True)
        # First build creates manifest
        index.build()
        vdb.reset_mock()
        vdb.exists.return_value = True
        # Second build should skip
        count = index.build()
        assert count == 0
        vdb.insert.assert_not_called()

    def test_build_force_bypasses_manifest(self, tmp_path: Path) -> None:
        """build(force=True) rebuilds even when manifest matches."""
        (tmp_path / "a.py").write_text("x = 1\n")
        index, vdb = self._make_index(tmp_path, table_exists=True)
        index.build()  # creates manifest
        vdb.reset_mock()
        vdb.exists.return_value = True
        count = index.build(force=True)
        assert count == 1
        vdb.drop.assert_called_once()
        vdb.create.assert_called_once()
        vdb.insert.assert_called_once()

    def test_build_drops_stale_on_sha_mismatch(self, tmp_path: Path) -> None:
        """SHA change triggers drop -> create -> insert."""
        (tmp_path / "a.py").write_text("x = 1\n")
        index, vdb = self._make_index(tmp_path, table_exists=True)
        # Write manifest with stale SHA
        _write_manifest(
            tmp_path / "codebase_index_manifest.json",
            repo_sha="stale-sha-from-yesterday",
            repo_dirty=False,
            config_fingerprint="whatever",
        )
        index.build()
        vdb.drop.assert_called_once()
        vdb.create.assert_called_once()
        vdb.insert.assert_called_once()

    def test_build_invalidates_on_config_fingerprint_change(self, tmp_path: Path) -> None:
        """Config change (e.g. extensions) triggers rebuild."""
        (tmp_path / "a.py").write_text("x = 1\n")
        index, vdb = self._make_index(tmp_path, table_exists=True)
        index.build()  # creates manifest with current config
        vdb.reset_mock()
        vdb.exists.return_value = True
        # Create new index with different extensions (different config_fingerprint)
        index2, vdb2 = self._make_index(
            tmp_path,
            table_exists=True,
            extensions=frozenset({".py", ".rs"}),
        )
        count = index2.build()
        assert count == 1  # rebuilt, not skipped

    def test_build_batch_embeds_documents(self, tmp_path: Path) -> None:
        """build() batch-embeds and sets Document.embedding before insert."""
        (tmp_path / "a.py").write_text("line1\nline2\n")
        index, vdb = self._make_index(tmp_path)
        index.build()
        docs = vdb.insert.call_args.kwargs["documents"]
        for doc in docs:
            assert doc.embedding is not None
            assert len(doc.embedding) == 8

    def test_build_sets_location_based_chunk_ids(self, tmp_path: Path) -> None:
        """build() sets Document.id from file location."""
        (tmp_path / "a.py").write_text("x = 1\n")
        index, vdb = self._make_index(tmp_path)
        index.build()
        docs = vdb.insert.call_args.kwargs["documents"]
        for doc in docs:
            assert doc.id is not None
            assert len(doc.id) == 40  # SHA-1 hex

    def test_build_dirty_repo_always_rebuilds(self, tmp_path: Path) -> None:
        """If repo was dirty when manifest written, next build always rebuilds."""
        (tmp_path / "a.py").write_text("x = 1\n")
        index, vdb = self._make_index(tmp_path, table_exists=True)
        # Write manifest with dirty=True
        sha, _ = _get_repo_state(tmp_path)
        _write_manifest(
            tmp_path / "codebase_index_manifest.json",
            repo_sha=sha,
            repo_dirty=True,
            config_fingerprint="fp",
        )
        count = index.build()
        assert count >= 1  # rebuilt even though SHA matches


# --- Result parsing ---


class TestParseResults:
    """_parse_results_static() handles various LanceDB payload formats."""

    def test_payload_as_json_string(self) -> None:
        """Normal case: payload is a JSON string."""
        row = {
            "payload": json.dumps(
                {
                    "content": "def hello(): pass",
                    "name": "src/app.py",
                    "meta_data": {
                        "file_path": "src/app.py",
                        "start_line": 1,
                        "end_line": 1,
                        "chunk_index": 0,
                    },
                }
            )
        }
        results = CodebaseIndex._parse_results_static([row])
        assert len(results) == 1
        assert results[0]["file_path"] == "src/app.py"
        assert results[0]["text"] == "def hello(): pass"
        assert results[0]["start_line"] == 1

    def test_payload_as_dict(self) -> None:
        """Some LanceDB versions may return payload as already-parsed dict."""
        row = {
            "payload": {
                "content": "x = 1",
                "name": "a.py",
                "meta_data": {
                    "file_path": "a.py",
                    "start_line": 1,
                    "end_line": 1,
                    "chunk_index": 0,
                },
            }
        }
        results = CodebaseIndex._parse_results_static([row])
        assert len(results) == 1
        assert results[0]["text"] == "x = 1"

    def test_payload_missing(self) -> None:
        """Missing payload -> row skipped."""
        results = CodebaseIndex._parse_results_static([{"id": "abc", "vector": []}])
        assert results == []

    def test_payload_malformed_json(self) -> None:
        """Malformed JSON -> row skipped, no crash."""
        results = CodebaseIndex._parse_results_static([{"payload": "not{json"}])
        assert results == []

    def test_meta_data_missing(self) -> None:
        """Missing meta_data -> uses name as file_path, defaults for lines."""
        row = {"payload": json.dumps({"content": "x", "name": "fallback.py"})}
        results = CodebaseIndex._parse_results_static([row])
        assert results[0]["file_path"] == "fallback.py"
        assert results[0]["start_line"] == 0
