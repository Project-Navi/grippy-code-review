# SPDX-License-Identifier: MIT
"""Step 1: Fetch PR diffs from GitHub for benchmark corpus."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

from benchmarks.martian.config import BenchConfig


def parse_golden_prs(golden_dir: Path) -> list[dict]:
    """Parse all golden comment files and extract PR metadata."""
    prs: list[dict] = []
    for path in sorted(golden_dir.glob("*.json")):
        data = json.loads(path.read_text())
        for entry in data:
            url = entry["url"]
            parts = urlparse(url).path.strip("/").split("/")
            # parts: [owner, repo, "pull", number]
            prs.append(
                {
                    "owner": parts[0],
                    "repo": parts[1],
                    "pr_number": int(parts[3]),
                    "pr_title": entry["pr_title"],
                    "golden_url": url,
                    "golden_file": path.name,
                    "golden_comments": entry.get("comments", []),
                }
            )
    return prs


def fetch_diff(
    *,
    owner: str,
    repo: str,
    pr_number: int,
    output_dir: Path,
    token: str,
) -> str:
    """Fetch a PR diff from GitHub API. Returns diff text. Caches to disk."""
    cache_path = output_dir / f"{repo}_PR{pr_number}.diff"
    if cache_path.exists():
        return cache_path.read_text()

    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3.diff",
    }
    resp = httpx.get(url, headers=headers, timeout=30, follow_redirects=True)
    resp.raise_for_status()

    diff_text = resp.text
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(diff_text)
    return diff_text


def fetch_all(config: BenchConfig | None = None) -> None:
    """Fetch diffs for all golden PRs."""
    config = config or BenchConfig()
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("ERROR: GITHUB_TOKEN env var required", file=sys.stderr)
        sys.exit(1)

    prs = parse_golden_prs(config.golden_dir)
    diff_dir = config.output_dir / "diffs"
    diff_dir.mkdir(parents=True, exist_ok=True)

    for i, pr in enumerate(prs, 1):
        cache_path = diff_dir / f"{pr['repo']}_PR{pr['pr_number']}.diff"
        status = "cached" if cache_path.exists() else "fetching"
        print(f"[{i}/{len(prs)}] {pr['repo']}#{pr['pr_number']} — {status}")

        fetch_diff(
            owner=pr["owner"],
            repo=pr["repo"],
            pr_number=pr["pr_number"],
            output_dir=diff_dir,
            token=token,
        )
        if status == "fetching":
            time.sleep(1)  # respect rate limits

    print(f"Done. {len(prs)} diffs in {diff_dir}")


if __name__ == "__main__":
    fetch_all()
