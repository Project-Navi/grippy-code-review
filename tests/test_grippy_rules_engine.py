# SPDX-License-Identifier: MIT
"""Tests for grippy.rules.engine — RuleEngine run + gate checking."""

from __future__ import annotations

import pytest

from grippy.rules.base import RuleResult, RuleSeverity
from grippy.rules.config import PROFILES, ProfileConfig
from grippy.rules.context import RuleContext, parse_diff
from grippy.rules.engine import RuleEngine


class _AlwaysWarnRule:
    """Test rule that always emits a WARN."""

    id = "test-warn"
    description = "Test rule"
    default_severity = RuleSeverity.WARN

    def run(self, ctx: RuleContext) -> list[RuleResult]:
        return [
            RuleResult(
                rule_id=self.id,
                severity=self.default_severity,
                message="test warning",
                file="test.py",
                line=1,
            )
        ]


class _AlwaysErrorRule:
    """Test rule that always emits an ERROR."""

    id = "test-error"
    description = "Test rule"
    default_severity = RuleSeverity.ERROR

    def run(self, ctx: RuleContext) -> list[RuleResult]:
        return [
            RuleResult(
                rule_id=self.id,
                severity=self.default_severity,
                message="test error",
                file="test.py",
                line=1,
            )
        ]


class _NoFindingsRule:
    """Test rule that never finds anything."""

    id = "test-clean"
    description = "Test rule"
    default_severity = RuleSeverity.INFO

    def run(self, ctx: RuleContext) -> list[RuleResult]:
        return []


class TestRuleEngine:
    def _ctx(self) -> RuleContext:
        return RuleContext(
            diff="",
            files=[],
            config=ProfileConfig(name="test", fail_on=RuleSeverity.ERROR),
        )

    def test_run_collects_results(self) -> None:
        engine = RuleEngine(rule_classes=[_AlwaysWarnRule, _AlwaysErrorRule])
        results = engine.run(self._ctx())
        assert len(results) == 2
        ids = {r.rule_id for r in results}
        assert ids == {"test-warn", "test-error"}

    def test_run_empty_rules(self) -> None:
        engine = RuleEngine(rule_classes=[])
        assert engine.run(self._ctx()) == []

    def test_run_no_findings(self) -> None:
        engine = RuleEngine(rule_classes=[_NoFindingsRule])
        assert engine.run(self._ctx()) == []

    def test_check_gate_error_on_security_profile(self) -> None:
        config = ProfileConfig(name="security", fail_on=RuleSeverity.ERROR)
        engine = RuleEngine(rule_classes=[])

        error_results = [
            RuleResult(rule_id="x", severity=RuleSeverity.ERROR, message="m", file="f")
        ]
        assert engine.check_gate(error_results, config) is True

        warn_results = [RuleResult(rule_id="x", severity=RuleSeverity.WARN, message="m", file="f")]
        assert engine.check_gate(warn_results, config) is False

    def test_check_gate_warn_on_strict(self) -> None:
        config = ProfileConfig(name="strict", fail_on=RuleSeverity.WARN)
        engine = RuleEngine(rule_classes=[])

        warn_results = [RuleResult(rule_id="x", severity=RuleSeverity.WARN, message="m", file="f")]
        assert engine.check_gate(warn_results, config) is True

        info_results = [RuleResult(rule_id="x", severity=RuleSeverity.INFO, message="m", file="f")]
        assert engine.check_gate(info_results, config) is False

    def test_check_gate_critical_on_general(self) -> None:
        config = ProfileConfig(name="general", fail_on=RuleSeverity.CRITICAL)
        engine = RuleEngine(rule_classes=[])

        error_results = [
            RuleResult(rule_id="x", severity=RuleSeverity.ERROR, message="m", file="f")
        ]
        assert engine.check_gate(error_results, config) is False

        critical_results = [
            RuleResult(rule_id="x", severity=RuleSeverity.CRITICAL, message="m", file="f")
        ]
        assert engine.check_gate(critical_results, config) is True

    def test_check_gate_empty_results(self) -> None:
        config = ProfileConfig(name="strict", fail_on=RuleSeverity.WARN)
        engine = RuleEngine(rule_classes=[])
        assert engine.check_gate([], config) is False

    def test_default_registry_loads(self) -> None:
        """Verify default engine loads all rules from the registry."""
        engine = RuleEngine()
        assert len(engine._rules) == 10

    def test_check_gate_skips_suppressed(self) -> None:
        from dataclasses import replace

        from grippy.rules.base import ResultEnrichment

        suppressed_enrichment = ResultEnrichment(
            blast_radius=0,
            is_recurring=False,
            prior_count=0,
            suppressed=True,
            suppression_reason="file imports sqlalchemy",
            velocity="",
        )
        results = [
            replace(
                RuleResult(
                    rule_id="sql-injection-risk",
                    severity=RuleSeverity.ERROR,
                    message="SQL injection risk",
                    file="app.py",
                ),
                enrichment=suppressed_enrichment,
            )
        ]
        config = ProfileConfig(name="security", fail_on=RuleSeverity.ERROR)
        assert not RuleEngine(rule_classes=[]).check_gate(results, config)

    def test_check_gate_still_fails_on_unsuppressed(self) -> None:
        from dataclasses import replace

        from grippy.rules.base import ResultEnrichment

        unsuppressed = ResultEnrichment(
            blast_radius=3,
            is_recurring=True,
            prior_count=2,
            suppressed=False,
            suppression_reason="",
            velocity="",
        )
        results = [
            replace(
                RuleResult(
                    rule_id="sql-injection-risk",
                    severity=RuleSeverity.ERROR,
                    message="SQL injection risk",
                    file="app.py",
                ),
                enrichment=unsuppressed,
            )
        ]
        config = ProfileConfig(name="security", fail_on=RuleSeverity.ERROR)
        assert RuleEngine(rule_classes=[]).check_gate(results, config)


