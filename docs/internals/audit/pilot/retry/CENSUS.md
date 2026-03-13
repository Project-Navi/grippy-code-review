<!-- SPDX-License-Identifier: MIT -->

# Unit Census: retry

**Audit date:** 2026-03-13
**Commit:** 259d0b8
**Unit type:** review-pipeline (primary), no secondary
**Phase:** 3 (Orchestration)
**Trust boundaries:** TB-5 (Model output boundary), TB-8 (Rule coverage validation)

---

## File Inventory

| File | LOC | Role |
|------|----:|------|
| `src/grippy/retry.py` | 203 | Source |
| `tests/test_grippy_retry.py` | 529 | Test |
| **Total** | **732** | |

Test:source ratio: 2.61:1

---

## Dependency Graph

### Internal Dependencies (grippy.*)

| Import | Module | Phase |
|--------|--------|------:|
| `GrippyReview` | `grippy.schema` | 0 |

### External Dependencies

| Import | Package |
|--------|---------|
| `json` | stdlib |
| `re` | stdlib |
| `collections.abc.Callable` | stdlib |
| `typing.Any` | stdlib |
| `ValidationError` | `pydantic` |

### Dependents (who imports this unit)

| Module | Import | Phase |
|--------|--------|------:|
| `grippy.__init__` | `ReviewParseError`, `run_review` (re-export) | — |
| `grippy.mcp_server` | `ReviewParseError`, `run_review` | 4 |
| `grippy.review` | `ReviewParseError`, `run_review` | 4 |

---

## Public Surface

| Symbol | Type | Signature |
|--------|------|-----------|
| `ReviewParseError` | class (Exception) | `(attempts: int, last_raw: str, errors: list[str])` |
| `run_review` | function | `(agent, message, *, max_retries=3, on_validation_error=None, expected_rule_counts=None, expected_rule_files=None) -> GrippyReview` |

### Private Functions (security-critical — TB-5 and TB-8 anchors)

| Symbol | Boundary | Signature |
|--------|:--------:|-----------|
| `_safe_error_summary` | TB-8 | `(e: ValidationError) -> str` |
| `_strip_markdown_fences` | TB-5 | `(text: str) -> str` |
| `_parse_response` | TB-5 | `(content: Any) -> GrippyReview` |
| `_validate_rule_coverage` | TB-8 | `(review, expected_rule_counts, expected_rule_files=None) -> list[str]` |

---

## Test Coverage Map

| Test File | Test Class | Test Count | Coverage Area |
|-----------|------------|:----------:|---------------|
| `test_grippy_retry.py` | `TestRunReviewSuccess` | 9 | Successful parsing: dict, JSON, model instance, reasoning content, model ID stamp |
| | `TestRunReviewRetry` | 4 | Retry on invalid JSON, invalid schema, error context in retry message, multi-retry |
| | `TestRunReviewExhausted` | 4 | Max retries exceeded, error redaction, attempt count, zero-retry mode |
| | `TestRunReviewCallback` | 3 | Callback on error, callback args, no callback on success |
| | `TestRunReviewEdgeCases` | 4 | None content, empty string, markdown fences, default retry count |
| | `TestRetrySanitization` | 3 | Safe error summary, retry message excludes raw values, JSON decode error safe |
| | `TestRuleCoverageCounts` | 4 | Count validation: all met, missing count, completely missing, extra OK |
| | `TestRuleCoverageRetryLoop` | 4 | Integration: retry on missing rule_id, no retry when present, warns on exhaustion, count-not-just-presence |
| **Total** | | **35** | |

---

## Config Surface

No environment variables read directly. No Settings classes.

Configuration is received via function parameters:
- `max_retries` (default: 3)
- `expected_rule_counts` (optional dict)
- `expected_rule_files` (optional dict)

---

## B6.5 Reclassification Checkpoint

review-pipeline checklist has 9 items (RP-01 through RP-09). Applicability assessment:

| Item | Applicable? | Notes |
|------|:-----------:|-------|
| RP-01 | Yes | Error paths produce distinguishable states |
| RP-02 | Partial | Sanitization is downstream (github-review), but retry must not introduce unsanitized content |
| RP-03 | Yes | Core TB-8 function |
| RP-04 | Yes | Core TB-8 function |
| RP-05 | Partial | Pipeline ordering is review.py's concern; retry is a consumer |
| RP-06 | Yes | Core TB-5 function |
| RP-07 | No | Thread lifecycle is github-review scope |
| RP-08 | No | CI exit codes are review.py scope |
| RP-09 | No | Timeout enforcement is review.py scope |

6/9 items applicable (>50%). **Confirmed: review-pipeline is correct primary type.**

N/A items (RP-07, RP-08, RP-09) are responsibilities of other units in the pipeline (github-review, review).
