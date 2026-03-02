# SPDX-License-Identifier: MIT
"""Python import extraction for dependency graph edges.

Uses stdlib ast module to parse imports and resolve them to repo-relative
file paths. Only emits edges for in-repo files (skips stdlib/third-party).
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path

log = logging.getLogger(__name__)


def resolve_import_to_path(
    module: str,
    search_root: Path,
) -> str | None:
    """Resolve a dotted module name to a repo-relative file path.

    Checks for both module.py and module/__init__.py under search_root.
    Returns None if not resolvable to an in-repo file.
    """
    parts = module.split(".")
    # Try as a .py file
    candidate = search_root / Path(*parts).with_suffix(".py")
    if candidate.is_file():
        try:
            return str(candidate.relative_to(search_root.parent))
        except ValueError:
            return str(candidate.relative_to(search_root))

    # Try as a package (__init__.py)
    candidate = search_root / Path(*parts) / "__init__.py"
    if candidate.is_file():
        try:
            return str(candidate.relative_to(search_root.parent))
        except ValueError:
            return str(candidate.relative_to(search_root))

    return None


def _resolve_relative_import(
    module: str | None,
    level: int,
    file_path: Path,
    repo_root: Path,
) -> str | None:
    """Resolve a relative import to a repo-relative file path."""
    pkg_dir = file_path.parent
    for _ in range(level - 1):
        pkg_dir = pkg_dir.parent

    if module:
        parts = module.split(".")
        candidate = pkg_dir / Path(*parts).with_suffix(".py")
        if candidate.is_file():
            return str(candidate.relative_to(repo_root))
        candidate = pkg_dir / Path(*parts) / "__init__.py"
        if candidate.is_file():
            return str(candidate.relative_to(repo_root))
    return None


def extract_imports(file_path: Path, repo_root: Path) -> list[str]:
    """Extract resolved in-repo import paths from a Python file.

    Returns deduplicated list of repo-relative paths. Skips stdlib,
    third-party, and unresolvable imports. Handles syntax errors gracefully.
    """
    try:
        source = file_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(file_path))
    except (SyntaxError, OSError):
        return []

    # Find all search roots (directories containing packages)
    search_roots = _find_search_roots(repo_root)

    resolved: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                path = _try_resolve(alias.name, search_roots)
                if path:
                    resolved.append(path)
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                # Relative import
                path = _resolve_relative_import(
                    node.module,
                    node.level,
                    file_path,
                    repo_root,
                )
                if path:
                    resolved.append(path)
            elif node.module:
                path = _try_resolve(node.module, search_roots)
                if path:
                    resolved.append(path)

    return list(dict.fromkeys(resolved))


def _try_resolve(module: str, search_roots: list[Path]) -> str | None:
    """Try resolving a module against multiple search roots."""
    for root in search_roots:
        result = resolve_import_to_path(module, root)
        if result:
            return result
    return None


def _find_search_roots(repo_root: Path) -> list[Path]:
    """Find Python source roots in the repo (directories with packages)."""
    roots: list[Path] = []
    # Common patterns: src/, lib/, .
    for candidate in ["src", "lib", "."]:
        path = repo_root / candidate
        if path.is_dir():
            roots.append(path)
    return roots or [repo_root]