# --- Convenience wrappers from grippy.rules.__init__ ---


class TestConvenienceWrappers:
    """Verify run_rules() and check_gate() wrappers in grippy.rules.__init__."""

    def test_run_rules_returns_results(self) -> None:
        """run_rules() parses diff, runs engine, returns results."""
        from grippy.rules import run_rules
        from grippy.rules.config import ProfileConfig

        profile = ProfileConfig(name="security", fail_on=RuleSeverity.ERROR)
        # A diff with no security issues should return empty or only low findings
        diff = "diff --git a/readme.md b/readme.md\n--- a/readme.md\n+++ b/readme.md\n@@ -1 +1 @@\n-old\n+new\n"
        results = run_rules(diff, profile)
        assert isinstance(results, list)

    def test_run_rules_detects_known_pattern(self) -> None:
        """run_rules() detects a known security pattern (private key header)."""
        from grippy.rules import run_rules
        from grippy.rules.config import ProfileConfig

        profile = ProfileConfig(name="security", fail_on=RuleSeverity.ERROR)
        diff = (
            "diff --git a/config.py b/config.py\n"
            "--- a/config.py\n+++ b/config.py\n"
            "@@ -1,1 +1,2 @@\n"
            " # config\n"
            "+-----BEGIN RSA PRIVATE KEY-----\n"  # pragma: allowlist secret
        )
        results = run_rules(diff, profile)
        assert any(r.rule_id == "secrets-in-diff" for r in results)

    def test_check_gate_wrapper(self) -> None:
        """check_gate() wrapper delegates to engine correctly."""
        from grippy.rules import check_gate
        from grippy.rules.config import ProfileConfig

        profile = ProfileConfig(name="security", fail_on=RuleSeverity.ERROR)
        error_results = [
            RuleResult(rule_id="x", severity=RuleSeverity.ERROR, message="m", file="f")
        ]
        assert check_gate(error_results, profile) is True

        warn_results = [RuleResult(rule_id="x", severity=RuleSeverity.WARN, message="m", file="f")]
        assert check_gate(warn_results, profile) is False


