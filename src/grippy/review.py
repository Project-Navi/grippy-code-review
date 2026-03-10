# SPDX-License-Identifier: MIT
"""Grippy CI review entry point — reads PR event, runs agent, posts comment.

Usage (GitHub Actions):
    python -m grippy.review

Environment variables:
    GITHUB_TOKEN            — GitHub API token for fetching diff and posting comments
    GITHUB_EVENT_PATH       — path to PR event JSON (set by GitHub Actions)
    OPENAI_API_KEY          — OpenAI API key (or unset for local endpoints)
    GRIPPY_BASE_URL         — API endpoint (default: http://localhost:1234/v1)
    GRIPPY_MODEL_ID         — model identifier (default: devstral-small-2-24b-instruct-2512)
    GRIPPY_EMBEDDING_MODEL  — embedding model (default: text-embedding-qwen3-embedding-4b)
    GRIPPY_TRANSPORT        — API transport (default: infer from OPENAI_API_KEY)
    GRIPPY_API_KEY          — API key for non-OpenAI endpoints (embedding auth fallback)
    GRIPPY_DATA_DIR         — persistent directory for graph DB + LanceDB
    GRIPPY_TIMEOUT          — seconds before review is killed (0 = no timeout)
    GITHUB_REPOSITORY       — owner/repo (set by GitHub Actions, fallback)
"""

from __future__ import annotations

import itertools
import json
import os
import sys
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

import navi_sanitize

from grippy.agent import create_reviewer, format_pr_context
from grippy.embedder import create_embedder
from grippy.github_review import post_review
from grippy.graph_context import build_context_pack, format_context_for_llm
from grippy.graph_store import SQLiteGraphStore
from grippy.graph_types import EdgeType, MissingNodeError, NodeType, _record_id
from grippy.imports import extract_imports
from grippy.retry import ReviewParseError, run_review
from grippy.rules import RuleResult, RuleSeverity, check_gate, load_profile, run_rules
from grippy.rules.enrichment import enrich_results, persist_rule_findings

# Max diff size sent to the LLM — configurable for local models with smaller context
MAX_DIFF_CHARS = int(os.environ.get("GRIPPY_MAX_DIFF_CHARS", "500000"))


_ERROR_HINTS: dict[str, str] = {
    "CONFIG ERROR": "Valid `GRIPPY_TRANSPORT` values: `openai`, `anthropic`, `google`, `groq`, `mistral`, `local`.",
    "TIMEOUT": "Increase `GRIPPY_TIMEOUT` or reduce PR diff size.",
}


def _failure_comment(repo: str, error_type: str) -> str:
    """Build a generic error comment for posting to a PR."""
    hint = _ERROR_HINTS.get(error_type, "")
    hint_line = f"\n\n{hint}" if hint else ""
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    if run_id:
        log_url = f"https://github.com/{repo}/actions/runs/{run_id}"
    else:
        log_url = f"https://github.com/{repo}/actions"
    return (
        f"## \u274c Grippy Review \u2014 {error_type}\n\n"
        f"Review failed. Check the [Actions log]({log_url}) for details."
        f"{hint_line}\n\n"
        "<!-- grippy-error -->"
    )


def load_pr_event(event_path: Path) -> dict[str, Any]:
    """Parse GitHub Actions pull_request event payload.

    Returns:
        Dict with keys: pr_number, repo, title, author, head_ref, head_sha, base_ref, description.

    Raises:
        FileNotFoundError: If event_path doesn't exist.
        KeyError: If event JSON lacks pull_request key.
    """
    data = json.loads(event_path.read_text(encoding="utf-8"))
    pr = data["pull_request"]
    return {
        "pr_number": pr["number"],
        "repo": data["repository"]["full_name"],
        "title": pr["title"],
        "author": pr["user"]["login"],
        "head_ref": pr["head"]["ref"],
        "head_sha": pr["head"].get("sha", ""),
        "base_ref": pr["base"]["ref"],
        "description": pr.get("body") or "",
        "before_sha": data.get("before", ""),
    }


