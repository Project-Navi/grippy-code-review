# SPDX-License-Identifier: MIT
"""End-to-end smoke tests — real diffs through real LLM providers.

Each test sends a small diff through the full Grippy pipeline
(create_reviewer -> format_pr_context -> run_review) and validates the
structured output against the GrippyReview Pydantic schema.

Tests skip automatically when the required API key is absent.
Run with:  uv run pytest tests/test_e2e_llm_smoke.py -v -m e2e
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from grippy.agent import DEFAULT_PROMPTS_DIR, create_reviewer, format_pr_context
from grippy.retry import run_review
from grippy.schema import GrippyReview, VerdictStatus

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

PROMPTS_DIR: Path = DEFAULT_PROMPTS_DIR

SMALL_DIFF: str = """\
diff --git a/utils/math.py b/utils/math.py
new file mode 100644
index 0000000..a1b2c3d
--- /dev/null
+++ b/utils/math.py
@@ -0,0 +1,15 @@
+\"\"\"Simple math utilities.\"\"\"
+
+
+def clamp(value: float, lo: float, hi: float) -> float:
+    \"\"\"Clamp *value* between *lo* and *hi* inclusive.\"\"\"
+    if lo > hi:
+        raise ValueError(f"lo ({lo}) must be <= hi ({hi})")
+    return max(lo, min(hi, value))
+
+
+def safe_divide(a: float, b: float, default: float = 0.0) -> float:
+    \"\"\"Return a / b, falling back to *default* when b is zero.\"\"\"
+    if b == 0:
+        return default
+    return a / b
"""


_HOMELAB_URL = "http://100.72.243.82:1234/v1"


def _run_pipeline(
    transport: str,
    model_id: str,
    base_url: str | None = None,
) -> GrippyReview:
    """Helper: create agent, format context, run review, return result."""
    kwargs: dict[str, str] = {}
    if base_url:
        kwargs["base_url"] = base_url
    agent = create_reviewer(
        transport=transport,
        model_id=model_id,
        prompts_dir=PROMPTS_DIR,
        mode="pr_review",
        **kwargs,
    )

    message = format_pr_context(
        title="Add math utility helpers",
        author="dev-alice",
        branch="feat/math-utils -> main",
        description="Adds clamp() and safe_divide() helpers for numeric processing.",
        diff=SMALL_DIFF,
    )

    return run_review(agent, message, max_retries=2)


# ---------------------------------------------------------------------------
# Skip conditions
# ---------------------------------------------------------------------------

skip_no_openai = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set",
)
skip_no_anthropic = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)
skip_no_groq = pytest.mark.skipif(
    not os.environ.get("GROQ_API_KEY"),
    reason="GROQ_API_KEY not set",
)
skip_no_google = pytest.mark.skipif(
    not os.environ.get("GOOGLE_API_KEY"),
    reason="GOOGLE_API_KEY not set",
)


def _homelab_reachable() -> bool:
    """Return True if the homelab LM Studio endpoint responds."""
    import socket

    try:
        with socket.create_connection(("100.72.243.82", 1234), timeout=2):
            return True
    except OSError:
        return False


skip_no_homelab = pytest.mark.skipif(
    not _homelab_reachable(),
    reason="Homelab LM Studio not reachable at 100.72.243.82:1234",
)

_ANY_KEY_AVAILABLE = any(
    os.environ.get(k)
    for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GROQ_API_KEY", "GOOGLE_API_KEY")
)

_ANY_PROVIDER_AVAILABLE = _ANY_KEY_AVAILABLE or _homelab_reachable()

skip_no_any_key = pytest.mark.skipif(
    not _ANY_PROVIDER_AVAILABLE,
    reason="No LLM available (need API key or homelab reachable)",
)


def _pick_available_provider() -> tuple[str, str, str | None]:
    """Return (transport, model_id, base_url) for the first available provider."""
    if os.environ.get("OPENAI_API_KEY"):
        return ("openai", "gpt-4.1-mini", None)
    if os.environ.get("ANTHROPIC_API_KEY"):
        return ("anthropic", "claude-sonnet-4-20250514", None)
    if os.environ.get("GROQ_API_KEY"):
        return ("groq", "llama-3.3-70b-versatile", None)
    if os.environ.get("GOOGLE_API_KEY"):
        return ("google", "gemini-2.0-flash", None)
    if _homelab_reachable():
        return ("local", "devstral-small-2-24b-instruct-2512", _HOMELAB_URL)
    msg = "No LLM provider available"
    raise RuntimeError(msg)


# ---------------------------------------------------------------------------
# Shared assertions
# ---------------------------------------------------------------------------


def _assert_basic_review(review: GrippyReview) -> None:
    """Common assertions for any provider smoke test."""
    assert isinstance(review, GrippyReview)
    assert 0 <= review.score.overall <= 100
    assert review.verdict.status in list(VerdictStatus)
    assert isinstance(review.findings, list)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.e2e


@skip_no_openai
@pytest.mark.timeout(120)
class TestOpenAISmoke:
    """Smoke test against OpenAI (gpt-4.1-mini)."""

    def test_openai_review(self) -> None:
        review = _run_pipeline("openai", "gpt-4.1-mini")
        _assert_basic_review(review)


@skip_no_anthropic
@pytest.mark.timeout(120)
class TestAnthropicSmoke:
    """Smoke test against Anthropic (claude-sonnet-4-20250514)."""

    def test_anthropic_review(self) -> None:
        review = _run_pipeline("anthropic", "claude-sonnet-4-20250514")
        _assert_basic_review(review)


@skip_no_groq
@pytest.mark.timeout(120)
class TestGroqSmoke:
    """Smoke test against Groq (llama-3.3-70b-versatile)."""

    def test_groq_review(self) -> None:
        review = _run_pipeline("groq", "llama-3.3-70b-versatile")
        _assert_basic_review(review)


@skip_no_google
@pytest.mark.timeout(120)
class TestGoogleSmoke:
    """Smoke test against Google (gemini-2.0-flash)."""

    def test_google_review(self) -> None:
        review = _run_pipeline("google", "gemini-2.0-flash")
        _assert_basic_review(review)


@skip_no_homelab
@pytest.mark.timeout(180)
class TestLocalHomelabSmoke:
    """Smoke test against homelab LM Studio (devstral-small 24B Q4)."""

    def test_local_review(self) -> None:
        review = _run_pipeline(
            "local",
            "devstral-small-2-24b-instruct-2512",
            base_url=_HOMELAB_URL,
        )
        _assert_basic_review(review)


@skip_no_any_key
@pytest.mark.timeout(120)
class TestSchemaCompleteness:
    """Deep schema validation using whichever provider is available."""

    def test_schema_fields_populated(self) -> None:
        transport, model_id, base_url = _pick_available_provider()
        review = _run_pipeline(transport, model_id, base_url=base_url)

        # Basic review assertions
        _assert_basic_review(review)

        # Score
        assert isinstance(review.score.overall, int)
        assert 0 <= review.score.breakdown.security <= 100
        assert 0 <= review.score.breakdown.logic <= 100

        # Verdict
        assert review.verdict.status in list(VerdictStatus)
        assert isinstance(review.verdict.summary, str)
        assert len(review.verdict.summary) > 0

        # Personality
        assert isinstance(review.personality.opening_catchphrase, str)
        assert len(review.personality.opening_catchphrase) > 0
        assert isinstance(review.personality.closing_line, str)

        # PR metadata
        assert review.pr.title
        assert review.pr.author

        # Scope
        assert review.scope.files_in_diff >= 1
        assert 0 <= review.scope.coverage_percentage <= 100

        # Meta
        assert review.meta.tokens_used >= 0
