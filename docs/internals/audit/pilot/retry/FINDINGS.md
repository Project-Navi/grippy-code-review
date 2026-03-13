<!-- SPDX-License-Identifier: MIT -->

# Audit Findings: retry

**Audit date:** 2026-03-13
**Commit:** 259d0b8
**Auditor:** Claude Opus 4.6 (AI draft) / Nelson Spence (human reviewer -- pending)
**Unit type:** review-pipeline (primary)
**Trust boundaries owned:** TB-5 (Model output boundary), TB-8 (Rule coverage validation)

---

## Strengths

1. **Excellent test:source ratio (2.61:1).** 529 LOC of tests covering 203 LOC of source. 35 tests across 7 test classes with positive, negative, edge case, adversarial sanitization, and integration categories.

2. **Clean static analysis trifecta.** ruff, mypy strict, and bandit all pass with zero issues on 163 lines of code.

3. **Defense-in-depth on retry messages.** `_safe_error_summary()` (retry.py:35-45) extracts only field paths and error type codes from `ValidationError`, never echoing raw values. This prevents attacker-controlled PR content from being re-injected into the LLM context via retry prompts. Three dedicated adversarial tests prove this property (`TestRetrySanitization`).

4. **Multi-format response parsing.** `_parse_response()` (retry.py:56-82) handles 5 input formats: `GrippyReview` instance (passthrough), `dict` (Pydantic validation), JSON string (parse + validate), markdown-fenced JSON (strip fences + parse), and reasoning model content. Robust against LLM output format variation. 9+ tests cover these paths.

5. **Rule coverage validation prevents hallucination and omission.** `_validate_rule_coverage()` (retry.py:85-106) cross-references LLM findings against deterministic rule engine results by both count and file set. Prevents the LLM from silently dropping known findings or fabricating findings that reference wrong files. 8 dedicated tests.

6. **Typed error hierarchy.** `ReviewParseError` (retry.py:21-32) carries structured context: `attempts`, `last_raw` (redacted in `__str__`), `errors` list. Error paths never produce values that look like success — they always raise.

7. **Model ID stamping.** `run_review()` overwrites the LLM-hallucinated `review.model` field with the actual model ID from the agent (retry.py:170-172). Prevents model attribution fabrication.

8. **Graceful degradation on rule coverage exhaustion.** When max retries are exhausted but rule coverage is still incomplete, `run_review()` issues a `warnings.warn()` and returns the partial review rather than crashing (retry.py:161-168). This prevents pipeline hangs on stubborn LLM output.

---

## Evidence Index

| Item ID | Description | Tier | Artifact | Assessment |
|---------|-------------|:----:|----------|------------|
| RP-01 | Error paths produce distinguishable states | A | `test_raises_after_max_retries`, `test_error_redacts_raw_output`, `test_error_contains_attempt_count`, `test_max_retries_zero_means_no_retry` | **PASS** |
| RP-02 | LLM text sanitized before external posting | C | retry does not sanitize content — delegates to github-review (TB-6). By design: retry owns structural validation (TB-5), not content sanitization. | **N/A (downstream)** |
| RP-03 | Rule coverage validation catches hallucinations | A + C | `TestRuleCoverageCounts` (4 tests), `TestRuleCoverageRetryLoop` (4 tests). Count validation proven. **File-set validation untested** (F-RY-001). | **PARTIAL** |
| RP-04 | Retry errors don't echo PR content to LLM | A | `test_safe_error_summary_omits_raw_values`, `test_retry_message_excludes_raw_validation_values`, `test_retry_message_excludes_json_decode_details` | **PASS** |
| RP-05 | Rules run on full diff, LLM sees truncated | C | Pipeline trace: review.py runs `run_rules()` at line 522 on full diff, then `truncate_diff()` at line 537 before passing to retry. retry receives truncated diff via `message` param. | **PASS (upstream)** |
| RP-06 | JSON parsing handles multiple formats | A | `test_parses_dict_response`, `test_parses_json_string_response`, `test_parses_model_instance_response`, `test_json_string_with_markdown_fences`, `test_retries_on_invalid_json`, `test_retries_on_invalid_schema`, `test_none_content_triggers_retry`, `test_empty_string_triggers_retry` | **PASS** |
| RP-07 | No duplicate comments on re-review | — | N/A — thread lifecycle managed by github-review unit, not retry. | **N/A** |
| RP-08 | CI exit codes correct per verdict | — | N/A — exit codes set by review.py, not retry. | **N/A** |
| RP-09 | Timeout enforced, clean exit | — | N/A — timeout enforcement is review.py's responsibility. retry has no timeout logic. | **N/A** |

