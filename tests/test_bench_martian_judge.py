# SPDX-License-Identifier: MIT
"""Tests for benchmarks/martian/judge.py."""

import pytest

from benchmarks.martian.judge import (
    JUDGE_PROMPT,
    compute_metrics,
    judge_pair,
    match_candidates_to_golden,
)


def test_judge_prompt_matches_martian():
    assert "Determine if the candidate identifies the SAME underlying issue" in JUDGE_PROMPT
    assert "Accept semantic matches" in JUDGE_PROMPT


def test_match_candidates_greedy_assignment():
    """Each golden matches at most one candidate (highest confidence)."""
    verdicts = [
        {"golden_idx": 0, "candidate_idx": 0, "match": True, "confidence": 0.9},
        {"golden_idx": 0, "candidate_idx": 1, "match": True, "confidence": 0.7},
        {"golden_idx": 1, "candidate_idx": 0, "match": True, "confidence": 0.8},
        {"golden_idx": 1, "candidate_idx": 1, "match": False, "confidence": 0.3},
    ]
    matches = match_candidates_to_golden(verdicts, n_golden=2, n_candidates=2)
    # Golden 0 matches candidate 0 (conf 0.9)
    # Golden 1 must match candidate 1 (candidate 0 already taken) — but conf 0.3, no match
    assert matches[0] == 0  # golden 0 → candidate 0
    assert matches[1] is None  # golden 1 → no match (candidate 0 taken, candidate 1 no match)


def test_compute_metrics_perfect():
    metrics = compute_metrics(tp=3, total_candidates=3, total_golden=3)
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["f1"] == 1.0


def test_compute_metrics_partial():
    metrics = compute_metrics(tp=2, total_candidates=4, total_golden=3)
    assert metrics["precision"] == pytest.approx(0.5)
    assert metrics["recall"] == pytest.approx(2 / 3, abs=0.01)


def test_compute_metrics_zero_candidates():
    metrics = compute_metrics(tp=0, total_candidates=0, total_golden=3)
    assert metrics["precision"] == 0.0
    assert metrics["recall"] == 0.0
    assert metrics["f1"] == 0.0


def test_judge_pair_with_custom_fn():
    """judge_pair uses custom fn when provided."""

    def mock_judge(golden, candidate):
        return {"reasoning": "mock", "match": True, "confidence": 0.95}

    result = judge_pair("golden text", "candidate text", judge_fn=mock_judge)
    assert result["match"] is True
    assert result["confidence"] == 0.95
