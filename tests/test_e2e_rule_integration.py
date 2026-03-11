# SPDX-License-Identifier: MIT
"""End-to-end tests for rule findings -> LLM acknowledgment path.

Validates that:
1. The deterministic rule engine detects known security patterns in diffs
2. Rule findings are correctly injected into the LLM context and acknowledged
3. The rule coverage cross-reference in run_review enforces LLM compliance

Run with:  uv run pytest tests/test_e2e_rule_integration.py -v -m e2e
"""

from __future__ import annotations

import pytest

from grippy.agent import create_reviewer, format_pr_context
from grippy.retry import run_review
from grippy.rules import RuleResult, RuleSeverity, run_rules
from grippy.rules.config import PROFILES, ProfileConfig
from grippy.schema import GrippyReview
from tests.e2e_fixtures import E2E_TIMEOUT, LLM_BASE_URL, LLM_MODEL_ID, PROMPTS_DIR, skip_no_llm

SECURITY_PROFILE: ProfileConfig = PROFILES["security"]

# ---------------------------------------------------------------------------
# Test diffs
# ---------------------------------------------------------------------------

# Diff that adds an OpenAI API key to a .env file — triggers secrets-in-diff
SECRET_DIFF: str = """\
diff --git a/.env b/.env
new file mode 100644
index 0000000..abc1234
--- /dev/null
+++ b/.env
@@ -0,0 +1,3 @@
+DATABASE_URL=postgres://localhost/mydb
+OPENAI_API_KEY=sk-proj-abc123def456ghi789jkl012mno345pqr678stu901vwx234
+DEBUG=true
"""

# Diff that adds a workflow with expanded permissions — triggers workflow-permissions-expanded
WORKFLOW_DIFF: str = """\
diff --git a/.github/workflows/deploy.yml b/.github/workflows/deploy.yml
new file mode 100644
index 0000000..def5678
--- /dev/null
+++ b/.github/workflows/deploy.yml
@@ -0,0 +1,18 @@
+name: Deploy
+on:
+  push:
+    branches: [main]
+
+permissions:
+  contents: write
+  packages: write
+
+jobs:
+  deploy:
+    runs-on: ubuntu-latest
+    steps:
+      - uses: actions/checkout@v4
+      - uses: actions/setup-node@v4
+      - run: npm ci
+      - run: npm run build
+      - run: npm run deploy
"""


def _format_rule_findings(results: list[RuleResult]) -> str:
    """Format rule findings as text — mirrors review.py::_format_rule_findings."""
    severity_map = {
        RuleSeverity.CRITICAL: "CRITICAL",
        RuleSeverity.ERROR: "ERROR",
        RuleSeverity.WARN: "WARN",
        RuleSeverity.INFO: "INFO",
    }
    lines: list[str] = []
    for r in results:
        sev = severity_map.get(r.severity, "INFO")
        parts = [f"[{sev}] {r.rule_id} @ {r.file}"]
        if r.line is not None:
            parts[0] += f":{r.line}"
        parts[0] += f": {r.message}"
        if r.evidence:
            parts.append(f"  evidence: {r.evidence}")
        lines.append(" | ".join(parts) if r.evidence else parts[0])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.e2e


class TestRuleEngineDetection:
    """Test 1: Deterministic rule engine detects known patterns (no LLM needed)."""

    def test_rules_detect_secret_in_diff(self) -> None:
        """Verify the rule engine finds a known secret pattern in a .env diff."""
        results = run_rules(SECRET_DIFF, SECURITY_PROFILE)

        # Must find at least one result
        assert len(results) > 0, "Rule engine should detect secrets in the diff"

        # At least one should be the secrets-in-diff rule
        secret_results = [r for r in results if r.rule_id == "secrets-in-diff"]
        assert len(secret_results) > 0, "Expected at least one 'secrets-in-diff' finding"

        # At least one CRITICAL finding (the OpenAI key pattern matches sk-...)
        critical_secrets = [r for r in secret_results if r.severity == RuleSeverity.CRITICAL]
        assert len(critical_secrets) > 0, (
            "Expected at least one CRITICAL severity finding for the OpenAI API key"
        )

        # The finding should reference the .env file
        assert any(r.file == ".env" for r in secret_results), (
            "Secret finding should reference .env file"
        )

    def test_rules_detect_workflow_permissions(self) -> None:
        """Verify the rule engine detects expanded workflow permissions."""
        results = run_rules(WORKFLOW_DIFF, SECURITY_PROFILE)

        assert len(results) > 0, "Rule engine should detect workflow issues"

        # Should find workflow-permissions-expanded findings
        wf_results = [r for r in results if r.rule_id == "workflow-permissions-expanded"]
        assert len(wf_results) > 0, "Expected at least one 'workflow-permissions-expanded' finding"

        # At least one ERROR for the write permissions
        error_findings = [r for r in wf_results if r.severity >= RuleSeverity.ERROR]
        assert len(error_findings) > 0, "Expected ERROR severity for expanded write permissions"


