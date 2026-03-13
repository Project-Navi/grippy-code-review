<!-- SPDX-License-Identifier: MIT -->

# Unit Census: rule-secrets

**Audit date:** 2026-03-13
**Commit:** 259d0b8
**Unit type:** security-rule (primary), no secondary
**Phase:** 1 (Core Infra)
**Trust boundaries:** None (consumer of TB-2 via rule-engine, not an anchor owner)

---

## File Inventory

| File | LOC | Role |
|------|----:|------|
| `src/grippy/rules/secrets_in_diff.py` | 138 | Source |
| `tests/test_grippy_rule_secrets.py` | 116 | Test |
| **Total** | **254** | |

Test:source ratio: 0.84:1

---

## Dependency Graph

### Internal Dependencies (grippy.*)

| Import | Module | Phase |
|--------|--------|------:|
| `RuleResult`, `RuleSeverity` | `grippy.rules.base` | 1 |
| `RuleContext` | `grippy.rules.context` | 1 |

### External Dependencies

| Import | Package |
|--------|---------|
| `re` | stdlib |

### Dependents (who imports this unit)

| Module | Import |
|--------|--------|
| `grippy.rules.registry` | `SecretsInDiffRule` (added to `RULE_REGISTRY`) |

---

## Public Surface

| Symbol | Type | Signature |
|--------|------|-----------|
| `SecretsInDiffRule` | class | Rule class with `run(ctx: RuleContext) -> list[RuleResult]` |
| `SecretsInDiffRule.id` | attr | `"secrets-in-diff"` |
| `SecretsInDiffRule.description` | attr | `str` |
| `SecretsInDiffRule.default_severity` | attr | `RuleSeverity.CRITICAL` |
| `SecretsInDiffRule.run` | method | `(ctx: RuleContext) -> list[RuleResult]` |
| `SecretsInDiffRule._redact` | staticmethod | `(value: str) -> str` |

### Module-Level Helpers (private)

| Symbol | Signature |
|--------|-----------|
| `_is_comment_line` | `(content: str) -> bool` |
| `_is_placeholder` | `(match_text: str) -> bool` |
| `_in_tests_dir` | `(path: str) -> bool` |
| `_SECRET_PATTERNS` | `list[tuple[str, re.Pattern, RuleSeverity]]` — 10 patterns |
| `_PLACEHOLDERS` | `frozenset[str]` — 15 placeholder values |

---

## Test Coverage Map

| Test File | Test Class | Test Count | Coverage Area |
|-----------|------------|:----------:|---------------|
| `test_grippy_rule_secrets.py` | `TestSecretsInDiff` | 14 | Pattern detection, filtering, redaction |

### Test Categories

| Category | Count | Tests |
|----------|:-----:|-------|
| Positive fixtures (pattern detection) | 8 | aws_key, github_classic_pat, github_fine_grained_pat, github_other_tokens, openai_key, private_key_header, generic_secret_assignment, env_file_addition |
| Negative fixtures (non-match) | 3 | comment_line_skipped, placeholder_skipped, placeholder_your_dash_skipped |
| Diff-line filtering | 2 | tests_directory_skipped, context_line_not_flagged |
| Output safety | 1 | evidence_is_redacted |

---

## Config Surface

| Name | Type | Source |
|------|------|--------|
| `_SECRET_PATTERNS` | `list[tuple]` | Hardcoded — 10 regex patterns, all CRITICAL |
| `_PLACEHOLDERS` | `frozenset` | Hardcoded — 15 placeholder strings |

No environment variables. No Settings classes.

---

## B6.5 Reclassification Checkpoint

security-rule checklist has 9 items (SR-01 through SR-09). Applicability assessment:

| Item | Applicable? | Notes |
|------|:-----------:|-------|
| SR-01 | Yes | Pattern detection coverage |
| SR-02 | Yes | ReDoS safety |
| SR-03 | Yes | Severity assignment |
| SR-04 | Yes | Added-line-only filtering |
| SR-05 | Yes | Finding evidence fields |
| SR-06 | Partial | Profile activation is engine-level, but rule should be testable in isolation |
| SR-07 | Yes | Secret redaction |
| SR-08 | Yes | Enrichment compatibility |
| SR-09 | Yes | Fixture matrix coverage |

8.5/9 items applicable (>50%). **Confirmed: security-rule is correct primary type.**
