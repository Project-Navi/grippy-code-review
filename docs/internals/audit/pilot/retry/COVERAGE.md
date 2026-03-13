<!-- SPDX-License-Identifier: MIT -->

# Test Coverage: retry

**Audit date:** 2026-03-13
**Commit:** 259d0b8

---

## Test File Inventory

| Test File | Source File | Test Count | LOC (test) | LOC (source) | Ratio |
|-----------|------------|:----------:|:----------:|:------------:|:-----:|
| `tests/test_grippy_retry.py` | `src/grippy/retry.py` | 35 | 529 | 203 | 2.61:1 |

All 35 tests pass. Static analysis (ruff, mypy, bandit) clean on both files.

---

## Coverage Gaps

### Gap 1: `expected_rule_files` validation path untested (TB-8) — HIGH

**LOC at risk:** 4 lines (retry.py:102-105)
**Finding:** F-RY-001

The file-set validation branch of `_validate_rule_coverage()` is exercised in production (review.py:529 builds the dict, review.py:628 passes it to `run_review()`) but has zero test coverage. This is a TB-8 anchor function with a security-critical purpose: preventing hallucinated findings that reference wrong files.

**What is untested:**
- `expected_rule_files` parameter to `_validate_rule_coverage()` — never passed in any test
- `expected_rule_files` parameter to `run_review()` — never passed in any test
- The file intersection logic: `finding_files & expected_rule_files[rule_id]`
- The "findings don't reference flagged files" error message

**Remediation:** ~15 LOC (2-3 tests: file mismatch detection, file match acceptance, interaction with count validation).

### Gap 2: No adversarial parsing tests at TB-5 boundary — MEDIUM

**LOC at risk:** 27 lines (retry.py:56-82, `_parse_response()`)
**Finding:** Not filed (below threshold for standalone finding)

No test exercises `_parse_response()` with adversarial input designed to exploit the JSON parser or Pydantic validator. The existing `TestRetrySanitization` tests focus on retry message safety, not on the parsing boundary itself.

Examples of untested adversarial inputs:
- Extremely large JSON payload (>1MB)
- Deeply nested JSON (recursion depth)
- JSON with Unicode escape sequences that could bypass Pydantic validation
- Multiple JSON objects in one response

**Remediation:** ~20 LOC (3-4 adversarial parsing tests).

### Gap 3: No test for `_strip_markdown_fences` edge cases — LOW

**LOC at risk:** 5 lines (retry.py:48-53)
**Finding:** Not filed (low severity)

Only one test exercises markdown fence stripping (`test_json_string_with_markdown_fences`). No tests for:
- Nested fences (fence inside fence)
- Partial fences (opening without closing)
- Multiple fenced blocks (first wins?)
- Language tag variations (`\`\`\`JSON` vs `\`\`\`json` vs `\`\`\``)

**Remediation:** ~15 LOC (3-4 edge case tests).

---

## Per-Source Summary

| Source File | LOC | Functions | Tested Functions | Untested Paths | Gap Priority |
|-------------|:---:|:---------:|:----------------:|:--------------:|:------------|
| `retry.py` | 203 | 6 | 6 (all) | `expected_rule_files` branch in `_validate_rule_coverage` | HIGH (TB-8) |

All 6 functions/classes are exercised by existing tests. The gap is in parameter coverage: one parameter path of one function has zero test exercises despite being used in production.

---

## Function-Level Coverage Detail

| Function | Tests Exercising | Untested Paths |
|----------|:----------------:|----------------|
| `ReviewParseError.__init__` | 4 (exhaustion tests) | — |
| `_safe_error_summary` | 3 (sanitization tests) | — |
| `_strip_markdown_fences` | 1 (`test_json_string_with_markdown_fences`) | Edge cases (Gap 3) |
| `_parse_response` | 9+ (success + retry tests) | Adversarial inputs (Gap 2) |
| `_validate_rule_coverage` | 4 (count tests) | `expected_rule_files` param (Gap 1) |
| `run_review` | 20+ (all test classes) | `expected_rule_files` param pass-through (Gap 1) |

---

## Recommendations

| Priority | Gap | LOC Estimate | Checklist Item | Trust Boundary |
|:--------:|-----|:------------:|:--------------:|:--------------:|
| 1 | Add `expected_rule_files` validation tests | ~15 | RP-03 | TB-8 |
| 2 | Add adversarial parsing tests | ~20 | RP-06 | TB-5 |
| 3 | Add markdown fence edge case tests | ~15 | RP-06 | TB-5 |
| **Total** | | **~50 LOC** | | |
