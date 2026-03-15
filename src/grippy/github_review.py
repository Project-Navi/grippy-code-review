# SPDX-License-Identifier: MIT
"""GitHub PR Review API integration — inline comments, resolution, summaries.

Finding lifecycle is owned by GitHub: fetch existing comments, compare,
post only genuinely new findings, resolve threads for absent findings.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Any, NamedTuple
from urllib.parse import unquote

import navi_sanitize
import nh3
from github import Github, GithubException

from grippy.schema import Finding


class ThreadRef(NamedTuple):
    """Lightweight reference to a review thread — replaces PyGithub comment objects."""

    node_id: str
    body: str


# --- Diff parser ---


def parse_diff_lines(diff_text: str) -> dict[str, set[int]]:
    """Parse unified diff to extract addressable RIGHT-side line numbers.

    GitHub's PR Review API only allows comments on lines that appear in
    the diff hunk. This function returns a mapping of file paths to the
    set of right-side (new file) line numbers that are addressable.

    Args:
        diff_text: Complete unified diff text from GitHub API.

    Returns:
        Dict mapping file paths to sets of addressable line numbers.
    """
    if not diff_text.strip():
        return {}

    result: dict[str, set[int]] = {}
    current_file: str | None = None
    right_line = 0

    for line in diff_text.splitlines():
        # Track current file from diff headers
        file_match = re.match(r"^diff --git a/.+ b/(.+)$", line)
        if file_match:
            current_file = file_match.group(1)
            if current_file not in result:
                result[current_file] = set()
            continue

        # Parse hunk header for right-side starting line
        hunk_match = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
        if hunk_match:
            right_line = int(hunk_match.group(1))
            continue

        if current_file is None:
            continue

        # Skip diff metadata lines
        if line.startswith("---") or line.startswith("+++"):
            continue
        if line.startswith("diff --git"):
            continue
        if line.startswith("new file") or line.startswith("index "):
            continue

        # Deleted lines: only advance left-side counter (not tracked)
        if line.startswith("-"):
            continue

        # Added lines: addressable on the right side
        if line.startswith("+"):
            result[current_file].add(right_line)
            right_line += 1
            continue

        # Context lines (space prefix): addressable on right side
        if line.startswith(" "):
            result[current_file].add(right_line)
            right_line += 1
            continue

        # "\ No newline at end of file" — skip, don't increment
        if line.startswith("\\"):
            continue

        # Any other line (unexpected metadata) — skip

    return result


# --- Finding classification ---


def classify_findings(
    findings: list[Finding],
    diff_lines: dict[str, set[int]],
) -> tuple[list[Finding], list[Finding]]:
    """Split findings into inline-eligible and off-diff.

    A finding is inline-eligible if its file appears in the diff and its
    line_start is within an addressable hunk line.

    Args:
        findings: List of findings from the review.
        diff_lines: Output of parse_diff_lines().

    Returns:
        (inline_findings, off_diff_findings)
    """
    inline: list[Finding] = []
    off_diff: list[Finding] = []
    for finding in findings:
        file_lines = diff_lines.get(finding.file)
        if file_lines and finding.line_start in file_lines:
            inline.append(finding)
        else:
            off_diff.append(finding)
    return inline, off_diff


# --- Output sanitization ---

# Dangerous URL schemes in markdown link syntax — not covered by nh3
# since [text](javascript:...) is markdown, not HTML.
_DANGEROUS_SCHEME_RE = re.compile(
    r"(?:javascript|data|vbscript)\s*:",
    re.IGNORECASE,
)


def _sanitize_comment_text(text: str) -> str:
    """Sanitize LLM-generated text — Unicode normalization + HTML cleaning.

    Pipeline: navi-sanitize (invisible chars, homoglyphs, bidi) → nh3
    (HTML tag stripping) → dangerous URL scheme removal.

    Args:
        text: Raw text from an LLM-generated field.

    Returns:
        Cleaned text safe for GitHub comment posting.
    """
    text = navi_sanitize.clean(text)
    text = nh3.clean(text, tags=set())
    # Strip markdown images (tracking pixels) and external links (phishing)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    text = re.sub(r"\[([^\]]*)\]\(https?://[^)]+\)", r"\1", text)
    text = _DANGEROUS_SCHEME_RE.sub("", unquote(text))
    return text


# --- Inline comment builder ---

_SEVERITY_EMOJI = {
    "CRITICAL": "\U0001f534",
    "HIGH": "\U0001f7e0",
    "MEDIUM": "\U0001f7e1",
    "LOW": "\U0001f535",
}

# Marker format: <!-- grippy:file:category:line -->
_GRIPPY_MARKER_RE = re.compile(r"<!-- grippy:(?P<file>[^:]+):(?P<category>[^:]+):(?P<line>\d+) -->")


def _sanitize_path(path: str) -> str:
    """Sanitize file paths — Unicode normalization + traversal removal + allowlist."""
    path = navi_sanitize.clean(path, escaper=navi_sanitize.path_escaper)
    return re.sub(r"[^a-zA-Z0-9_./ -]", "", path)


def _finding_marker(finding: Finding) -> str:
    """Build an HTML comment marker for dedup — keyed on file, category, line."""
    safe_file = _sanitize_path(finding.file)
    return f"<!-- grippy:{safe_file}:{finding.category.value}:{finding.line_start} -->"


def build_review_comment(finding: Finding) -> dict[str, str | int]:
    """Build a PyGithub-compatible review comment dict for a finding.

    Args:
        finding: The finding to create a comment for.

    Returns:
        Dict with keys: path, body, line, side.
    """
    emoji = _SEVERITY_EMOJI.get(finding.severity.value, "\u26aa")
    title = _sanitize_comment_text(finding.title)
    description = _sanitize_comment_text(finding.description)
    suggestion = _sanitize_comment_text(finding.suggestion)
    evidence = _sanitize_comment_text(finding.evidence)
    grippy_note = _sanitize_comment_text(finding.grippy_note)
    body_lines = [
        f"#### {emoji} {finding.severity.value}: {title}",
        f"Confidence: {finding.confidence}%",
        "",
    ]
    if evidence.strip():
        body_lines.extend([f"```\n{evidence}\n```", ""])
    body_lines.extend(
        [
            description,
            "",
            f"**Suggestion:** {suggestion}",
            "",
            f"*\u2014 {grippy_note}*",
            "",
            _finding_marker(finding),
        ]
    )
    return {
        "path": _sanitize_path(finding.file),
        "body": "\n".join(body_lines),
        "line": finding.line_start,
        "side": "RIGHT",
    }


# --- GitHub comment fetching ---


def _parse_marker(body: str) -> tuple[str, str, int] | None:
    """Extract (file, category, line) from a grippy marker in comment body."""
    match = _GRIPPY_MARKER_RE.search(body)
    if match:
        return (match.group("file"), match.group("category"), int(match.group("line")))
    return None


def fetch_grippy_comments(
    *,
    repo: str,
    pr_number: int,
) -> dict[tuple[str, str, int], ThreadRef]:
    """Fetch existing Grippy review threads from a PR via GraphQL.

    Queries the ``reviewThreads`` connection on the pull request, extracting
    grippy markers from the first comment of each thread. Uses cursor
    pagination (100 threads per page, max 20 pages / 2000 threads).

    Args:
        repo: Repository full name (owner/repo).
        pr_number: Pull request number.

    Returns:
        Dict mapping (file, category, line) to a ThreadRef with thread
        node_id and first comment body.
    """
    import json

    owner, name = repo.split("/", 1)

    _fetch_threads_query = (
        "query FetchThreads($owner: String!, $name: String!, $pr: Int!, $cursor: String) {"
        " repository(owner: $owner, name: $name) {"
        " pullRequest(number: $pr) {"
        " reviewThreads(first: 100, after: $cursor) {"
        " pageInfo { hasNextPage endCursor }"
        " nodes { id comments(first: 1) { nodes { body } } }"
        " } } } }"
    )

    result: dict[tuple[str, str, int], ThreadRef] = {}
    cursor: str | None = None

    for _page in range(20):  # safety limit: max 20 pages
        cmd = [
            "gh",
            "api",
            "graphql",
            "-f",
            f"query={_fetch_threads_query}",
            "-f",
            f"owner={owner}",
            "-f",
            f"name={name}",
            "-F",
            f"pr={pr_number}",
        ]
        if cursor is not None:
            cmd.extend(["-f", f"cursor={cursor}"])

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if proc.returncode != 0:
                print(f"::warning::Failed to fetch review threads: {proc.stderr}")
                return result

            data = json.loads(proc.stdout)
            threads_conn = (
                data.get("data", {})
                .get("repository", {})
                .get("pullRequest", {})
                .get("reviewThreads", {})
            )
            for node in threads_conn.get("nodes", []):
                if not node:
                    continue
                thread_id = node.get("id", "")
                comments = node.get("comments", {}).get("nodes", [])
                if not comments:
                    continue
                body = comments[0].get("body", "")
                key = _parse_marker(body)
                if key is not None:
                    result[key] = ThreadRef(node_id=thread_id, body=body)

            page_info = threads_conn.get("pageInfo", {})
            if not page_info.get("hasNextPage", False):
                break
            cursor = page_info.get("endCursor")
        except Exception as exc:
            print(f"::warning::Exception fetching review threads: {exc}")
            return result

    return result


# --- Summary dashboard ---


def format_summary_comment(
    *,
    score: int,
    verdict: str,
    finding_count: int,
    new_count: int,
    resolved_count: int,
    off_diff_findings: list[Finding],
    head_sha: str,
    pr_number: int,
    diff_truncated: bool = False,
    summary_only_findings: list[Finding] | None = None,
    policy_bypassed: bool = False,
    display_capped_count: int = 0,
) -> str:
    """Format the compact summary dashboard as an issue comment.

    Args:
        score: Overall review score (0-100).
        verdict: PASS, FAIL, or PROVISIONAL.
        finding_count: Total findings this round.
        new_count: Genuinely new findings posted this round.
        resolved_count: Prior findings resolved this round.
        off_diff_findings: Findings outside diff hunks (shown inline here).
        head_sha: Commit SHA for this review.
        pr_number: PR number for marker scoping.
        diff_truncated: Whether the diff was truncated to fit context limits.

    Returns:
        Formatted markdown comment body.
    """
    status_emoji = {
        "PASS": "\u2705",  # nosec B105
        "FAIL": "\u274c",
        "PROVISIONAL": "\u26a0\ufe0f",
    }.get(verdict, "\U0001f50d")

    lines: list[str] = []
    lines.append(f"## {status_emoji} Grippy Review \u2014 {verdict}")
    lines.append("")
    lines.append(f"**Score: {score}/100** | **Findings: {finding_count}**")
    lines.append("")

    if policy_bypassed:
        lines.append(
            "> \u26a0\ufe0f **Output policy was bypassed due to an internal error."
            " Findings are unfiltered.**"
        )
        lines.append("")

    if diff_truncated:
        lines.append(
            "> \u26a0\ufe0f **Notice:** Diff was truncated to fit context limits."
            " Some files may not have been reviewed."
        )
        lines.append("")

    # Delta section
    if new_count or resolved_count:
        parts = []
        if new_count:
            parts.append(f"{new_count} new")
        if resolved_count:
            parts.append(f"\u2705 {resolved_count} resolved")
        lines.append(f"**Delta:** {' \u00b7 '.join(parts)}")
        lines.append("")

    if display_capped_count > 0:
        lines.append(f"> {display_capped_count} additional finding(s) omitted for brevity.")
        lines.append("")

    # Off-diff findings
    if off_diff_findings:
        lines.append("<details>")
        lines.append(f"<summary>Off-diff findings ({len(off_diff_findings)})</summary>")
        lines.append("")
        for f in off_diff_findings:
            sev_emoji = _SEVERITY_EMOJI.get(f.severity.value, "\u26aa")
            f_title = _sanitize_comment_text(f.title)
            f_description = _sanitize_comment_text(f.description)
            f_suggestion = _sanitize_comment_text(f.suggestion)
            lines.append(f"#### {sev_emoji} {f.severity.value}: {f_title}")
            lines.append(f"\U0001f4c1 `{_sanitize_path(f.file)}:{f.line_start}`")
            lines.append("")
            lines.append(f_description)
            lines.append("")
            lines.append(f"**Suggestion:** {f_suggestion}")
            lines.append("")
        lines.append("</details>")
        lines.append("")

    # Summary-only findings (scored but not inline-eligible)
    if summary_only_findings:
        lines.append("<details>")
        lines.append(
            f"<summary>Summary-only findings ({len(summary_only_findings)})"
            " \u2014 scored but not inline-eligible</summary>"
        )
        lines.append("")
        for f in summary_only_findings:
            sev_emoji = _SEVERITY_EMOJI.get(f.severity.value, "\u26aa")
            f_title = _sanitize_comment_text(f.title)
            f_description = _sanitize_comment_text(f.description)
            f_suggestion = _sanitize_comment_text(f.suggestion)
            lines.append(f"#### {sev_emoji} {f.severity.value}: {f_title}")
            lines.append(f"\U0001f4c1 `{_sanitize_path(f.file)}:{f.line_start}`")
            lines.append("")
            lines.append(f_description)
            lines.append("")
            lines.append(f"**Suggestion:** {f_suggestion}")
            lines.append("")
        lines.append("</details>")
        lines.append("")

    lines.append("---")
    lines.append(f"<sub>Commit: {head_sha[:7]}</sub>")
    lines.append("")
    lines.append(f"<!-- grippy-summary-{pr_number} -->")

    return "\n".join(lines)


# --- Post review ---

_REVIEW_BATCH_SIZE = 25

GRIPPY_VERDICT_MARKER = "<!-- grippy-verdict"

_GRIPPY_META_RE = re.compile(r"<!-- grippy-meta ({.*?}) -->")


def build_verdict_body(*, score: int, verdict: str, head_sha: str, base_text: str) -> str:
    """Build verdict review body with machine-readable markers.

    Appends ``<!-- grippy-verdict {sha} -->`` for identity and
    ``<!-- grippy-meta {...} -->`` for structured score/verdict extraction.
    """
    return (
        f"{base_text}\n\n"
        f"<!-- grippy-verdict {head_sha} -->\n"
        f"<!-- grippy-meta {json.dumps({'score': score, 'verdict': verdict})} -->"
    )


def parse_grippy_meta(body: str) -> dict[str, Any] | None:
    """Extract structured metadata from a grippy verdict body.

    Returns:
        Dict with "score" and "verdict" keys, or None if not found/malformed.
    """
    match = _GRIPPY_META_RE.search(body)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except (json.JSONDecodeError, ValueError):
        return None


def _dismiss_prior_verdicts(
    pr: Any,
    head_sha: str,
    *,
    force: bool = False,
    exclude_review_id: int | None = None,
) -> int:
    """Dismiss prior grippy verdicts. Returns count dismissed.

    Args:
        pr: PyGithub PullRequest object.
        head_sha: Current commit SHA.
        force: If True, dismiss same-SHA verdicts too (workflow_dispatch).
        exclude_review_id: Review ID to never dismiss (the just-posted verdict).
    """
    dismissed = 0
    for review in pr.get_reviews():
        if review.id == exclude_review_id:
            continue
        if review.state not in ("APPROVED", "CHANGES_REQUESTED"):
            continue
        if GRIPPY_VERDICT_MARKER not in (review.body or ""):
            continue
        if not force and review.commit_id == head_sha:
            continue
        try:
            review.dismiss(f"Superseded by review of {head_sha[:7]}")
            dismissed += 1
        except GithubException:
            pass
    return dismissed


def post_review(
    *,
    token: str,
    repo: str,
    pr_number: int,
    findings: list[Finding],
    head_sha: str,
    diff: str,
    score: int,
    verdict: str,
    diff_truncated: bool = False,
    summary_only_findings: list[Finding] | None = None,
    policy_bypassed: bool = False,
    display_capped_count: int = 0,
) -> None:
    """Post Grippy review as inline comments + summary dashboard.

    GitHub owns finding lifecycle:
    1. Fetch existing grippy comments from this PR
    2. Compare new findings against existing — skip matches (marker dedup)
    3. Post only genuinely new findings as inline comments
    4. Query GitHub GraphQL for thread states — resolve only outdated threads
    5. Post/update summary with delta counts

    Args:
        token: GitHub API token.
        repo: Repository full name (owner/repo).
        pr_number: Pull request number.
        findings: Current round's findings.
        head_sha: Current commit SHA.
        diff: Full PR diff text.
        score: Overall review score.
        verdict: PASS, FAIL, or PROVISIONAL.
        diff_truncated: Whether the diff was truncated to fit context limits.
    """
    gh = Github(token)
    repository = gh.get_repo(repo)
    pr = repository.get_pull(pr_number)

    # 1. Fetch existing grippy comments
    existing = fetch_grippy_comments(repo=repo, pr_number=pr_number)

    # 2. Classify: which current findings already have comments?
    new_findings: list[Finding] = []
    for finding in findings:
        key = (finding.file, finding.category.value, finding.line_start)
        if key not in existing:
            new_findings.append(finding)

    # 3. Identify stale: a thread is stale if its marker key is no longer in
    #    the current findings (the finding was suppressed or disappeared).
    #    Resolve all absent, unresolved threads — not just GitHub-outdated ones.
    current_keys = {(f.file, f.category.value, f.line_start) for f in findings}
    absent_comments = [comment for key, comment in existing.items() if key not in current_keys]
    resolved_comments: list[Any] = []
    if absent_comments:
        thread_states = fetch_thread_states([c.node_id for c in absent_comments])
        for comment in absent_comments:
            state = thread_states.get(comment.node_id, {})
            if not state.get("isResolved", False):
                resolved_comments.append(comment)

    # Detect fork PR — GITHUB_TOKEN is read-only for forks
    is_fork = (
        pr.head.repo is not None
        and pr.base.repo is not None
        and pr.head.repo.full_name != pr.base.repo.full_name
    )

    # Parse diff and classify new findings
    diff_lines = parse_diff_lines(diff)
    inline, off_diff = classify_findings(new_findings, diff_lines)

    # For fork PRs, skip inline comments — put everything in summary
    if is_fork:
        off_diff = new_findings
        inline = []

    # 4. Post inline review comments (batched, with 422 fallback)
    failed_findings: list[Finding] = []
    if inline:
        comments = [build_review_comment(f) for f in inline]
        for i in range(0, len(comments), _REVIEW_BATCH_SIZE):
            batch = comments[i : i + _REVIEW_BATCH_SIZE]
            try:
                pr.create_review(
                    event="COMMENT",
                    comments=batch,  # type: ignore[arg-type]
                )
            except GithubException as exc:
                if exc.status == 422:
                    # Move this batch's findings to off-diff
                    failed_findings.extend(inline[i : i + _REVIEW_BATCH_SIZE])
                else:
                    raise
    if failed_findings:
        off_diff.extend(failed_findings)

    # 5. Resolve threads for findings no longer present (non-fatal)
    actual_resolved = 0
    if resolved_comments:
        try:
            thread_ids = [c.node_id for c in resolved_comments]
            actual_resolved = resolve_threads(repo=repo, pr_number=pr_number, thread_ids=thread_ids)
            print(f"  Resolved {actual_resolved}/{len(thread_ids)} threads")
        except Exception as exc:
            print(f"::warning::Thread resolution failed: {exc}")

    # 6. Submit APPROVE / REQUEST_CHANGES review verdict (non-fatal)
    #    Post new verdict FIRST, then dismiss old ones (post-first ordering).
    new_review = None
    try:
        if verdict == "PASS":
            body = build_verdict_body(
                score=score,
                verdict=verdict,
                head_sha=head_sha,
                base_text=f"Grippy approves \u2014 **PASS** ({score}/100)",
            )
            new_review = pr.create_review(event="APPROVE", body=body)
        elif verdict == "FAIL":
            body = build_verdict_body(
                score=score,
                verdict=verdict,
                head_sha=head_sha,
                base_text=f"Grippy requests changes \u2014 **FAIL** ({score}/100)",
            )
            new_review = pr.create_review(event="REQUEST_CHANGES", body=body)
    except GithubException as exc:
        print(f"::warning::Verdict review ({verdict}) failed: {exc.status}")

    # 6a. Dismiss prior grippy verdicts AFTER new one lands
    if new_review is not None:
        is_manual = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
        dismissed = _dismiss_prior_verdicts(
            pr,
            head_sha,
            force=is_manual,
            exclude_review_id=new_review.id,
        )
        if dismissed:
            print(f"  Dismissed {dismissed} prior verdict(s)")

    # 7. Build summary comment
    summary = format_summary_comment(
        score=score,
        verdict=verdict,
        finding_count=len(findings),
        new_count=len(new_findings),
        resolved_count=actual_resolved,
        off_diff_findings=off_diff,
        head_sha=head_sha,
        pr_number=pr_number,
        diff_truncated=diff_truncated,
        summary_only_findings=summary_only_findings,
        policy_bypassed=policy_bypassed,
        display_capped_count=display_capped_count,
    )

    # Upsert: edit existing summary or create new
    marker = f"<!-- grippy-summary-{pr_number} -->"
    for issue_comment in pr.get_issue_comments():
        if marker in issue_comment.body:
            issue_comment.edit(summary)
            return

    pr.create_issue_comment(summary)


# --- Thread resolution ---


def fetch_thread_states(thread_ids: list[str]) -> dict[str, dict[str, bool]]:
    """Fetch isOutdated and isResolved state for review threads via GraphQL.

    Uses ``gh api graphql`` subprocess with the ``nodes`` query to batch-fetch
    thread metadata. GitHub marks threads as ``isOutdated`` when the underlying
    diff line has moved or been removed — this is more reliable than comparing
    marker keys across commits.

    Args:
        thread_ids: List of GitHub review thread node IDs (PRRT_...).

    Returns:
        Dict mapping thread_id to ``{"isOutdated": bool, "isResolved": bool}``.
        Missing/failed IDs are omitted from the result.
    """
    if not thread_ids:
        return {}

    _nodes_query = (
        "query FetchThreadStates($ids: [ID!]!) { "
        "nodes(ids: $ids) { "
        "... on PullRequestReviewThread { id isOutdated isResolved } } }"
    )
    try:
        result = subprocess.run(
            [
                "gh",
                "api",
                "graphql",
                "-f",
                f"query={_nodes_query}",
                "-F",
                f"ids={json.dumps(thread_ids)}",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            print(f"::warning::Failed to fetch thread states: {result.stderr}")
            return {}

        data = json.loads(result.stdout)
        states: dict[str, dict[str, bool]] = {}
        for node in data.get("data", {}).get("nodes", []):
            if node and "id" in node:
                states[node["id"]] = {
                    "isOutdated": node.get("isOutdated", False),
                    "isResolved": node.get("isResolved", False),
                }
        return states
    except Exception as exc:
        print(f"::warning::Exception fetching thread states: {exc}")
        return {}


def resolve_threads(
    *,
    repo: str,
    pr_number: int,
    thread_ids: list[str],
) -> int:
    """Auto-resolve GitHub review threads via a single batched GraphQL mutation.

    Uses aliased mutations to resolve all threads in one ``gh api graphql``
    subprocess call. Each thread ID gets an alias (t0, t1, ...) so individual
    failures don't block the batch.

    Args:
        repo: Repository full name (owner/repo).
        pr_number: Pull request number (for logging).
        thread_ids: List of GitHub review thread node IDs (PRRT_...).

    Returns:
        Number of threads successfully resolved.
    """
    if not thread_ids:
        return 0

    import json

    # Build aliased mutation with proper GraphQL variables ($id0, $id1, ...)
    # to prevent injection — aligns with fetch_thread_states() pattern.
    var_decls = ", ".join(f"$id{i}: ID!" for i in range(len(thread_ids)))
    aliases = [
        f"t{i}: resolveReviewThread(input: {{threadId: $id{i}}}) {{ thread {{ id isResolved }} }}"
        for i in range(len(thread_ids))
    ]
    mutation = f"mutation BatchResolve({var_decls}) {{ {' '.join(aliases)} }}"

    cmd = ["gh", "api", "graphql", "-f", f"query={mutation}"]
    for i, tid in enumerate(thread_ids):
        cmd.extend(["-f", f"id{i}={tid}"])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            print(f"::warning::Batch thread resolution failed: {result.stderr}")
            return 0

        data = json.loads(result.stdout)
        resolved = 0
        for i in range(len(thread_ids)):
            alias_result = data.get("data", {}).get(f"t{i}")
            if alias_result and alias_result.get("thread", {}).get("isResolved"):
                resolved += 1
        return resolved
    except Exception as exc:
        print(f"::warning::Exception in batch thread resolution: {exc}")
        return 0