---

## Findings

### F-RY-001: `expected_rule_files` validation path in TB-8 has zero test coverage

**Severity:** HIGH
**Status:** OPEN
**File:** `src/grippy/retry.py:102-105`, `tests/test_grippy_retry.py`
**Evidence tier:** A (confirmed by grep — zero matches for `expected_rule_files` in test file)

**Current behavior:**

```python
# retry.py:102-105
elif expected_rule_files and rule_id in expected_rule_files:
    finding_files = {f.file for f in matching}
    if not finding_files & expected_rule_files[rule_id]:
        missing.append(f"{rule_id} (findings don't reference flagged files)")
```

This code path validates that LLM-generated findings reference the same files as the deterministic rule engine. It prevents a sophisticated hallucination attack: the LLM produces the correct number of findings for a rule_id but attributes them to wrong files.

**Production usage confirmed:** `review.py:529` builds `expected_rule_files` from rule results and passes it to `run_review()` at line 628. This is a live code path.

**Test gap:** No test in `test_grippy_retry.py` passes `expected_rule_files` to `_validate_rule_coverage()` or `run_review()`. The entire file-set validation branch is exercised only in production, never in tests.

**Why it matters:** This is a TB-8 anchor function with a security-critical code path (anti-hallucination defense) that has no Tier A evidence. Per project quality standards: "Security paths require tests. No merge without test. Period."

**Suggested improvement:**

```python
def test_fabricated_file_detected(self) -> None:
    """Findings with correct rule_id but wrong files are caught."""
    review = self._review_with_findings(["secrets-in-diff"])
    # Finding references "src/app.py" but engine flagged "config.py"
    missing = _validate_rule_coverage(
        review,
        {"secrets-in-diff": 1},
        {"secrets-in-diff": frozenset({"config.py"})},
    )
    assert len(missing) == 1
    assert "flagged files" in missing[0]
```

~10 LOC. High priority — closes TB-8 gap.

---

### F-RY-002: `import warnings` is a lazy import inside function body

**Severity:** INFO
**Status:** OPEN
**File:** `src/grippy/retry.py:162`
**Evidence tier:** C (code inspection)

**Current behavior:**

```python
# retry.py:161-164
# Final attempt still missing — warn but return what we have
import warnings
warnings.warn(...)
```

`import warnings` is inside the function body rather than at module level. This is a common Python pattern for rarely-hit code paths to avoid import overhead, but it deviates from the project's convention of top-level imports.

**Why it matters:** Minor convention issue. ruff doesn't flag it (E402 only applies to top-level code, not function bodies). The import is for a stdlib module with negligible load cost.

**Suggested improvement:** Move `import warnings` to the top of the file. Low priority, cosmetic only.

---

## Compound Chain Exposure

### CH-1: Prompt Injection → Fabricated Finding → Merge Block

**Chain description:** An attacker crafts PR content with prompt injection that causes the LLM to fabricate findings (or drop legitimate ones), leading to an incorrect merge block or approval.

**retry's role:** RELAY at TB-5 (output parsing) and TB-8 (rule coverage validation).

#### TB-5 Controls (Model Output Boundary)

| Control | Function | Evidence | Assessment |
|---------|----------|----------|------------|
| Structural validation | `_parse_response()` | JSON parse + Pydantic `GrippyReview.model_validate()`. 9+ tests. | Catches structurally invalid fabrication (wrong schema). |
| Format normalization | `_strip_markdown_fences()` | Strips markdown code fences before JSON parse. 1 test. | Prevents markdown-wrapped injection. |
| Type dispatch | `_parse_response()` | Handles 5 content types deterministically. | No type-confusion attack possible. |

**TB-5 verdict:** Structurally sound. Cannot detect semantically valid fabricated findings — that is TB-8's responsibility.

#### TB-8 Controls (Rule Coverage Validation)

