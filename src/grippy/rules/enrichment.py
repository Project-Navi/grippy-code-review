# SPDX-License-Identifier: MIT
"""Post-processor that enriches rule results with graph-derived context."""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import replace
from typing import TYPE_CHECKING

from grippy.graph_types import EdgeType, NodeType, _record_id
from grippy.rules.base import ResultEnrichment, RuleResult

if TYPE_CHECKING:
    from grippy.graph_store import SQLiteGraphStore

log = logging.getLogger(__name__)

# --- Import-based suppression map ---
# rule_id -> list of import path substrings that suppress it
_SUPPRESSION_MAP: dict[str, list[str]] = {
    "sql-injection-risk": ["sqlalchemy", "django/db", "peewee", "tortoise"],
    "hardcoded-credentials": ["pydantic_settings", "dynaconf"],
}

# rule_id -> list of file path substrings that suppress it
_PATH_SUPPRESSION_MAP: dict[str, list[str]] = {
    "weak-crypto": ["cache", "checksum", "hash", "etag", "fingerprint"],
}


def enrich_results(
    results: list[RuleResult],
    graph_store: SQLiteGraphStore | None,
) -> list[RuleResult]:
    """Enrich rule results with graph-derived context.

    If graph_store is None, returns results unchanged.
    Non-fatal — any graph query failure logs a warning and falls back to defaults.
    """
    if graph_store is None or not results:
        return results

    try:
        return _do_enrich(results, graph_store)
    except Exception:
        log.warning("Rule enrichment failed (non-fatal)", exc_info=True)
        return results


def _do_enrich(
    results: list[RuleResult],
    store: SQLiteGraphStore,
) -> list[RuleResult]:
    """Internal enrichment — all four passes."""
    unique_files = list(dict.fromkeys(r.file for r in results))
    unique_pairs = list(dict.fromkeys((r.rule_id, r.file) for r in results))

    # Pre-compute per-file data
    blast = _compute_blast_radius(store, unique_files)
    recurrence = _compute_recurrence(store, unique_pairs)
    suppression = _compute_suppression(store, unique_files, results)
    velocity = _compute_velocity(store, results)

    enriched: list[RuleResult] = []
    for r in results:
        br = blast.get(r.file, 0)
        rec_key = (r.rule_id, r.file)
        is_rec, prior = recurrence.get(rec_key, (False, 0))
        sup, sup_reason = suppression.get((r.rule_id, r.file), (False, ""))
        vel = velocity.get(r.rule_id, "")

        enriched.append(
            replace(
                r,
                enrichment=ResultEnrichment(
                    blast_radius=br,
                    is_recurring=is_rec,
                    prior_count=prior,
                    suppressed=sup,
                    suppression_reason=sup_reason,
                    velocity=vel,
                ),
            )
        )
    return enriched


def _compute_blast_radius(
    store: SQLiteGraphStore,
    files: list[str],
) -> dict[str, int]:
    """Count incoming IMPORTS edges for each file (1-hop dependents)."""
    result: dict[str, int] = {}
    for path in files:
        fid = _record_id(NodeType.FILE, path)
        nb = store.neighbors(fid, direction="incoming", rel_filter=[EdgeType.IMPORTS])
        result[path] = len(nb.incoming)
    return result


def _compute_recurrence(
    store: SQLiteGraphStore,
    pairs: list[tuple[str, str]],
) -> dict[tuple[str, str], tuple[bool, int]]:
    """Check prior findings for each (rule_id, file) pair."""
    result: dict[tuple[str, str], tuple[bool, int]] = {}
    for rule_id, path in pairs:
        fid = _record_id(NodeType.FILE, path)
        nb = store.neighbors(fid, direction="incoming", rel_filter=[EdgeType.FOUND_IN])
        count = sum(1 for _edge, node in nb.incoming if node.data.get("rule_id") == rule_id)
        result[(rule_id, path)] = (count > 0, count)
    return result


def _compute_suppression(
    store: SQLiteGraphStore,
    files: list[str],
    results: list[RuleResult],
) -> dict[tuple[str, str], tuple[bool, str]]:
    """Check import-based and path-based suppression for each (rule_id, file)."""
    # Build import cache per file
    imports_cache: dict[str, list[str]] = {}
    for path in files:
        fid = _record_id(NodeType.FILE, path)
        nb = store.neighbors(fid, direction="outgoing", rel_filter=[EdgeType.IMPORTS])
        import_paths = [node.data.get("path", node.id) for _edge, node in nb.outgoing]
        imports_cache[path] = import_paths

    out: dict[tuple[str, str], tuple[bool, str]] = {}
    for r in results:
        key = (r.rule_id, r.file)
        if key in out:
            continue

        # Path-based suppression
        if r.rule_id in _PATH_SUPPRESSION_MAP:
            lower_path = r.file.lower()
            for substr in _PATH_SUPPRESSION_MAP[r.rule_id]:
                if substr in lower_path:
                    out[key] = (True, f"file path contains '{substr}'")
                    break
            if key in out:
                continue

        # Import-based suppression
        if r.rule_id in _SUPPRESSION_MAP:
            file_imports = imports_cache.get(r.file, [])
            for imp in file_imports:
                imp_lower = imp.lower()
                for substr in _SUPPRESSION_MAP[r.rule_id]:
                    if substr in imp_lower:
                        out[key] = (True, f"file imports {substr}")
                        break
                if key in out:
                    break

        if key not in out:
            out[key] = (False, "")
    return out


def _compute_velocity(
    store: SQLiteGraphStore,
    results: list[RuleResult],
) -> dict[str, str]:
    """Count findings by rule_id across recent reviews."""
    rule_ids = list(dict.fromkeys(r.rule_id for r in results))

    # Get recent reviews
    recent_reviews = store.get_recent_nodes(limit=20, types=[NodeType.REVIEW])
    if not recent_reviews:
        return dict.fromkeys(rule_ids, "")

    # Collect all findings from recent reviews
    rule_counts: Counter[str] = Counter()
    for review_node in recent_reviews:
        nb = store.neighbors(review_node.id, direction="outgoing", rel_filter=[EdgeType.PRODUCED])
        for _edge, finding_node in nb.outgoing:
            rid = finding_node.data.get("rule_id", "")
            if rid:
                rule_counts[rid] += 1

    out: dict[str, str] = {}
    for rid in rule_ids:
        count = rule_counts.get(rid, 0)
        if count > 0:
            out[rid] = f"{count} {rid} finding(s) across last {len(recent_reviews)} reviews"
        else:
            out[rid] = ""
    return out