class TestResultEnrichment:
    def test_rule_result_default_enrichment_is_none(self) -> None:
        r = RuleResult(rule_id="test", severity=RuleSeverity.WARN, message="msg", file="f.py")
        assert r.enrichment is None

    def test_rule_result_with_enrichment(self) -> None:
        from grippy.rules.base import ResultEnrichment

        e = ResultEnrichment(
            blast_radius=5,
            is_recurring=True,
            prior_count=3,
            suppressed=False,
            suppression_reason="",
            velocity="",
        )
        r = RuleResult(
            rule_id="test",
            severity=RuleSeverity.WARN,
            message="msg",
            file="f.py",
            enrichment=e,
        )
        assert r.enrichment is not None
        assert r.enrichment.blast_radius == 5
        assert r.enrichment.is_recurring is True
        assert r.enrichment.prior_count == 3

    def test_enrichment_is_frozen(self) -> None:
        from grippy.rules.base import ResultEnrichment

        e = ResultEnrichment(
            blast_radius=0,
            is_recurring=False,
            prior_count=0,
            suppressed=False,
            suppression_reason="",
            velocity="",
        )
        with pytest.raises(AttributeError):
            e.blast_radius = 99  # type: ignore[misc]

    def test_replace_adds_enrichment(self) -> None:
        from dataclasses import replace

        from grippy.rules.base import ResultEnrichment

        r = RuleResult(rule_id="test", severity=RuleSeverity.WARN, message="msg", file="f.py")
        e = ResultEnrichment(
            blast_radius=2,
            is_recurring=False,
            prior_count=0,
            suppressed=False,
            suppression_reason="",
            velocity="",
        )
        r2 = replace(r, enrichment=e)
        assert r.enrichment is None  # original unchanged
        assert r2.enrichment is not None
        assert r2.enrichment.blast_radius == 2


# --- nogrip pragma integration ---


def _make_diff(filename: str, added_lines: list[str]) -> str:
    body = "\n".join(f"+{line}" for line in added_lines)
    return (
        f"diff --git a/{filename} b/{filename}\n"
        f"new file mode 100644\n"
        f"--- /dev/null\n"
        f"+++ b/{filename}\n"
        f"@@ -0,0 +1,{len(added_lines)} @@\n"
        f"{body}\n"
    )


class TestNogrip:
    def test_bare_nogrip_suppresses_all_rules(self) -> None:
        diff = _make_diff("app.py", ["h = hashlib.md5(data)  # nogrip"])
        ctx = RuleContext(diff=diff, files=parse_diff(diff), config=PROFILES["security"])
        results = RuleEngine().run(ctx)
        assert all(r.file != "app.py" or r.line != 1 for r in results)

    def test_targeted_nogrip_suppresses_matching_rule(self) -> None:
        diff = _make_diff("app.py", ["h = hashlib.md5(data)  # nogrip: weak-crypto"])
        ctx = RuleContext(diff=diff, files=parse_diff(diff), config=PROFILES["security"])
        results = RuleEngine().run(ctx)
        assert not any(r.rule_id == "weak-crypto" and r.file == "app.py" for r in results)

    def test_targeted_nogrip_does_not_suppress_other_rules(self) -> None:
        diff = _make_diff("app.py", ["h = hashlib.md5(data)  # nogrip: sql-injection-risk"])
        ctx = RuleContext(diff=diff, files=parse_diff(diff), config=PROFILES["security"])
        results = RuleEngine().run(ctx)
        assert any(r.rule_id == "weak-crypto" and r.file == "app.py" for r in results)

    def test_nogrip_gate_check(self) -> None:
        diff = _make_diff("app.py", ["h = hashlib.md5(data)  # nogrip"])
        ctx = RuleContext(
            diff=diff, files=parse_diff(diff), config=PROFILES["strict-security"]
        )
        engine = RuleEngine()
        results = engine.run(ctx)
        assert not engine.check_gate(results, PROFILES["strict-security"])

    def test_nogrip_uses_original_line_not_evidence(self) -> None:
        """Pragma at column 121+ must still suppress (evidence is truncated to 120)."""
        padding = "x" * 115
        line = f"{padding} = 1  # nogrip"  # pragma is past char 120
        diff = _make_diff("app.py", [line])
        ctx = RuleContext(diff=diff, files=parse_diff(diff), config=PROFILES["security"])
        results = RuleEngine().run(ctx)
        # If any rule fires on this line, nogrip should still suppress it
        assert all(r.file != "app.py" or r.line != 1 for r in results)
