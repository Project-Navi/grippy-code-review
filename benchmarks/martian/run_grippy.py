# SPDX-License-Identifier: MIT
"""Step 2: Run Grippy reviews against fetched diffs."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime

from benchmarks.martian.config import BenchConfig
from benchmarks.martian.fetch_diffs import parse_golden_prs


def _format_rules_for_agent(rule_findings: list) -> str:
    """Format rule findings as text for the agent's context.

    Own implementation — avoids coupling to grippy.review internals.
    This is simple string formatting; the agent just needs to see the
    rule results to avoid duplicating them.
    """
    lines = []
    for r in rule_findings:
        loc = f"{r.file}:{r.line}" if r.line else r.file
        lines.append(f"[{r.severity.name}] {r.rule_id}: {r.message} ({loc})")
    return "\n".join(lines)


def is_inline_finding(finding: dict) -> bool:
    """True if finding has a specific file and line anchor."""
    return bool(finding.get("file")) and bool(finding.get("line_start"))


def format_finding_as_comment(finding: dict) -> str:
    """Format a finding as a reviewer comment for benchmark extraction.

    Mirrors the structure of Grippy's production inline comments
    (see github_review.py:build_review_comment) but strips metadata
    that would bias the Martian judge:
    - No severity emoji/tags (judge should match on issue, not label)
    - No confidence score (internal metric)
    - No suggestion (judge matches problems, not fixes)
    - No grippy_note (personality, not substance)
    - No dedup marker (internal bookkeeping)

    What remains: title + description, which is the issue substance
    that a human reviewer would write.
    """
    title = finding.get("title", "").strip()
    desc = finding.get("description", "").strip()
    # Markdown heading mirrors production format structure
    return f"#### {title}\n\n{desc}"


def review_single_pr(
    *,
    diff_text: str,
    pr_title: str,
    config: BenchConfig,
) -> dict:
    """Run Grippy review on a single diff. Returns serialized review dict.

    Runs deterministic rules with the frozen profile, then LLM review.
    Profile is passed explicitly — never relies on ambient env for this.
    """
    from grippy.agent import create_reviewer, format_pr_context
    from grippy.retry import run_review
    from grippy.rules import load_profile, run_rules

    # Deterministic rules — profile from frozen config, explicit
    profile_cfg = load_profile(cli_profile=config.profile)
    rule_findings = run_rules(diff_text, profile_cfg)

    # Format rule findings for the agent (only if profile enables them)
    # Own formatter — avoids reaching into grippy.review internals
    rule_text = ""
    if rule_findings and config.profile != "general":
        rule_text = _format_rules_for_agent(rule_findings)

    agent = create_reviewer(
        model_id=config.model_id,
        base_url=config.base_url,
        api_key=config.api_key,
        transport=config.transport,
        mode=config.mode,
        include_rule_findings=bool(rule_text),
    )
    message = format_pr_context(
        title=pr_title,
        author="benchmark",
        branch="feature → main",
        diff=diff_text,
        rule_findings=rule_text,
    )
    review = run_review(agent, message)
    return review.model_dump()


def run_all(config: BenchConfig | None = None, resume: bool = False) -> None:
    """Run Grippy on all fetched diffs."""
    config = config or BenchConfig.from_env()
    prs = parse_golden_prs(config.golden_dir)

    diff_dir = config.output_dir / "diffs"
    review_dir = config.output_dir / "reviews"
    comment_dir = config.output_dir / "comments"
    review_dir.mkdir(parents=True, exist_ok=True)
    comment_dir.mkdir(parents=True, exist_ok=True)

    manifest = []
    for i, pr in enumerate(prs, 1):
        slug = f"{pr['repo']}_PR{pr['pr_number']}"
        review_path = review_dir / f"{slug}.json"
        comment_path = comment_dir / f"{slug}.json"

        if resume and review_path.exists() and comment_path.exists():
            print(f"[{i}/{len(prs)}] {slug} — skipped (resume, both review + comments exist)")
            continue
        if resume and review_path.exists() and not comment_path.exists():
            print(f"[{i}/{len(prs)}] {slug} — regenerating comments from cached review")
            try:
                review_data = json.loads(review_path.read_text()).get("review", {})
                findings = review_data.get("findings", [])
                inline_comments = []
                general_comments = []
                for f in findings:
                    body = format_finding_as_comment(f)
                    if is_inline_finding(f):
                        inline_comments.append(
                            {"path": f["file"], "line": f["line_start"], "body": body}
                        )
                    else:
                        general_comments.append(body)
                comment_path.write_text(
                    json.dumps(
                        {
                            "inline": inline_comments,
                            "general": general_comments,
                        },
                        indent=2,
                    )
                )
                manifest.append({"pr": slug, "status": "ok", "findings": len(findings)})
            except Exception as e:
                print(f"[{i}/{len(prs)}] {slug} — ERROR regenerating: {e}", file=sys.stderr)
                manifest.append({"pr": slug, "status": "failed", "reason": str(e)})
            continue

        diff_path = diff_dir / f"{slug}.diff"
        if not diff_path.exists():
            print(f"[{i}/{len(prs)}] {slug} — ERROR: diff not found", file=sys.stderr)
            manifest.append({"pr": slug, "status": "failed", "reason": "diff_not_found"})
            continue

        diff_text = diff_path.read_text()
        print(f"[{i}/{len(prs)}] {slug} — reviewing ({len(diff_text)} chars)")

        ts = datetime.now(UTC).isoformat()
        try:
            review_data = review_single_pr(
                diff_text=diff_text,
                pr_title=pr["pr_title"],
                config=config,
            )

            # Save full review
            output = {"provenance": config.stamp(), "timestamp": ts, "review": review_data}
            review_path.write_text(json.dumps(output, indent=2))

            # Format findings as comments for extraction step
            findings = review_data.get("findings", [])
            inline_comments = []
            general_comments = []
            for f in findings:
                body = format_finding_as_comment(f)
                if is_inline_finding(f):
                    inline_comments.append(
                        {
                            "path": f["file"],
                            "line": f["line_start"],
                            "body": body,
                        }
                    )
                else:
                    general_comments.append(body)

            comment_path.write_text(
                json.dumps(
                    {
                        "inline": inline_comments,
                        "general": general_comments,
                    },
                    indent=2,
                )
            )

            manifest.append({"pr": slug, "status": "ok", "findings": len(findings)})
        except Exception as e:
            print(f"[{i}/{len(prs)}] {slug} — ERROR: {e}", file=sys.stderr)
            manifest.append({"pr": slug, "status": "failed", "reason": str(e)})

    # Write run manifest
    manifest_path = config.output_dir / "run_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "provenance": config.stamp(),
                "timestamp": datetime.now(UTC).isoformat(),
                "results": manifest,
            },
            indent=2,
        )
    )
    ok = sum(1 for m in manifest if m["status"] == "ok")
    fail = sum(1 for m in manifest if m["status"] == "failed")
    print(f"Done. {ok} reviewed, {fail} failed, {len(prs) - ok - fail} skipped.")


if __name__ == "__main__":
    resume = "--resume" in sys.argv
    run_all(resume=resume)
