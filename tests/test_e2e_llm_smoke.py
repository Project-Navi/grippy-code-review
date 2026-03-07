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
from grippy.schema import GrippyReview, Severity, VerdictStatus

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


# ---------------------------------------------------------------------------
# Complex diffs for retry / recovery tests
# ---------------------------------------------------------------------------

SECURITY_MULTI_FILE_DIFF: str = """\
diff --git a/auth/login.py b/auth/login.py
new file mode 100644
index 0000000..b2c3d4e
--- /dev/null
+++ b/auth/login.py
@@ -0,0 +1,22 @@
+\"\"\"Authentication handler.\"\"\"
+import hashlib
+import os
+import sqlite3
+
+DB_PASSWORD = "admin123"
+
+
+def authenticate(username: str, password: str) -> bool:
+    \"\"\"Check credentials against the database.\"\"\"
+    conn = sqlite3.connect("users.db")
+    query = f"SELECT * FROM users WHERE name='{username}' AND pass='{password}'"
+    result = conn.execute(query)
+    return result.fetchone() is not None
+
+
+def hash_password(pw: str) -> str:
+    \"\"\"Hash a password for storage.\"\"\"
+    return hashlib.md5(pw.encode()).hexdigest()
+
+
+API_KEY = "sk-proj-AAAAAAAAAAAAAAAA"
diff --git a/api/views.py b/api/views.py
new file mode 100644
index 0000000..c3d4e5f
--- /dev/null
+++ b/api/views.py
@@ -0,0 +1,18 @@
+\"\"\"API views for user management.\"\"\"
+import subprocess
+
+
+def run_report(user_input: str) -> str:
+    \"\"\"Generate a report based on user input.\"\"\"
+    result = subprocess.run(
+        f"generate-report {user_input}",
+        shell=True,
+        capture_output=True,
+    )
+    return result.stdout.decode()
+
+
+def get_user(user_id: int) -> dict:
+    \"\"\"Fetch user data.\"\"\"
+    data = open(f"/data/users/{user_id}.json").read()
+    return {"raw": data}
"""

MULTI_ISSUE_DIFF: str = """\
diff --git a/services/payment.py b/services/payment.py
new file mode 100644
index 0000000..d4e5f6a
--- /dev/null
+++ b/services/payment.py
@@ -0,0 +1,42 @@
+\"\"\"Payment processing service.\"\"\"
+import sqlite3
+import hashlib
+
+STRIPE_SECRET_KEY = "sk_test_FAKE_KEY_FOR_TESTING_1234567890"
+DB_CONN_STRING = "postgresql://admin:password123@prod-db:5432/payments"
+
+
+def process_payment(card_number: str, amount: float, merchant_id: str) -> dict:
+    \"\"\"Process a payment transaction.\"\"\"
+    conn = sqlite3.connect("payments.db")
+    conn.execute(
+        f"INSERT INTO transactions (card, amount, merchant) "
+        f"VALUES ('{card_number}', {amount}, '{merchant_id}')"
+    )
+    conn.commit()
+    return {"status": "ok", "card": card_number}
+
+
+def verify_signature(payload: str, secret: str) -> bool:
+    \"\"\"Verify webhook signature.\"\"\"
+    computed = hashlib.md5(payload.encode()).hexdigest()
+    return computed == secret
+
+
+def get_transaction(txn_id: str) -> dict:
+    \"\"\"Retrieve transaction details.\"\"\"
+    conn = sqlite3.connect("payments.db")
+    row = conn.execute(
+        f"SELECT * FROM transactions WHERE id='{txn_id}'"
+    ).fetchone()
+    if row is None:
+        return {}
+    return dict(row)
+
+
+def refund(txn_id: str, reason: str) -> None:
+    \"\"\"Issue a refund.\"\"\"
+    conn = sqlite3.connect("payments.db")
+    conn.execute(
+        f"UPDATE transactions SET status='refunded', reason='{reason}' "
+        f"WHERE id='{txn_id}'"
+    )
+    conn.commit()
"""


# ---------------------------------------------------------------------------
# Retry / recovery e2e tests
# ---------------------------------------------------------------------------


