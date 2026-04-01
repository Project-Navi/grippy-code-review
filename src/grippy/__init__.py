# SPDX-License-Identifier: MIT
"""Grippy — the reluctant code inspector. Agno-based AI code review agent."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__: str = version("grippy-mcp")
except PackageNotFoundError:
    __version__ = "0.1.0"

from grippy.agent import create_reviewer
from grippy.codebase import CodebaseIndex, CodebaseToolkit
from grippy.embedder import create_embedder
from grippy.github_review import (
    build_review_comment,
    classify_findings,
    fetch_grippy_comments,
    format_summary_comment,
    parse_diff_lines,
    post_review,
    resolve_threads,
)
from grippy.graph_store import SQLiteGraphStore
from grippy.graph_types import (
    EdgeType,
    GraphEdge,
    GraphNode,
    MissingNodeError,
    NodeType,
    TraversalReceipt,
    TraversalResult,
)
from grippy.ports import (
    ReviewerPort,
    ReviewToolBudgetError,
    ReviewTransportError,
    SanitizedPRContext,
)
from grippy.retry import ReviewParseError, run_review
from grippy.review import (
    load_pr_event,
    truncate_diff,
)
from grippy.schema import GrippyReview

__all__ = [
    "CodebaseIndex",
    "CodebaseToolkit",
    "EdgeType",
    "GraphEdge",
    "GraphNode",
    "GrippyReview",
    "MissingNodeError",
    "NodeType",
    "ReviewParseError",
    "ReviewToolBudgetError",
    "ReviewTransportError",
    "ReviewerPort",
    "SQLiteGraphStore",
    "SanitizedPRContext",
    "TraversalReceipt",
    "TraversalResult",
    "__version__",
    "build_review_comment",
    "classify_findings",
    "create_embedder",
    "create_reviewer",
    "fetch_grippy_comments",
    "format_summary_comment",
    "load_pr_event",
    "parse_diff_lines",
    "post_review",
    "resolve_threads",
    "run_review",
    "truncate_diff",
]