def truncate_diff(diff: str, max_chars: int = MAX_DIFF_CHARS) -> str:
    """Truncate diff at file boundaries if it exceeds max_chars.

    Splits on 'diff --git' markers and includes complete files until the
    budget is exhausted. Appends a truncation warning.
    """
    if len(diff) <= max_chars:
        return diff

    # Split into per-file blocks
    parts = diff.split("diff --git ")
    # First element is empty or preamble
    preamble = parts[0]
    file_blocks = [f"diff --git {p}" for p in parts[1:]]

    kept: list[str] = []
    total = len(preamble)
    for block in file_blocks:
        if total + len(block) > max_chars and kept:
            break
        kept.append(block)
        total += len(block)

    truncated_count = len(file_blocks) - len(kept)
    result = preamble + "".join(kept)
    if truncated_count > 0:
        result += f"\n\n... {truncated_count} file(s) truncated (diff exceeded {max_chars} chars) (truncated)"
    return result


def fetch_pr_diff(token: str, repo: str, pr_number: int) -> str:
    """Fetch complete PR diff via GitHub API raw diff endpoint.

    Uses Accept: application/vnd.github.v3.diff to get the full unified
    diff in a single request — no pagination issues.
    """
    import requests

    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3.diff",
    }
    response = requests.get(url, headers=headers, timeout=60)
    response.raise_for_status()
    return response.text


def fetch_changed_since(token: str, repo: str, before: str, after: str) -> list[str]:
    """Fetch file paths changed between two commits via GitHub compare API.

    Used to annotate re-reviews with which files changed since the last review.
    Non-fatal — returns empty list on any error.

    Args:
        token: GitHub API token.
        repo: Repository full name (owner/repo).
        before: Previous HEAD SHA (from synchronize event ``before`` field).
        after: Current HEAD SHA.

    Returns:
        List of file paths that changed between the two commits.
    """
    import requests

    url = f"https://api.github.com/repos/{repo}/compare/{before}...{after}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        return [f["filename"] for f in data.get("files", [])]
    except Exception as exc:
        print(f"::warning::Failed to fetch changed files since last review: {exc}")
        return []


def post_comment(token: str, repo: str, pr_number: int, body: str) -> None:
    """Post an error/status comment on a PR (used for error paths only)."""
    from github import Github

    gh = Github(token)
    repository = gh.get_repo(repo)
    pr = repository.get_pull(pr_number)
    pr.create_issue_comment(body)


def _with_timeout(fn: Callable[[], Any], *, timeout_seconds: int) -> Any:
    """Run *fn* with a SIGALRM timeout (Linux only).  0 = no timeout."""
    if timeout_seconds <= 0:
        return fn()

    import signal

    def _handler(signum: int, frame: Any) -> None:
        msg = f"Review timed out after {timeout_seconds}s"
        raise TimeoutError(msg)

    old_handler = signal.signal(signal.SIGALRM, _handler)
    signal.alarm(timeout_seconds)
    try:
        return fn()
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


_SEVERITY_MAP: dict[RuleSeverity, str] = {
    RuleSeverity.CRITICAL: "CRITICAL",
    RuleSeverity.ERROR: "ERROR",
    RuleSeverity.WARN: "WARN",
    RuleSeverity.INFO: "INFO",
}


