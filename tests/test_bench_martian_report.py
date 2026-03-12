# SPDX-License-Identifier: MIT
"""Tests for benchmarks/martian/report.py."""

import json

from benchmarks.martian.report import aggregate_by_repo, format_table, report

SAMPLE_RESULTS = {
    "overall": {"precision": 0.6, "recall": 0.5, "f1": 0.545, "tp": 5},
    "per_pr": [
        {
            "pr": "keycloak_PR32918",
            "golden_url": "https://github.com/keycloak/keycloak/pull/32918",
            "n_candidates": 3,
            "n_golden": 2,
            "metrics": {"precision": 0.67, "recall": 1.0, "f1": 0.8, "tp": 2},
        },
        {
            "pr": "sentry_PR100",
            "golden_url": "https://github.com/getsentry/sentry/pull/100",
            "n_candidates": 5,
            "n_golden": 4,
            "metrics": {"precision": 0.6, "recall": 0.75, "f1": 0.67, "tp": 3},
        },
    ],
}


def test_aggregate_by_repo():
    by_repo = aggregate_by_repo(SAMPLE_RESULTS["per_pr"])
    assert "keycloak" in by_repo
    assert "sentry" in by_repo
    assert by_repo["keycloak"]["n_prs"] == 1


def test_format_table_produces_lines():
    lines = format_table(SAMPLE_RESULTS)
    text = "\n".join(lines)
    assert "Precision" in text
    assert "Recall" in text
    assert "F1" in text


def test_report_unified_failure_accounting(tmp_path, capsys):
    """Failures from run + extract + judge phases all surface in one report."""
    output_dir = tmp_path / "output"
    scores_dir = output_dir / "scores"
    scores_dir.mkdir(parents=True)

    # Judge results: one normal, one missing_candidates
    judge_results = {
        "overall": {"precision": 0.5, "recall": 0.5, "f1": 0.5, "tp": 1},
        "per_pr": [
            {
                "pr": "keycloak_PR100",
                "golden_url": "https://github.com/keycloak/keycloak/pull/100",
                "n_candidates": 2,
                "n_golden": 2,
                "metrics": {"precision": 0.5, "recall": 0.5, "f1": 0.5, "tp": 1},
            },
            {
                "pr": "sentry_PR200",
                "golden_url": "https://github.com/getsentry/sentry/pull/200",
                "n_candidates": 0,
                "n_golden": 3,
                "status": "missing_candidates",
                "metrics": {"precision": 0.0, "recall": 0.0, "f1": 0.0, "tp": 0},
            },
        ],
    }
    (scores_dir / "judge_results.json").write_text(json.dumps(judge_results))

    # Run manifest: one failure
    run_manifest = {
        "results": [
            {"pr": "grafana_PR300", "status": "failed", "reason": "timeout"},
            {"pr": "keycloak_PR100", "status": "ok", "findings": 3},
        ]
    }
    (output_dir / "run_manifest.json").write_text(json.dumps(run_manifest))

    # Extract manifest: another failure
    extract_manifest = [
        {"pr": "discourse_PR400", "status": "failed", "reason": "json_parse_error"},
    ]
    (output_dir / "extract_manifest.json").write_text(json.dumps(extract_manifest))

    from benchmarks.martian.config import BenchConfig

    cfg = BenchConfig(output_dir=output_dir)
    report(config=cfg)

    captured = capsys.readouterr().out
    # All three failure phases should appear
    assert "[run] grafana_PR300" in captured
    assert "[extract] discourse_PR400" in captured
    assert "[judge] sentry_PR200" in captured
    assert "FAILURE ACCOUNTING" in captured


def test_report_unique_failure_dedup(tmp_path, capsys):
    """Same PR failing in run AND extract counts as ONE unique failure."""
    output_dir = tmp_path / "output"
    scores_dir = output_dir / "scores"
    scores_dir.mkdir(parents=True)

    judge_results = {
        "overall": {"precision": 0.0, "recall": 0.0, "f1": 0.0, "tp": 0},
        "per_pr": [
            {
                "pr": "keycloak_PR100",
                "golden_url": "https://github.com/keycloak/keycloak/pull/100",
                "n_candidates": 0,
                "n_golden": 2,
                "status": "missing_candidates",
                "metrics": {"precision": 0.0, "recall": 0.0, "f1": 0.0, "tp": 0},
            },
        ],
    }
    (scores_dir / "judge_results.json").write_text(json.dumps(judge_results))

    # Same PR fails in both run and extract
    run_manifest = {"results": [{"pr": "keycloak_PR100", "status": "failed", "reason": "timeout"}]}
    (output_dir / "run_manifest.json").write_text(json.dumps(run_manifest))

    extract_manifest = [{"pr": "keycloak_PR100", "status": "failed", "reason": "no_comments"}]
    (output_dir / "extract_manifest.json").write_text(json.dumps(extract_manifest))

    from benchmarks.martian.config import BenchConfig

    cfg = BenchConfig(output_dir=output_dir)
    report(config=cfg)

    captured = capsys.readouterr().out
    # Should count as 1 failure, not 3
    assert "1/1 failed" in captured
    # First occurrence wins (run phase)
    assert "[run] keycloak_PR100" in captured


def test_report_high_failure_rate_warning(tmp_path, capsys):
    """>10% failure rate triggers the public-claims warning."""
    output_dir = tmp_path / "output"
    scores_dir = output_dir / "scores"
    scores_dir.mkdir(parents=True)

    # 2 PRs, 1 missing = 50% failure rate
    judge_results = {
        "overall": {"precision": 0.5, "recall": 0.5, "f1": 0.5, "tp": 1},
        "per_pr": [
            {
                "pr": "keycloak_PR100",
                "golden_url": "https://github.com/keycloak/keycloak/pull/100",
                "n_candidates": 2,
                "n_golden": 2,
                "metrics": {"precision": 0.5, "recall": 0.5, "f1": 0.5, "tp": 1},
            },
            {
                "pr": "sentry_PR200",
                "golden_url": "https://github.com/getsentry/sentry/pull/200",
                "n_candidates": 0,
                "n_golden": 3,
                "status": "missing_candidates",
                "metrics": {"precision": 0.0, "recall": 0.0, "f1": 0.0, "tp": 0},
            },
        ],
    }
    (scores_dir / "judge_results.json").write_text(json.dumps(judge_results))

    from benchmarks.martian.config import BenchConfig

    cfg = BenchConfig(output_dir=output_dir)
    report(config=cfg)

    captured = capsys.readouterr().out
    assert "WARNING" in captured
    assert "NOT valid for public claims" in captured


def test_report_no_failures_clean_output(tmp_path, capsys):
    """Clean run shows 'No failures' message."""
    output_dir = tmp_path / "output"
    scores_dir = output_dir / "scores"
    scores_dir.mkdir(parents=True)

    judge_results = {
        "overall": {"precision": 0.8, "recall": 0.7, "f1": 0.74, "tp": 7},
        "per_pr": [
            {
                "pr": "keycloak_PR100",
                "golden_url": "https://github.com/keycloak/keycloak/pull/100",
                "n_candidates": 3,
                "n_golden": 2,
                "metrics": {"precision": 0.67, "recall": 1.0, "f1": 0.8, "tp": 2},
            },
        ],
    }
    (scores_dir / "judge_results.json").write_text(json.dumps(judge_results))

    from benchmarks.martian.config import BenchConfig

    cfg = BenchConfig(output_dir=output_dir)
    report(config=cfg)

    captured = capsys.readouterr().out
    assert "No failures" in captured
    assert "FAILURE ACCOUNTING" not in captured
