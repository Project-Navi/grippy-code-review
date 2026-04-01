# SPDX-License-Identifier: MIT
"""Grippy MCP server -- exposes scan_diff and audit_diff as FastMCP tools."""

from __future__ import annotations

import json
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from grippy.graph_store import SQLiteGraphStore
from grippy.ignore import filter_diff, load_grippyignore
from grippy.local_diff import DiffError, diff_stats, get_local_diff, get_repo_root
from grippy.mcp_response import serialize_audit, serialize_scan
from grippy.review import _format_rule_findings, truncate_diff
from grippy.rules import check_gate, load_profile, run_rules
from grippy.rules.base import RuleResult
from grippy.rules.enrichment import enrich_results

mcp = FastMCP(
    "grippy",
    instructions=(
        "Grippy is a security-focused code review agent. "
        "Use scan_diff for fast deterministic checks (no LLM). "
        "Use audit_diff for full AI-powered review (requires LLM config)."
    ),
)


def _json_error(message: str) -> str:
    """Return a JSON-encoded error response."""
    return json.dumps({"error": message})


# ---------------------------------------------------------------------------
# Inner helpers
# ---------------------------------------------------------------------------


def _load_graph_store() -> SQLiteGraphStore | None:
    """Load graph store from GRIPPY_DATA_DIR if available."""
    data_dir = os.environ.get("GRIPPY_DATA_DIR", "./grippy-data")
    db_path = Path(data_dir) / "navi-graph.db"
    if not db_path.exists():
        return None
    try:
        return SQLiteGraphStore(db_path=db_path)
    except Exception:
        return None


def _run_scan(scope: str = "staged", profile: str = "security") -> str:
    """Run deterministic rules and return JSON results."""
    try:
        profile_config = load_profile(cli_profile=profile)
    except ValueError as exc:
        return _json_error(str(exc))

    try:
        diff = get_local_diff(scope)
    except DiffError as exc:
        return _json_error(str(exc))

    # Filter ignored files
    repo_root = get_repo_root()
    spec = load_grippyignore(repo_root)
    diff, _excluded = filter_diff(diff, spec)

    stats = diff_stats(diff)

    findings: list[RuleResult] = []
    gate_failed = False
    if diff and profile_config.name != "general":
        findings = run_rules(diff, profile_config)
        findings = enrich_results(findings, _load_graph_store())
        gate_failed = check_gate(findings, profile_config)

    return json.dumps(
        serialize_scan(findings, gate=gate_failed, profile=profile_config.name, diff_stats=stats)
    )


def _run_audit(scope: str = "staged", profile: str = "security") -> str:
    """Run full LLM-powered review and return JSON results."""
    try:
        profile_config = load_profile(cli_profile=profile)
    except ValueError as exc:
        return _json_error(str(exc))

    try:
        diff = get_local_diff(scope)
    except DiffError as exc:
        return _json_error(str(exc))

    # Filter ignored files
    repo_root = get_repo_root()
    spec = load_grippyignore(repo_root)
    diff, _excluded = filter_diff(diff, spec)

    if not diff:
        return _json_error("Empty diff — nothing to review")

    stats = diff_stats(diff)

    # Run deterministic rules on full diff (if profile is not general)
    rule_findings: list[RuleResult] = []
    mode = "pr_review"
    if profile_config.name != "general":
        rule_findings = run_rules(diff, profile_config)
        rule_findings = enrich_results(rule_findings, _load_graph_store())
        mode = "security_audit"

    # Truncate diff for LLM context window
    original_len = len(diff)
    diff = truncate_diff(diff)
    diff_truncated = len(diff) < original_len

    # Read model config from env
    base_url = os.environ.get("GRIPPY_BASE_URL", "http://localhost:1234/v1")
    model_id = os.environ.get("GRIPPY_MODEL_ID", "devstral-small-2-24b-instruct-2512")
    api_key = os.environ.get("GRIPPY_API_KEY", "lm-studio")
    transport = os.environ.get("GRIPPY_TRANSPORT") or None

    # Late imports to avoid heavy dependencies for scan_diff
    from grippy.agent import create_reviewer, format_pr_context
    from grippy.retry import ReviewParseError, run_review

    try:
        agent = create_reviewer(
            model_id=model_id,
            base_url=base_url,
            api_key=api_key,
            transport=transport,
            mode=mode,
            include_rule_findings=bool(rule_findings),
        )
    except ValueError as exc:
        return _json_error(f"Config error: {exc}")
    except Exception:
        return _json_error("Failed to initialize review agent")

    # Format rule findings text
    rule_findings_text = ""
    if rule_findings:
        rule_findings_text = _format_rule_findings(rule_findings)

    user_message = format_pr_context(
        title="Local diff review",
        author="local",
        branch=scope,
        diff=diff,
        rule_findings=rule_findings_text,
    )

    try:
        review = run_review(agent, user_message, mode=mode, diff=diff)
    except ReviewParseError as exc:
        return _json_error(f"Review failed after {exc.attempts} attempts")
    except Exception as exc:
        return _json_error(f"Review failed: {type(exc).__name__}")

    review.model = model_id

    return json.dumps(
        serialize_audit(
            review,
            profile=profile_config.name,
            diff_stats=stats,
            rule_findings=rule_findings if rule_findings else None,
            diff_truncated=diff_truncated,
        )
    )


# ---------------------------------------------------------------------------
# MCP tool wrappers
# ---------------------------------------------------------------------------


def _resolve_profile(profile: str | None) -> str:
    """Resolve effective profile: explicit param > GRIPPY_PROFILE env > 'security'."""
    if profile is not None:
        return profile
    return os.environ.get("GRIPPY_PROFILE", "security")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
def scan_diff(scope: str = "staged", profile: str | None = None) -> str:
    """Run deterministic security rules against a local git diff. Fast, no LLM needed.

    Args:
        scope: What to scan. Options:
            - "staged" (default) -- staged changes (git diff --cached)
            - "commit:<ref>" -- a specific commit (e.g. "commit:HEAD", "commit:abc123")
            - "range:<base>..<head>" -- a commit range (e.g. "range:main..HEAD")
        profile: Security profile controlling gate threshold. Falls back to
            GRIPPY_PROFILE env var, then "security".
            - "security" (default) -- fail gate on ERROR or higher
            - "strict-security" -- fail gate on WARN or higher
            - "general" -- no rules, returns empty findings
    """
    return _run_scan(scope=scope, profile=_resolve_profile(profile))


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
def audit_diff(scope: str = "staged", profile: str | None = None) -> str:
    """Run a full AI-powered code review against a local git diff. Requires LLM config.

    Args:
        scope: What to review. Options:
            - "staged" (default) -- staged changes (git diff --cached)
            - "commit:<ref>" -- a specific commit (e.g. "commit:HEAD", "commit:abc123")
            - "range:<base>..<head>" -- a commit range (e.g. "range:main..HEAD")
        profile: Security profile controlling rule gate and review mode. Falls back to
            GRIPPY_PROFILE env var, then "security".
            - "security" (default) -- run deterministic rules, fail gate on ERROR or higher
            - "strict-security" -- run rules, fail gate on WARN or higher
            - "general" -- no deterministic rules, LLM-only review
    """
    return _run_audit(scope=scope, profile=_resolve_profile(profile))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the Grippy MCP server over stdio."""
    mcp.run(transport="stdio")