def _escape_rule_field(text: str) -> str:
    """Sanitize and escape rule finding fields to prevent prompt injection.

    Pipeline: navi-sanitize (invisible chars, bidi, homoglyphs, NFKC) →
    XML delimiter escaping. Crafted filenames or evidence strings could
    contain Unicode obfuscation or XML payloads — both are neutralized.
    """
    text = navi_sanitize.clean(text)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _check_already_reviewed(
    pr: Any,
    head_sha: str,
    *,
    pr_number: int,
) -> dict[str, Any] | None:
    """Check if grippy already fully reviewed this commit.

    A review is complete when BOTH exist:
    1. A verdict (APPROVED/CHANGES_REQUESTED) with ``<!-- grippy-verdict -->`` marker
    2. A summary comment with ``<!-- grippy-summary-N -->`` marker

    Returns:
        Parsed grippy-meta dict (score, verdict) if complete review exists, else None.
    """
    from grippy.github_review import GRIPPY_VERDICT_MARKER, parse_grippy_meta

    meta = None
    for review in pr.get_reviews():
        if review.state not in ("APPROVED", "CHANGES_REQUESTED"):
            continue
        if GRIPPY_VERDICT_MARKER not in (review.body or ""):
            continue
        if review.commit_id != head_sha:
            continue
        meta = parse_grippy_meta(review.body or "")
        if meta is not None:
            break

    if meta is None:
        return None

    summary_marker = f"<!-- grippy-summary-{pr_number} -->"
    for comment in pr.get_issue_comments():
        if summary_marker in (comment.body or ""):
            return meta

    return None


def _format_rule_findings(results: list[RuleResult]) -> str:
    """Format rule findings as text for the LLM context."""
    lines: list[str] = []
    for r in results:
        sev = _SEVERITY_MAP.get(r.severity, "INFO")
        file_safe = _escape_rule_field(r.file)
        msg_safe = _escape_rule_field(r.message)
        parts = [f"[{sev}] {r.rule_id} @ {file_safe}"]
        if r.line is not None:
            parts[0] += f":{r.line}"
        parts[0] += f": {msg_safe}"
        if r.evidence:
            parts.append(f"  evidence: {_escape_rule_field(r.evidence)}")
        lines.append(" | ".join(parts) if r.evidence else parts[0])
    return "\n".join(lines)


