# SPDX-License-Identifier: MIT
"""Step 5: Compute and display benchmark metrics."""

from __future__ import annotations

import json
import sys
from urllib.parse import urlparse

from benchmarks.martian.config import BenchConfig
from benchmarks.martian.judge import compute_metrics


def aggregate_by_repo(per_pr: list[dict]) -> dict:
    """Aggregate metrics by source repository."""
    repos: dict[str, dict] = {}
    for pr in per_pr:
        url = pr.get("golden_url", "")
        parts = urlparse(url).path.strip("/").split("/")
        repo = parts[1] if len(parts) >= 2 else pr["pr"].split("_")[0]

        if repo not in repos:
            repos[repo] = {"n_prs": 0, "tp": 0, "candidates": 0, "golden": 0}

        repos[repo]["n_prs"] += 1
        repos[repo]["tp"] += pr["metrics"]["tp"]
        repos[repo]["candidates"] += pr["n_candidates"]
        repos[repo]["golden"] += pr["n_golden"]

    for _repo, data in repos.items():
        m = compute_metrics(data["tp"], data["candidates"], data["golden"])
        data.update(m)

    return repos


def format_table(results: dict) -> list[str]:
    """Format results as a text table."""
    lines = []
    overall = results["overall"]

    lines.append("=" * 60)
    lines.append("GRIPPY BENCHMARK RESULTS")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"  Precision:  {overall['precision']:.1%}")
    lines.append(f"  Recall:     {overall['recall']:.1%}")
    lines.append(f"  F1:         {overall['f1']:.1%}")
    lines.append(f"  TP:         {overall['tp']}")
    lines.append("")

    # Per-repo breakdown
    by_repo = aggregate_by_repo(results["per_pr"])
    lines.append("-" * 60)
    lines.append(f"{'Repo':<20} {'PRs':>4} {'P':>7} {'R':>7} {'F1':>7}")
    lines.append("-" * 60)
    for repo, data in sorted(by_repo.items()):
        lines.append(
            f"{repo:<20} {data['n_prs']:>4} "
            f"{data['precision']:>6.1%} {data['recall']:>6.1%} {data['f1']:>6.1%}"
        )
    lines.append("-" * 60)

    prov = results.get("provenance", {})
    if prov:
        lines.append("")
        lines.append(f"Model:   {prov.get('model_id', '?')}")
        lines.append(f"Profile: {prov.get('profile', '?')}")
        lines.append(f"Martian: {prov.get('martian_commit', '?')[:8]}")

    return lines


def report(config: BenchConfig | None = None) -> None:
    """Print benchmark report from judge results.

    Surfaces skipped/failed PRs prominently — silent omission is how
    people accuse you of laundering the score.
    """
    config = config or BenchConfig()
    score_path = config.output_dir / "scores" / "judge_results.json"

    if not score_path.exists():
        print(f"ERROR: No judge results at {score_path}", file=sys.stderr)
        sys.exit(1)

    results = json.loads(score_path.read_text())
    for line in format_table(results):
        print(line)

    # Unified failure accounting across ALL phases
    unique_failures: dict[str, dict] = {}
    for manifest_name in ("run_manifest.json", "extract_manifest.json"):
        mp = config.output_dir / manifest_name
        if mp.exists():
            entries = json.loads(mp.read_text())
            entries = entries.get("results", entries) if isinstance(entries, dict) else entries
            for r in entries:
                if r.get("status") == "failed":
                    pr_slug = r["pr"]
                    if pr_slug not in unique_failures:
                        unique_failures[pr_slug] = {**r, "phase": manifest_name.split("_")[0]}

    # Also check judge results for missing candidates
    for pr_result in results.get("per_pr", []):
        if pr_result.get("status") == "missing_candidates":
            pr_slug = pr_result["pr"]
            if pr_slug not in unique_failures:
                unique_failures[pr_slug] = {
                    "pr": pr_slug,
                    "status": "missing_candidates",
                    "phase": "judge",
                }

    failed = list(unique_failures.values())
    total = len(results.get("per_pr", []))

    if failed:
        print()
        print("=" * 60)
        print("FAILURE ACCOUNTING (all phases)")
        print("=" * 60)
        for f in failed:
            phase = f.get("phase", "?")
            reason = f.get("reason", f.get("status", "unknown"))
            print(f"  [{phase}] {f['pr']} — {reason}")
        pct = len(failed) / total * 100 if total else 0
        print(f"\n  {len(failed)}/{total} failed ({pct:.0f}%)")
        if pct > 10:
            print("  WARNING: >10% failure rate — run NOT valid for public claims")
    else:
        print(f"\n  No failures across {total} PRs.")


if __name__ == "__main__":
    report()
