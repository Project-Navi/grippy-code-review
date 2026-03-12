# SPDX-License-Identifier: MIT
"""Tests for benchmarks/martian/fetch_diffs.py."""

import json

from benchmarks.martian.fetch_diffs import fetch_diff, parse_golden_prs

SAMPLE_GOLDEN = [
    {
        "pr_title": "Fix auth bug",
        "url": "https://github.com/keycloak/keycloak/pull/32918",
        "comments": [{"comment": "issue", "severity": "Critical"}],
    }
]


def test_parse_golden_prs(tmp_path):
    golden_dir = tmp_path / "golden_comments"
    golden_dir.mkdir()
    (golden_dir / "keycloak.json").write_text(json.dumps(SAMPLE_GOLDEN))

    prs = parse_golden_prs(golden_dir)
    assert len(prs) == 1
    assert prs[0]["owner"] == "keycloak"
    assert prs[0]["repo"] == "keycloak"
    assert prs[0]["pr_number"] == 32918
    assert prs[0]["pr_title"] == "Fix auth bug"
    assert prs[0]["golden_url"] == "https://github.com/keycloak/keycloak/pull/32918"


def test_parse_golden_extracts_owner_repo_from_url(tmp_path):
    """Handles orgs like calcom/cal.com correctly."""
    golden_dir = tmp_path / "golden_comments"
    golden_dir.mkdir()
    data = [
        {
            "pr_title": "Test",
            "url": "https://github.com/calcom/cal.com/pull/123",
            "comments": [],
        }
    ]
    (golden_dir / "cal_dot_com.json").write_text(json.dumps(data))
    prs = parse_golden_prs(golden_dir)
    assert prs[0]["owner"] == "calcom"
    assert prs[0]["repo"] == "cal.com"


def test_fetch_diff_caching(tmp_path):
    """Skips fetch if diff file already exists."""
    diff_dir = tmp_path / "diffs"
    diff_dir.mkdir()
    cached = diff_dir / "keycloak_PR32918.diff"
    cached.write_text("cached diff content")

    result = fetch_diff(
        owner="keycloak",
        repo="keycloak",
        pr_number=32918,
        output_dir=diff_dir,
        token="fake",
    )
    assert result == "cached diff content"
