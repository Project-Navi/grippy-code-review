<!-- SPDX-License-Identifier: MIT -->

# Test Coverage: rule-secrets

**Audit date:** 2026-03-13
**Commit:** 259d0b8

---

## Test File Inventory

| Test File | Source File | Test Count | LOC (test) | LOC (source) | Ratio |
|-----------|------------|:----------:|:----------:|:------------:|:-----:|
| `tests/test_grippy_rule_secrets.py` | `src/grippy/rules/secrets_in_diff.py` | 14 | 116 | 138 | 0.84:1 |

All 14 tests pass. Static analysis (ruff, mypy, bandit) clean on both files.

---

## Coverage Gaps

### Gap 1: No adversarial/ReDoS tests (SR-02) — HIGH

**LOC at risk:** 25 lines (10 regex patterns at lines 12-37)
**Finding:** F-RS-001

No test exercises the regex patterns with adversarial-length input. While manual analysis suggests the patterns are structurally safe, the SR-02 checklist item requires Tier A evidence (test). A parametrized test with 100K+ character input per pattern would close this gap.

**Remediation:** ~10 LOC (1 parametrized test with 10 pattern inputs).

### Gap 2: No renamed/binary/submodule diff tests (SR-09) — MEDIUM

**LOC at risk:** 15 lines (diff iteration logic at lines 86-129)
**Finding:** F-RS-002

The rule's behavior when encountering renamed files, binary diffs, or submodule updates is untested. `parse_diff()` (in context.py) handles these formats, and the rule iterates over the parsed output. Failure here would be silent (no crash, but possible missed detection or false positive).

**Remediation:** ~15 LOC (3 tests with edge-case diff formats).

### Gap 3: No integration test through enrichment pipeline (SR-08) — LOW

**LOC at risk:** 8 lines (RuleResult construction at lines 96-128)

The rule returns `list[RuleResult]`, which is structurally compatible with `enrich_results()`. No test proves this integration end-to-end at the rule level. The engine-level tests may cover this, but it's not verified from the rule-secrets audit scope.

**Remediation:** ~10 LOC (1 integration test calling `enrich_results()` on rule output).

---

## Per-Source Summary

| Source File | LOC | Functions | Tested Functions | Untested Functions | Gap Priority |
|-------------|:---:|:---------:|:----------------:|:------------------:|:------------|
| `secrets_in_diff.py` | 138 | 5 | 5 (all) | 0 | Fixture depth, not function coverage |

All 5 functions (`_is_comment_line`, `_is_placeholder`, `_in_tests_dir`, `SecretsInDiffRule.run`, `SecretsInDiffRule._redact`) are exercised by existing tests. The gap is in fixture breadth (adversarial/edge-case inputs), not function coverage.

---

## Recommendations

| Priority | Gap | LOC Estimate | Checklist Item |
|:--------:|-----|:------------:|:--------------:|
| 1 | Add adversarial ReDoS test (100K+ char input per pattern) | ~10 | SR-02 |
| 2 | Add renamed/binary/submodule diff fixtures | ~15 | SR-09 |
| 3 | Add enrichment integration test | ~10 | SR-08 |
| **Total** | | **~35 LOC** | |
