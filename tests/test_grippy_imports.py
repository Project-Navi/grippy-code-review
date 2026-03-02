# SPDX-License-Identifier: MIT
"""Tests for Python import extraction."""

from __future__ import annotations

from pathlib import Path

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
