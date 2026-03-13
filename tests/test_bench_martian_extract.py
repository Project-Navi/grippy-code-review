# SPDX-License-Identifier: MIT
"""Tests for benchmarks/martian/extract.py."""

from benchmarks.martian.extract import (
    EXTRACT_SYSTEM_PROMPT,
    EXTRACT_USER_PROMPT,
    extract_candidates_for_pr,
    inline_to_candidate,
)


def test_extract_prompt_matches_martian():
    """Verify prompts are vendored verbatim from Martian."""
    assert "Extract each distinct code issue" in EXTRACT_USER_PROMPT
    assert "Each issue should be a single, specific problem" in EXTRACT_USER_PROMPT
    assert "You extract code review issues" in EXTRACT_SYSTEM_PROMPT


def test_inline_to_candidate():
    inline = {"path": "src/auth.py", "line": 42, "body": "SQL injection risk"}
    candidate = inline_to_candidate(inline)
    assert candidate["text"] == "SQL injection risk"
    assert candidate["path"] == "src/auth.py"
    assert candidate["line"] == 42
    assert candidate["source"] == "inline"


def test_extract_candidates_all_inline():
    """When all findings are inline, no LLM extraction needed."""
    comments = {
        "inline": [
            {"path": "a.py", "line": 1, "body": "Issue one"},
            {"path": "b.py", "line": 2, "body": "Issue two"},
        ],
        "general": [],
    }
    candidates = extract_candidates_for_pr(comments, llm_extract_fn=None)
    assert len(candidates) == 2
    assert all(c["source"] == "inline" for c in candidates)


def test_extract_candidates_with_general():
    """General comments go through LLM extraction."""
    comments = {
        "inline": [{"path": "a.py", "line": 1, "body": "Inline issue"}],
        "general": ["Found two problems: null check missing and race condition"],
    }

    def mock_extract(text):
        return ["null check missing", "race condition"]

    candidates = extract_candidates_for_pr(comments, llm_extract_fn=mock_extract)
    assert len(candidates) == 3
    assert candidates[0]["source"] == "inline"
    assert candidates[1]["source"] == "extracted"
    assert candidates[2]["source"] == "extracted"
    assert candidates[1]["text"] == "null check missing"