| Control | Function | Evidence | Assessment |
|---------|----------|----------|------------|
| Count validation | `_validate_rule_coverage()` | Cross-references finding counts per rule_id. 4 unit tests + 4 integration tests. | Catches dropped findings. |
| File-set validation | `_validate_rule_coverage()` | Cross-references finding files against engine-flagged files. **Zero tests** (F-RY-001). | Catches file-misattributed fabrication — but unproven. |
| Safe error feedback | `_safe_error_summary()` | Strips raw values from retry prompts. 3 adversarial tests. | Prevents PR content re-injection via error messages. |
| Error redaction | `ReviewParseError.__str__()` | Redacts raw output in string representation. 1 test. | Prevents leakage in logs. |

**TB-8 verdict:** Count validation is well-tested. File-set validation exists in code and production but lacks test evidence (F-RY-001). Safe error handling is proven.

#### Upstream Assumption (agent / TB-3)

Input reaching retry is structured model output from Agno's `Agent.run()`, not raw prompt text. retry does not compose the initial prompt — that is agent.py's responsibility (TB-1, TB-3). retry only composes correction messages, which use `_safe_error_summary()` (generic field paths only) or predefined template strings. The original `message` parameter is re-appended for context but was already sanitized by the caller.

**Assumption validity:** REASONABLE. retry's correction messages (retry.py:153-159, :191-196) use safe templates. The `message` parameter pass-through is a potential concern — if the caller passes unsanitized content, retry would relay it. However, the callers (review.py, mcp_server.py) sanitize before calling.

#### Downstream Assumption (github-review / TB-6)

retry returns a validated `GrippyReview` or raises `ReviewParseError`. Downstream consumers (github-review, mcp-response) are responsible for sanitizing finding text before posting to external APIs. retry does not sanitize finding content — it validates structure.

**Assumption validity:** CORRECT by architecture. retry owns structural validation (TB-5) and anti-hallucination checks (TB-8). Content sanitization is github-review's responsibility (TB-6, 5-stage pipeline).

#### Chain Verdict

retry **relays with partial mitigation**:
- **Breaks** the chain for structural fabrication (wrong JSON, wrong schema) via TB-5.
- **Breaks** the chain for finding omission (dropped rule findings) via TB-8 count validation.
- **Partially breaks** the chain for file-misattributed fabrication via TB-8 file-set validation — code exists but is unproven by tests (F-RY-001).
- **Relays** semantically valid fabricated findings (new finding types the rule engine didn't detect) — by design, as the LLM is expected to find issues beyond rule patterns.

**Cannot determine full chain safety** without downstream audit of github-review (TB-6) for content sanitization.

---

### CH-3: Tool Output Poisoning → Bad Review (Stub)

**retry's participation:** None. retry does not interact with codebase tools (`CodebaseToolkit`). Not on this chain's path. Tool output flows through agent.py (TB-4 `sanitize_tool_hook`), not retry.

**Verification needed in non-pilot audit:** Verify that tool output sanitization in agent.py prevents poisoned tool results from affecting the LLM's review, which would then flow through retry unchanged.

---

### CH-4: Schema Mismatch → Silent Failure (Stub)

**retry's participation:** Consumer. retry depends on `grippy.schema.GrippyReview` for Pydantic validation in `_parse_response()`. If schema.py changes field types or adds required fields, retry's parsing would fail with `ValidationError` — a loud failure, not a silent one. This is the correct behavior.

**Verification needed in non-pilot audit:** Verify that schema changes trigger re-testing of retry (CI coverage). Currently validated by the test suite importing `GrippyReview` directly.

---

### CH-5: History Poisoning → Persistent Compromise (Stub)

**retry's participation:** None. retry does not manage session history. The AF-07 fix sets `add_history_to_context=False` in agent.py's `Agent()` constructor, preventing prior LLM responses (which may contain attacker-controlled PR content) from being included in subsequent prompts.

**Partial mitigation note:** AF-07 is in agent.py, not retry. retry's correction messages do re-send the original `message` parameter, but this is the sanitized PR context, not prior LLM responses.

**Verification needed in non-pilot audit:** Confirm AF-07 is still in place in agent.py. Verify that retry's correction message pattern cannot be exploited for history-like accumulation.

---

## Hypotheses

None. All observations during this audit produced sufficient evidence for classification as findings or were resolved through code inspection.
