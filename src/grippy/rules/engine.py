# SPDX-License-Identifier: MIT
"""Rule engine — instantiates rule classes and runs them against a diff context."""

from __future__ import annotations

from typing import TYPE_CHECKING

from grippy.rules.base import Rule, RuleResult

if TYPE_CHECKING:
    from grippy.rules.config import ProfileConfig
    from grippy.rules.context import RuleContext


class RuleEngine:
    """Instantiates rules from class registry and runs them against a context."""

    def __init__(self, rule_classes: list[type[Rule]] | None = None) -> None:
        from grippy.rules.registry import RULE_REGISTRY

        self._rules: list[Rule] = [cls() for cls in (rule_classes or RULE_REGISTRY)]

    def run(self, ctx: RuleContext) -> list[RuleResult]:
        """Run all rules and collect results, filtering # nogrip pragmas."""
        from grippy.ignore import build_nogrip_index

        nogrip_index = build_nogrip_index(ctx)
        results: list[RuleResult] = []
        for rule in self._rules:
            for finding in rule.run(ctx):
                if finding.line is None:
                    results.append(finding)
                    continue
                nogrip = nogrip_index.get((finding.file, finding.line))
                if nogrip is True:
                    continue  # bare # nogrip — suppress all
                if isinstance(nogrip, set) and finding.rule_id in nogrip:
                    continue  # targeted # nogrip — suppress matching rule
                results.append(finding)
        return results

    def check_gate(self, results: list[RuleResult], config: ProfileConfig) -> bool:
        """Return True if any non-suppressed result meets or exceeds the profile's fail_on threshold."""
        return any(
            r.severity.value >= config.fail_on.value
            for r in results
            if not (r.enrichment and r.enrichment.suppressed)
        )
