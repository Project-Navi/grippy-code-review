# SPDX-License-Identifier: MIT
"""Tests for Python import extraction."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from grippy.imports import extract_imports, resolve_import_to_path


class TestResolveImportToPath:
    def test_dotted_module(self, tmp_path: Path) -> None:
        (tmp_path / "src" / "grippy").mkdir(parents=True)
        (tmp_path / "src" / "grippy" / "agent.py").write_text("")
        result = resolve_import_to_path("grippy.agent", tmp_path / "src")
        assert result == "src/grippy/agent.py"

    def test_package_init(self, tmp_path: Path) -> None:
        (tmp_path / "src" / "grippy").mkdir(parents=True)
        (tmp_path / "src" / "grippy" / "__init__.py").write_text("")
        result = resolve_import_to_path("grippy", tmp_path / "src")
        assert result == "src/grippy/__init__.py"

    def test_unresolvable_returns_none(self, tmp_path: Path) -> None:
        result = resolve_import_to_path("nonexistent.module", tmp_path)
        assert result is None

    def test_stdlib_returns_none(self, tmp_path: Path) -> None:
        result = resolve_import_to_path("os.path", tmp_path)
        assert result is None

    def test_resolve_py_file_valueerror_fallback(self, tmp_path: Path) -> None:
        """ValueError fallback for .py files when relative_to(parent) fails."""
        (tmp_path / "src" / "grippy").mkdir(parents=True)
        (tmp_path / "src" / "grippy" / "agent.py").write_text("")
        search_root = tmp_path / "src"
        original = Path.relative_to

        def _raise_on_parent(self: Path, other: Path) -> Path:
            # Force ValueError when resolving relative to search_root.parent
            if other == search_root.parent:
                raise ValueError("forced")
            return original(self, other)

        with patch.object(Path, "relative_to", _raise_on_parent):
            result = resolve_import_to_path("grippy.agent", search_root)
        assert result is not None
        assert result.endswith("grippy/agent.py")

    def test_resolve_package_valueerror_fallback(self, tmp_path: Path) -> None:
        """ValueError fallback for __init__.py when relative_to(parent) fails."""
        (tmp_path / "src" / "grippy").mkdir(parents=True)
        (tmp_path / "src" / "grippy" / "__init__.py").write_text("")
        search_root = tmp_path / "src"
        original = Path.relative_to

        def _raise_on_parent(self: Path, other: Path) -> Path:
            if other == search_root.parent:
                raise ValueError("forced")
            return original(self, other)

        with patch.object(Path, "relative_to", _raise_on_parent):
            result = resolve_import_to_path("grippy", search_root)
        assert result is not None
        assert result.endswith("grippy/__init__.py")


class TestExtractImports:
    def test_import_statement(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        pkg = src / "grippy"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "agent.py").write_text("import grippy.schema\n")
        (pkg / "schema.py").write_text("")
        result = extract_imports(pkg / "agent.py", tmp_path)
        assert "src/grippy/schema.py" in result

    def test_from_import(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        pkg = src / "grippy"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "agent.py").write_text("from grippy.schema import GrippyReview\n")
        (pkg / "schema.py").write_text("")
        result = extract_imports(pkg / "agent.py", tmp_path)
        assert "src/grippy/schema.py" in result

    def test_skips_stdlib(self, tmp_path: Path) -> None:
        f = tmp_path / "app.py"
        f.write_text("import os\nimport json\n")
        result = extract_imports(f, tmp_path)
        assert result == []

    def test_handles_syntax_error(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.py"
        f.write_text("def broken(\n")
        result = extract_imports(f, tmp_path)
        assert result == []

    def test_relative_import(self, tmp_path: Path) -> None:
        pkg = tmp_path / "grippy"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "agent.py").write_text("from .schema import X\n")
        (pkg / "schema.py").write_text("")
        result = extract_imports(pkg / "agent.py", tmp_path)
        assert "grippy/schema.py" in result

    def test_deduplicates(self, tmp_path: Path) -> None:
        pkg = tmp_path / "grippy"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "agent.py").write_text("from .schema import A\nfrom .schema import B\n")
        (pkg / "schema.py").write_text("")
        result = extract_imports(pkg / "agent.py", tmp_path)
        assert result.count("grippy/schema.py") == 1

    def test_relative_import_parent_level(self, tmp_path: Path) -> None:
        """Level-2 relative import (from ..target import X) resolves correctly."""
        pkg = tmp_path / "pkg"
        sub = pkg / "sub"
        sub.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (sub / "__init__.py").write_text("")
        (pkg / "target.py").write_text("")
        (sub / "mod.py").write_text("from ..target import X\n")
        result = extract_imports(sub / "mod.py", tmp_path)
        assert "pkg/target.py" in result

    def test_relative_import_to_package(self, tmp_path: Path) -> None:
        """Relative import resolving to a package __init__.py (not a .py file)."""
        pkg = tmp_path / "pkg"
        sub = pkg / "sub"
        sub.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (sub / "__init__.py").write_text("")
        # Use `from .sub import X` — AST gives module="sub", level=1.
        # sub.py does NOT exist, so it falls through to sub/__init__.py.
        (pkg / "mod.py").write_text("from .sub import X\n")
        result = extract_imports(pkg / "mod.py", tmp_path)
        assert "pkg/sub/__init__.py" in result

    def test_relative_import_unresolvable(self, tmp_path: Path) -> None:
        """Relative import that resolves to neither .py nor __init__.py returns None."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        # Reference a module that doesn't exist as .py or package
        (pkg / "mod.py").write_text("from .nonexistent import X\n")
        result = extract_imports(pkg / "mod.py", tmp_path)
        assert result == []

    def test_relative_import_level_exceeds_depth(self, tmp_path: Path) -> None:
        """Level traversal that escapes repo root returns None, not ValueError."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        # level=5 far exceeds directory depth — would escape repo root
        (pkg / "mod.py").write_text("from .....deep import X\n")
        result = extract_imports(pkg / "mod.py", tmp_path)
        assert result == []

    def test_relative_import_outside_repo_py_file(self, tmp_path: Path) -> None:
        """Resolved .py candidate outside repo root is safely ignored."""
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "target.py").write_text("")
        repo = tmp_path / "repo"
        pkg = repo / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        # level=3 escapes repo/ into tmp_path, could find outside/target.py
        (pkg / "mod.py").write_text("from ...outside.target import X\n")
        result = extract_imports(pkg / "mod.py", repo)
        assert result == []

    def test_relative_import_outside_repo_package(self, tmp_path: Path) -> None:
        """Resolved __init__.py candidate outside repo root is safely ignored."""
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "__init__.py").write_text("")
        repo = tmp_path / "repo"
        pkg = repo / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        # level=3 escapes repo/ into tmp_path, resolves to outside/__init__.py
        (pkg / "mod.py").write_text("from ...outside import X\n")
        result = extract_imports(pkg / "mod.py", repo)
        assert result == []

    def test_from_dot_import_none_module(self, tmp_path: Path) -> None:
        """'from . import X' has module=None — should not crash."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("from . import something\n")
        # module is None for bare relative imports — _resolve_relative_import
        # short-circuits on the `if module:` guard
        result = extract_imports(pkg / "mod.py", tmp_path)
        # "something" doesn't exist as a file, so nothing resolves
        assert result == []

    def test_extract_imports_empty_file(self, tmp_path: Path) -> None:
        """Empty Python file produces no imports."""
        f = tmp_path / "empty.py"
        f.write_text("")
        result = extract_imports(f, tmp_path)
        assert result == []

    def test_extract_imports_os_error(self, tmp_path: Path) -> None:
        """Unreadable file returns empty list, not an exception."""
        f = tmp_path / "missing.py"
        # File doesn't exist — triggers OSError in read_text()
        result = extract_imports(f, tmp_path)
        assert result == []