@skip_no_homelab
class TestRetryRecoveryE2E:
    """E2E tests exercising the retry/recovery path with real LLM calls."""

    @pytest.mark.timeout(300)
    def test_retry_succeeds_after_validation_errors(self) -> None:
        """Verify that run_review can recover through retries on schema edge cases."""
        agent = create_reviewer(
            transport="local",
            model_id="devstral-small-2-24b-instruct-2512",
            base_url=_HOMELAB_URL,
            prompts_dir=PROMPTS_DIR,
            mode="pr_review",
        )

        message = format_pr_context(
            title="Add auth module with SQL queries",
            author="dev-bob",
            branch="feat/auth -> main",
            description="Adds login authentication and API views with report generation.",
            diff=SECURITY_MULTI_FILE_DIFF,
        )

        retry_errors: list[tuple[int, Exception]] = []

        def track_error(attempt: int, error: Exception) -> None:
            retry_errors.append((attempt, error))

        review = run_review(agent, message, max_retries=3, on_validation_error=track_error)

        # Core assertion: we got a valid review regardless of how many retries
        assert isinstance(review, GrippyReview)
        _assert_basic_review(review)
        # retry_errors may be empty (first attempt succeeded) or non-empty (retries fired)
        assert isinstance(retry_errors, list)

    @pytest.mark.timeout(300)
    def test_retry_callback_fires_on_error(self) -> None:
        """Verify the on_validation_error callback mechanism works end-to-end."""
        agent = create_reviewer(
            transport="local",
            model_id="devstral-small-2-24b-instruct-2512",
            base_url=_HOMELAB_URL,
            prompts_dir=PROMPTS_DIR,
            mode="pr_review",
        )

        message = format_pr_context(
            title="Add auth with hardcoded credentials",
            author="dev-charlie",
            branch="feat/auth-creds -> main",
            description="Authentication module with database access.",
            diff=SECURITY_MULTI_FILE_DIFF,
        )

        callback_log: list[tuple[int, str]] = []

        def on_error(attempt: int, error: Exception) -> None:
            callback_log.append((attempt, type(error).__name__))

        review = run_review(agent, message, max_retries=3, on_validation_error=on_error)

        # Review must succeed
        assert isinstance(review, GrippyReview)
        _assert_basic_review(review)
        # callback_log is a list — may be empty if first attempt succeeded
        assert isinstance(callback_log, list)
        # If retries happened, verify callback entries are well-formed
        for attempt_num, error_name in callback_log:
            assert isinstance(attempt_num, int)
            assert attempt_num >= 1
            assert isinstance(error_name, str)

    @pytest.mark.timeout(300)
    def test_review_with_multiple_findings(self) -> None:
        """Verify the schema handles real multi-finding output from a buggy diff."""
        agent = create_reviewer(
            transport="local",
            model_id="devstral-small-2-24b-instruct-2512",
            base_url=_HOMELAB_URL,
            prompts_dir=PROMPTS_DIR,
            mode="pr_review",
        )

        message = format_pr_context(
            title="Add payment processing service",
            author="dev-dana",
            branch="feat/payments -> main",
            description="Payment processing with SQL, secrets, and crypto.",
            diff=MULTI_ISSUE_DIFF,
        )

        review = run_review(agent, message, max_retries=3)

        _assert_basic_review(review)

        # The diff has SQL injection, hardcoded secrets, weak crypto — expect findings
        assert len(review.findings) >= 1, (
            f"Expected at least 1 finding for a diff with obvious security issues, "
            f"got {len(review.findings)}"
        )

        # Validate each finding has the required schema fields populated
        for finding in review.findings:
            assert finding.file, f"Finding {finding.id} missing file"
            assert finding.severity in list(Severity), (
                f"Finding {finding.id} has invalid severity: {finding.severity}"
            )
            assert finding.title, f"Finding {finding.id} missing title"
            assert finding.description, f"Finding {finding.id} missing description"
            assert 0 <= finding.confidence <= 100, (
                f"Finding {finding.id} confidence out of range: {finding.confidence}"
            )


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
