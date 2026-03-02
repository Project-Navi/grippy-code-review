# SPDX-License-Identifier: MIT
"""Pre-review context builder — queries the graph for blast radius + history."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import navi_sanitize

from grippy.graph_store import SQLiteGraphStore
from grippy.graph_types import _record_id


@dataclass
class ContextPack:
    """Pre-review context extracted from the graph store."""

    touched_files: list[str]
    blast_radius_files: list[tuple[str, int]]  # (path, dependent_count)
    recurring_findings: list[dict[str, Any]]
    file_history: dict[str, list[str]]  # file_path -> history observations
    author_risk_summary: dict[str, int] = field(default_factory=dict)


def build_context_pack(
    store: SQLiteGraphStore,
    touched_files: list[str],
    author_login: str | None = None,
) -> ContextPack:
    """Query graph for pre-review context. Non-fatal — empty on errors."""
    blast: list[tuple[str, int]] = []
    recurring: list[dict[str, Any]] = []
    file_history: dict[str, list[str]] = {}
    author_summary: dict[str, int] = {}

    # Blast radius: walk IMPORTS incoming from all touched files at once
    touched_ids = [_record_id("FILE", p) for p in touched_files]
    if touched_ids:
        walk_result = store.walk(
            touched_ids,
            max_depth=2,
            max_nodes=30,
            rel_allow=["IMPORTS"],
            direction="incoming",
        )
        # Count dependents per touched file (exclude the file itself)
        touched_set = set(touched_ids)
        for node in walk_result.nodes:
            if node.id not in touched_set:
                path = node.data.get("path", node.id)
                blast.append((path, 1))  # simplified count

    for path in touched_files:
        fid = _record_id("FILE", path)

        # Prior findings in this file
        findings_nb = store.neighbors(fid, direction="incoming", rel_filter=["FOUND_IN"])
        for _edge, finding_node in findings_nb.incoming:
            recurring.append(
                {
                    "file": path,
                    "fingerprint": finding_node.data.get("fingerprint", ""),
                    "severity": finding_node.data.get("severity", "UNKNOWN"),
                    "title": finding_node.data.get("title", ""),
                }
            )

        # File history from observations (filtered to history kind)
        obs = store.get_observations(fid, kind="history")
        if obs:
            file_history[path] = obs

    # Author history
    if author_login:
        author_id = _record_id("AUTHOR", author_login)
        result = store.walk(
            [author_id],
            max_depth=2,
            max_nodes=100,
            rel_allow=["AUTHORED", "PRODUCED"],
        )
        for n in result.nodes:
            if n.type == "FINDING":
                sev = n.data.get("severity", "UNKNOWN")
                author_summary[sev] = author_summary.get(sev, 0) + 1

    return ContextPack(
        touched_files=touched_files,
        blast_radius_files=sorted(blast, key=lambda x: x[1], reverse=True),
        recurring_findings=recurring,
        file_history=file_history,
        author_risk_summary=author_summary,
    )


def format_context_for_llm(pack: ContextPack, max_chars: int = 2000) -> str:
    """Format context pack as sanitized text for LLM prompt context."""
    if not pack.touched_files:
        return ""

    lines: list[str] = []

    if pack.blast_radius_files:
        lines.append("Files with downstream dependents:")
        for path, count in pack.blast_radius_files[:10]:
            lines.append(f"- {path}: imported by {count} module(s)")
        lines.append("")

    if pack.recurring_findings:
        lines.append("Prior findings in changed files:")
        for f in pack.recurring_findings[:10]:
            sev = navi_sanitize.clean(str(f.get("severity", "UNKNOWN")))
            title = navi_sanitize.clean(str(f.get("title", "")))
            lines.append(f"- {f['file']}: {sev} — {title}")
        lines.append("")

    if pack.file_history:
        lines.append("File history:")
        for path, obs in list(pack.file_history.items())[:5]:
            for o in obs[-3:]:  # last 3 observations per file
                lines.append(f"- {path}: {o}")
        lines.append("")

    if pack.author_risk_summary:
        parts = [f"{count}x {sev}" for sev, count in sorted(pack.author_risk_summary.items())]
        lines.append(f"Author history: {', '.join(parts)}")
        lines.append("")

    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[: max_chars - 20] + "\n... (truncated)"
    return text