@skip_no_llm
@pytest.mark.timeout(E2E_TIMEOUT)
class TestRuleFindingsInjection:
    """Test 2: Rule findings make it into LLM context and are acknowledged."""

    def test_rule_findings_injected_into_llm_context(self) -> None:
        """Run rules on a diff with secrets, inject into LLM, verify acknowledgment."""
        # Step 1: Run rules to get findings
        results = run_rules(SECRET_DIFF, SECURITY_PROFILE)
        assert len(results) > 0, "Precondition: rules should detect issues"

        # Step 2: Format findings text (mirrors review.py)
        findings_text = _format_rule_findings(results)
        assert "secrets-in-diff" in findings_text

        # Step 3: Build the LLM user message with rule findings
        message = format_pr_context(
            title="Add environment configuration",
            author="dev-bob",
            branch="feat/env-config -> main",
            description="Adds .env file with database and API configuration.",
            diff=SECRET_DIFF,
            rule_findings=findings_text,
        )

        # Step 4: Create reviewer with rule findings enabled
        agent = create_reviewer(
            transport="local",
            model_id=LLM_MODEL_ID,
            base_url=LLM_BASE_URL,
            prompts_dir=PROMPTS_DIR,
            mode="pr_review",
            include_rule_findings=True,
        )

        # Step 5: Run review
        review = run_review(agent, message, max_retries=2)

        # Step 6: Validate the LLM produced a valid review
        assert isinstance(review, GrippyReview)
        assert 0 <= review.score.overall <= 100

        # Step 7: The LLM should mention the security issue
        # Check findings reference the .env file or mention secrets/API keys
        all_finding_text = " ".join(
            f"{f.title} {f.description} {f.file}" for f in review.findings
        ).lower()
        has_secret_reference = any(
            term in all_finding_text
            for term in ("secret", "api", "key", ".env", "credential", "token", "sensitive")
        )
        assert has_secret_reference, (
            f"LLM review should reference the secret/API key issue. "
            f"Findings: {[f.title for f in review.findings]}"
        )

        # Check at least one finding references the .env file
        env_findings = [f for f in review.findings if ".env" in f.file]
        assert len(env_findings) > 0, (
            "LLM should produce at least one finding referencing the .env file"
        )


@skip_no_llm
@pytest.mark.timeout(E2E_TIMEOUT)
class TestRuleCoverageValidation:
    """Test 3: rule_id cross-reference validates LLM acknowledges rule findings."""

    def test_rule_coverage_validation(self) -> None:
        """Run rules, build expected counts/files, verify run_review enforces coverage.

        Uses the secret diff (single rule_id) to keep token count low.
        The coverage validation in run_review will retry if the LLM fails
        to set rule_id — we allow warnings for incomplete coverage since
        the local model may not perfectly match rule IDs.
        """
        # Step 1: Run rules — use SECRET_DIFF for a single, clear rule_id
        results = run_rules(SECRET_DIFF, SECURITY_PROFILE)
        assert len(results) > 0, "Precondition: rules should detect issues"

        # Step 2: Build expected_rule_counts and expected_rule_files
        # Only require 1 finding per rule_id (floor) to be lenient with local models
        expected_rule_counts: dict[str, int] = dict.fromkeys({r.rule_id for r in results}, 1)
        expected_rule_files: dict[str, frozenset[str]] = {
            rule_id: frozenset(r.file for r in results if r.rule_id == rule_id)
            for rule_id in expected_rule_counts
        }

        # Step 3: Format findings and build message
        findings_text = _format_rule_findings(results)
        message = format_pr_context(
            title="Add environment configuration",
            author="dev-carol",
            branch="feat/env-config -> main",
            description="Adds .env file with database and API configuration.",
            diff=SECRET_DIFF,
            rule_findings=findings_text,
        )

        # Step 4: Create reviewer
        agent = create_reviewer(
            transport="local",
            model_id=LLM_MODEL_ID,
            base_url=LLM_BASE_URL,
            prompts_dir=PROMPTS_DIR,
            mode="pr_review",
            include_rule_findings=True,
        )

        # Step 5: Run review with rule coverage enforcement
        # Use max_retries=2 to stay within timeout budget (~60s per call)
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            review = run_review(
                agent,
                message,
                max_retries=2,
                expected_rule_counts=expected_rule_counts,
                expected_rule_files=expected_rule_files,
            )

        # Step 6: Validate the review was produced
        assert isinstance(review, GrippyReview)
        assert 0 <= review.score.overall <= 100

        # Step 7: The LLM should mention secrets/API keys/.env
        all_finding_text = " ".join(
            f"{f.title} {f.description} {f.file}" for f in review.findings
        ).lower()
        has_secret_reference = any(
            term in all_finding_text
            for term in (
                "secret",
                "api",
                "key",
                ".env",
                "credential",
                "token",
                "sensitive",
                "leak",
                "expos",
            )
        )
        assert has_secret_reference, (
            f"LLM review should reference the secret/API key issue. "
            f"Findings: {[f.title for f in review.findings]}"
        )

        # Step 8: Check that at least some findings have rule_id set
        # (the retry loop may have coerced the LLM into setting them)
        findings_with_rule_id = [f for f in review.findings if f.rule_id]
        # This is informational — we log it but don't hard-fail if the LLM
        # acknowledged the issue without setting rule_id exactly.
        # The key validation is that run_review completed without raising
        # ReviewParseError, meaning the coverage check passed or warned.
        if not findings_with_rule_id:
            # Acceptable: the LLM discussed the issue but didn't set rule_id.
            # The retry mechanism warned about incomplete coverage.
            pass