def main(*, profile: str | None = None) -> None:
    """CI entry point — reads env, runs review, posts comment."""
    # Load .dev.vars if present (local dev only — never in CI)
    if not os.environ.get("CI"):
        dev_vars_path = Path(__file__).resolve().parent.parent.parent / ".dev.vars"
        if dev_vars_path.is_file():
            for line in dev_vars_path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())

    # Required env
    token = os.environ.get("GITHUB_TOKEN", "")
    event_path_str = os.environ.get("GITHUB_EVENT_PATH", "")
    base_url = os.environ.get("GRIPPY_BASE_URL", "http://localhost:1234/v1")
    model_id = os.environ.get("GRIPPY_MODEL_ID", "devstral-small-2-24b-instruct-2512")
    api_key = os.environ.get("GRIPPY_API_KEY", "lm-studio")
    transport = os.environ.get("GRIPPY_TRANSPORT") or None
    mode = os.environ.get("GRIPPY_MODE", "pr_review")
    timeout_seconds = int(os.environ.get("GRIPPY_TIMEOUT", "300"))

    if not token:
        print("::error::GITHUB_TOKEN not set")
        sys.exit(1)
    if not event_path_str:
        print("::error::GITHUB_EVENT_PATH not set")
        sys.exit(1)

    event_path = Path(event_path_str)
    if not event_path.is_file():
        print(f"::error::Event file not found: {event_path}")
        sys.exit(1)

    # 1. Parse event
    print("=== Grippy Review ===")
    pr_event = load_pr_event(event_path)
    safe_title = pr_event["title"].replace("\n", " ").replace("\r", " ")
    print(
        f"PR #{pr_event['pr_number']}: {safe_title} "
        f"({pr_event['head_ref']} → {pr_event['base_ref']})"
    )

    # 2. Validate transport early (before expensive diff fetch)
    from grippy.agent import _resolve_transport

    try:
        _resolve_transport(transport, model_id)
    except ValueError as exc:
        print(f"::error::Invalid configuration: {exc}")
        post_comment(
            token,
            pr_event["repo"],
            pr_event["pr_number"],
            _failure_comment(pr_event["repo"], "CONFIG ERROR"),
        )
        sys.exit(1)

    data_dir_str = os.environ.get("GRIPPY_DATA_DIR", "./grippy-data")
    embedding_model = os.environ.get("GRIPPY_EMBEDDING_MODEL", "text-embedding-qwen3-embedding-4b")
    data_dir = Path(data_dir_str)
    data_dir.mkdir(parents=True, exist_ok=True)

    # 2a. Build codebase index for tool-augmented review (non-fatal)
    codebase_tools: list[Any] = []
    workspace = os.environ.get("GITHUB_WORKSPACE", "")
    if workspace:
        try:
            from agno.vectordb.lancedb import LanceDb
            from agno.vectordb.search import SearchType

            from grippy.codebase import CodebaseIndex, CodebaseToolkit

            cb_embedder = create_embedder(
                transport=transport or "local",
                model=embedding_model,
                base_url=base_url,
                api_key=api_key,
            )
            lance_dir = data_dir / "lance"
            lance_dir.mkdir(parents=True, exist_ok=True)

            # NOTE: embedder is passed to both vector_db (Agno internals)
            # and index (batch embedding + query). Must be same instance.
            vector_db = LanceDb(
                uri=str(lance_dir),
                table_name="codebase_chunks",
                search_type=SearchType.hybrid,
                use_tantivy=False,
                embedder=cb_embedder,
            )
            cb_index = CodebaseIndex(
                repo_root=Path(workspace),
                vector_db=vector_db,
                embedder=cb_embedder,
                data_dir=data_dir,
            )
            force_reindex = os.environ.get("GRIPPY_FORCE_REINDEX", "").lower() in (
                "1",
                "true",
                "yes",
            )
            chunk_count = cb_index.build(force=force_reindex)
            if chunk_count > 0:
                print(f"  Indexed {chunk_count} chunks")
            else:
                print("Codebase index up-to-date (cached)")
            codebase_tools = [CodebaseToolkit(index=cb_index, repo_root=Path(workspace))]
        except Exception as exc:
            print(f"::warning::Codebase indexing failed (non-fatal): {exc}")

    # 2b. Build dependency graph (non-fatal)
    graph_store: SQLiteGraphStore | None = None
    try:
        graph_store = SQLiteGraphStore(db_path=data_dir / "navi-graph.db")
        if workspace:
            ws = Path(workspace)
            py_files = list(itertools.islice(ws.rglob("*.py"), 5000))
            for py_f in py_files:
                try:
                    rel = str(py_f.relative_to(ws))
                except ValueError:
                    continue
                fid = _record_id(NodeType.FILE, rel)
                graph_store.upsert_node(fid, NodeType.FILE, {"path": rel, "lang": "python"})
            for py_f in py_files:
                try:
                    rel = str(py_f.relative_to(ws))
                except ValueError:
                    continue
                imports = extract_imports(py_f, ws)
                src_id = _record_id(NodeType.FILE, rel)
                for imp_path in imports:
                    tgt_id = _record_id(NodeType.FILE, imp_path)
                    try:
                        graph_store.upsert_edge(src_id, tgt_id, EdgeType.IMPORTS)
                    except MissingNodeError:
                        pass  # target file not in graph — skip
            print(f"  Graph: {len(py_files)} files indexed")
    except Exception as exc:
        print(f"::warning::Graph store init failed (non-fatal): {exc}")
        graph_store = None

    # 3. Fetch diff (graceful 403 handling for fork PRs)
    print("Fetching PR diff...")
    try:
        diff = fetch_pr_diff(token, pr_event["repo"], pr_event["pr_number"])
    except Exception as exc:
        print(f"::error::Failed to fetch PR diff: {exc}")
        if "403" in str(exc):
            print(
                "::error::The token may lack access to this fork's diff. "
                "Ensure the GITHUB_TOKEN has read access to the fork, "
                "or use a PAT with `contents: read` scope."
            )
        try:
            post_comment(
                token,
                pr_event["repo"],
                pr_event["pr_number"],
                _failure_comment(pr_event["repo"], "DIFF ERROR"),
            )
        except Exception:
            pass  # nosec B110 — best-effort, don't mask the original error
        sys.exit(1)
    file_count = diff.count("diff --git")
    print(f"  {file_count} files, {len(diff)} chars")

    # 3a. Apply .grippyignore filtering
    from grippy.ignore import filter_diff, load_grippyignore
    from grippy.local_diff import get_repo_root

    spec = load_grippyignore(get_repo_root() or Path.cwd())
    diff, excluded_count = filter_diff(diff, spec)
    if excluded_count:
        print(f"  {excluded_count} file(s) excluded by .grippyignore")

    # Extract touched files from FULL diff (before truncation)
    touched_files_from_diff = [
        line.split(" b/", 1)[1]
        for line in diff.splitlines()
        if line.startswith("diff --git") and " b/" in line
    ]

    # 3b. Run security rule engine on FULL diff (before truncation)
    try:
        profile_config = load_profile(cli_profile=profile)
    except ValueError as exc:
        print(f"::error::Invalid profile: {exc}")
        post_comment(
            token,
            pr_event["repo"],
            pr_event["pr_number"],
            _failure_comment(pr_event["repo"], "CONFIG ERROR"),
        )
        sys.exit(1)

    rule_findings: list[RuleResult] = []
    rule_gate_failed = False
    expected_rule_counts: dict[str, int] | None = None
    expected_rule_files: dict[str, frozenset[str]] | None = None
    rule_findings_text = ""

    if profile_config.name != "general":
        print(f"Running rule engine (profile={profile_config.name})...")
        rule_findings = run_rules(diff, profile_config)
        rule_findings = enrich_results(rule_findings, graph_store)
        rule_gate_failed = check_gate(rule_findings, profile_config)
        print(f"  {len(rule_findings)} findings, gate={'FAILED' if rule_gate_failed else 'passed'}")
        if rule_findings:
            rule_findings_text = _format_rule_findings(rule_findings)
            expected_rule_counts = dict(Counter(r.rule_id for r in rule_findings))
            expected_rule_files = {
                rule_id: frozenset(r.file for r in rule_findings if r.rule_id == rule_id)
                for rule_id in expected_rule_counts
            }
        mode = "security_audit"

    # H2: cap diff size to avoid overflowing LLM context (after rule engine)
    original_len = len(diff)
    diff = truncate_diff(diff)
    diff_truncated = len(diff) < original_len
    if diff_truncated:
        print(f"  Diff truncated to {MAX_DIFF_CHARS} chars ({file_count} files in original)")

    # 3c. Create agent (after rule engine, so mode/rule_findings are resolved)
    # Build tool hooks for codebase tool sanitization
    tool_hooks_list: list[Any] | None = None
    if codebase_tools:
        from grippy.codebase import sanitize_tool_hook

        tool_hooks_list = [sanitize_tool_hook]

    try:
        agent = create_reviewer(
            model_id=model_id,
            base_url=base_url,
            api_key=api_key,
            transport=transport,
            mode=mode,
            db_path=data_dir / "grippy-session.db",
            session_id=f"pr-{pr_event['pr_number']}",
            tools=codebase_tools or None,
            tool_call_limit=10 if codebase_tools else None,
            tool_hooks=tool_hooks_list,
            include_rule_findings=bool(rule_findings),
        )
    except ValueError as exc:
        print(f"::error::Invalid configuration: {exc}")
        post_comment(
            token,
            pr_event["repo"],
            pr_event["pr_number"],
            _failure_comment(pr_event["repo"], "CONFIG ERROR"),
        )
        sys.exit(1)

    # 3d. Query graph for contextual hints (non-fatal)
    graph_context_text = ""
    if graph_store:
        try:
            pack = build_context_pack(
                graph_store,
                touched_files=touched_files_from_diff,
                author_login=pr_event.get("author"),
            )
            graph_context_text = format_context_for_llm(pack)
            if graph_context_text:
                print(f"  Graph context: {len(graph_context_text)} chars")
        except Exception as exc:
            print(f"::warning::Graph context query failed (non-fatal): {exc}")

    # 3e. Detect re-review: annotate files changed since last review (non-fatal)
    changed_since_text = ""
    before_sha = pr_event.get("before_sha", "")
    head_sha = pr_event.get("head_sha", "")
    if before_sha and head_sha and before_sha != head_sha:
        changed_files = fetch_changed_since(token, pr_event["repo"], before_sha, head_sha)
        if changed_files:
            changed_since_text = (
                f"This is a RE-REVIEW. The following {len(changed_files)} file(s) changed "
                f"since the last review (commit {before_sha[:7]}):\n"
                + "\n".join(f"  - {f}" for f in changed_files)
                + "\n\nPrioritize reviewing changes in these files. "
                "The rest of the diff was already reviewed in a prior run."
            )
            print(f"  Re-review: {len(changed_files)} files changed since {before_sha[:7]}")

    # 4. Format context
    description = pr_event["description"]
    if graph_context_text:
        description = f"{description}\n\n<graph-context>\n{graph_context_text}\n</graph-context>"

    user_message = format_pr_context(
        title=pr_event["title"],
        author=pr_event["author"],
        branch=f"{pr_event['head_ref']} → {pr_event['base_ref']}",
        description=description,
        diff=diff,
        rule_findings=rule_findings_text,
        changed_since_last_review=changed_since_text,
    )

    # 5. Run review with retry + validation (replaces agent.run + parse_review_response)
    print("Running review...")
    try:
        review = _with_timeout(
            lambda: run_review(
                agent,
                user_message,
                expected_rule_counts=expected_rule_counts,
                expected_rule_files=expected_rule_files,
            ),
            timeout_seconds=timeout_seconds,
        )
    except ReviewParseError as exc:
        print(f"::error::Grippy review failed after {exc.attempts} attempts: {exc}")
        try:
            post_comment(
                token,
                pr_event["repo"],
                pr_event["pr_number"],
                _failure_comment(pr_event["repo"], "PARSE ERROR"),
            )
        except Exception:
            pass  # nosec B110 — best-effort error posting
        sys.exit(1)
    except TimeoutError as exc:
        print(f"::error::Grippy review timed out: {exc}")
        try:
            post_comment(
                token,
                pr_event["repo"],
                pr_event["pr_number"],
                _failure_comment(pr_event["repo"], "TIMEOUT"),
            )
        except Exception:
            pass  # nosec B110 — best-effort error posting
        sys.exit(1)
    except Exception as exc:
        print(f"::error::Grippy agent failed: {exc}")
        try:
            post_comment(
                token,
                pr_event["repo"],
                pr_event["pr_number"],
                _failure_comment(pr_event["repo"], "ERROR"),
            )
        except Exception:
            pass  # nosec B110 — best-effort error posting
        sys.exit(1)

    # Override self-reported model — LLMs hallucinate their own model name
    review.model = model_id

    print(f"  Score: {review.score.overall}/100 — {review.verdict.status.value}")
    print(f"  Findings: {len(review.findings)}")

    # 6. Post review — GitHub owns finding lifecycle
    head_sha = pr_event.get("head_sha", "")
    print("Posting review...")
    try:
        post_review(
            token=token,
            repo=pr_event["repo"],
            pr_number=pr_event["pr_number"],
            findings=review.findings,
            head_sha=head_sha,
            diff=diff,
            score=review.score.overall,
            verdict=review.verdict.status.value,
            diff_truncated=diff_truncated,
        )
        print("  Done.")
    except Exception as exc:
        print(f"::warning::Failed to post review: {exc}")
        try:
            post_comment(
                token,
                pr_event["repo"],
                pr_event["pr_number"],
                _failure_comment(pr_event["repo"], "POST ERROR"),
            )
        except Exception:
            pass  # nosec B110 — best-effort error posting

    # 6b. Persist review to graph (fire-and-forget)
    if graph_store:
        try:
            review_id = _record_id(
                NodeType.REVIEW,
                pr_event["repo"],
                str(pr_event["pr_number"]),
                head_sha,
            )
            author_id = _record_id(NodeType.AUTHOR, pr_event["author"])
            graph_store.upsert_node(
                review_id,
                NodeType.REVIEW,
                {
                    "repo": pr_event["repo"],
                    "pr": pr_event["pr_number"],
                    "status": review.verdict.status.value,
                    "score": review.score.overall,
                    "findings_count": len(review.findings),
                },
            )
            graph_store.upsert_node(
                author_id,
                NodeType.AUTHOR,
                {"login": pr_event["author"]},
            )
            graph_store.upsert_edge(author_id, review_id, EdgeType.AUTHORED)

            for finding in review.findings:
                finding_id = _record_id(
                    NodeType.FINDING,
                    review_id,
                    finding.id,
                )
                graph_store.upsert_node(
                    finding_id,
                    NodeType.FINDING,
                    {
                        "finding_id": finding.id,
                        "severity": (
                            finding.severity.value
                            if hasattr(finding.severity, "value")
                            else str(finding.severity)
                        ),
                        "category": navi_sanitize.clean(str(finding.category)),
                        "title": navi_sanitize.clean(finding.title),
                        "confidence": finding.confidence,
                    },
                )
                if finding.file:
                    file_id = _record_id(NodeType.FILE, finding.file)
                    try:
                        graph_store.upsert_edge(finding_id, file_id, EdgeType.FOUND_IN)
                    except MissingNodeError:
                        pass  # file not in graph
                graph_store.upsert_edge(review_id, finding_id, EdgeType.PRODUCED)

            # Add history observations to touched files (from pre-truncation diff)
            for path in touched_files_from_diff:
                fid = _record_id(NodeType.FILE, path)
                try:
                    graph_store.add_observations(
                        fid,
                        [
                            f"PR #{pr_event['pr_number']}: "
                            f"score {review.score.overall}, "
                            f"{len(review.findings)} findings "
                            f"({review.verdict.status.value})"
                        ],
                        source="pipeline",
                        kind="history",
                    )
                except Exception:  # nosec B110
                    pass  # file not in graph

            # Persist rule findings for recurrence tracking
            if rule_findings:
                persist_rule_findings(graph_store, rule_findings, review_id)
        except Exception as exc:
            print(f"::warning::Graph persistence failed (non-fatal): {exc}")

    # 7. Set outputs for GitHub Actions
    github_output = os.environ.get("GITHUB_OUTPUT", "")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"score={review.score.overall}\n")
            f.write(f"verdict={review.verdict.status.value}\n")
            f.write(f"findings-count={len(review.findings)}\n")
            f.write(f"merge-blocking={str(review.verdict.merge_blocking).lower()}\n")
            f.write(f"rule-findings-count={len(rule_findings)}\n")
            f.write(f"rule-gate-failed={str(rule_gate_failed).lower()}\n")
            f.write(f"profile={profile_config.name}\n")

    # Exit non-zero if merge-blocking or rule gate failed
    if rule_gate_failed:
        print(f"::warning::Rule gate FAILED (profile={profile_config.name})")
        sys.exit(1)
    if review.verdict.merge_blocking:
        print(f"::warning::Review verdict: {review.verdict.status.value} (merge-blocking)")
        sys.exit(1)


if __name__ == "__main__":
    main()
