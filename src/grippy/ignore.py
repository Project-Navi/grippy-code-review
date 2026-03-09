# SPDX-License-Identifier: MIT
"""Suppression mechanisms: .grippyignore file filtering and # nogrip line pragma."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

import pathspec

if TYPE_CHECKING:
    from grippy.rules.context import RuleContext

log = logging.getLogger(__name__)

# Permissive rule-ID charset — validation against known IDs happens at check time.
NOGRIP_RE = re.compile(r"#\s*nogrip(?::\s*(\S[^\n]*?))?\s*$")

_FILE_HEADER_RE_SPLIT = re.compile(r"(?=^diff --git )", re.MULTILINE)


def parse_nogrip(line: str) -> set[str] | bool | None:
    """Parse a # nogrip pragma from a source line.

    Returns:
        True if bare ``# nogrip`` (suppress all rules).
        A set of rule IDs if ``# nogrip: id1, id2``.
        None if no pragma found OR if targeted syntax is malformed
        (empty after colon). Malformed must never widen suppression.
    """
    m = NOGRIP_RE.search(line)
    if m is None:
        return None
    ids_str = m.group(1)
    if ids_str is None:
        return True
    ids = {rid.strip() for rid in ids_str.split(",") if rid.strip()}
    if not ids:
        return None  # empty after colon — malformed, not a blanket suppress
    return ids


def load_grippyignore(repo_root: Path | None) -> pathspec.PathSpec | None:
    """Load .grippyignore from repo root. Returns None if not found."""
    if repo_root is None:
        return None
    ignore_path = repo_root / ".grippyignore"
    if not ignore_path.is_file():
        return None
    try:
        text = ignore_path.read_text(encoding="utf-8")
        return pathspec.PathSpec.from_lines("gitignore", text.splitlines())
    except Exception:
        log.warning("Failed to parse .grippyignore (non-fatal)", exc_info=True)
        return None


def filter_diff(diff: str, spec: pathspec.PathSpec | None) -> tuple[str, int]:
    """Remove files matching a pathspec from a unified diff.

    If all diff chunks are excluded, returns empty string regardless
    of any preamble text. Emptiness is determined by remaining diff
    headers, not by str.strip().

    Returns:
        Tuple of (filtered_diff, excluded_file_count).
    """
    if spec is None or not diff.strip():
        return diff, 0

    chunks = _FILE_HEADER_RE_SPLIT.split(diff)
    kept: list[str] = []
    excluded = 0
    has_diff_chunks = False

    for chunk in chunks:
        if not chunk.startswith("diff --git "):
            kept.append(chunk)  # preamble before first diff header
            continue
        # Extract path from "diff --git a/... b/<path>"
        first_line = chunk.split("\n", 1)[0]
        parts = first_line.split(" b/", 1)
        if len(parts) < 2:
            kept.append(chunk)
            has_diff_chunks = True
            continue
        file_path = parts[1]
        if spec.match_file(file_path):
            excluded += 1
        else:
            kept.append(chunk)
            has_diff_chunks = True

    if not has_diff_chunks:
        return "", excluded

    return "".join(kept), excluded


def build_nogrip_index(ctx: RuleContext) -> dict[tuple[str, int], set[str] | bool]:
    """Build a lookup of (file, lineno) -> nogrip pragma from parsed diff.

    Uses the original added-line content from the diff parser, NOT the
    truncated evidence field. This ensures pragmas past char 120 are
    still detected.
    """
    index: dict[tuple[str, int], set[str] | bool] = {}
    for f in ctx.files:
        for hunk in f.hunks:
            for line in hunk.lines:
                if line.type == "add" and line.new_lineno is not None:
                    nogrip = parse_nogrip(line.content)
                    if nogrip is not None:
                        index[(f.path, line.new_lineno)] = nogrip
    return index
