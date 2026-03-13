<!-- SPDX-License-Identifier: MIT -->

# DRAFT — Audit Scorecard: retry

> **This scorecard is a DRAFT.** Final health status determination will be performed during Phase 2 adjudication (Task 14). Scores may be adjusted for cross-unit calibration.

**Audit date:** 2026-03-13
**Commit:** 259d0b8
**Auditor:** Claude Opus 4.6 (AI draft) / Nelson Spence (human reviewer -- pending)
**Unit type:** review-pipeline (primary)
**Subprofile:** N/A

---

## Gate Rules

### Override Gates (force a specific status)

| Override Gate | Condition | Fired? |
|---|---|---|
| Critical finding | Any unresolved CRITICAL finding | No |
| Multi-HIGH block | 2+ unresolved HIGH findings (including provisional) | No (1 HIGH: F-RY-001) |
| Security collapse | Security Posture < 2 | No (score: 8) |
| Adversarial collapse | Adversarial Resilience < 2 | No (score: 7) |

### Ceiling Gates (cap the best allowed status)

| Ceiling Gate | Condition | Fired? |
|---|---|---|
| Severity cap | Any unresolved HIGH finding | **Yes** (F-RY-001) — ceiling: Needs Attention |
| Security hard floor | Security Posture < 4 | No (score: 8) |
| Adversarial hard floor | Adversarial Resilience < 4 | No (score: 7) |
| Security soft floor | Security Posture < 6 | No (score: 8) |
| Adversarial soft floor | Adversarial Resilience < 6 | No (score: 7) |
| Accepted critical risk | Any ACCEPTED_RISK at CRITICAL | No |
| Accepted high risk | Any ACCEPTED_RISK at HIGH | No |

---

## Summary

| Dimension | Score | Evidence Tier | Notes |
|-----------|------:|:---:|-------|
| 1. Contract Fidelity | 8/10 | A | All functions typed, typed exceptions, explicit returns. Calibration: matches schema (8). |
| 2. Robustness | 8/10 | A | Typed exceptions, configurable retry, graceful degradation on exhaustion. |
| 3. Security Posture | 8/10 | A + C | TB-5 and TB-8 anchors. Safe error summary, redaction, anti-hallucination. Untested file-set path (F-RY-001). |
| 4. Adversarial Resilience | 7/10 | A | 3 adversarial sanitization tests. Safe error feedback prevents injection via retry. File-set gap (F-RY-001). |
| 5. Auditability & Traceability | 7/10 | C | ReviewParseError carries attempt+error context. Callback mechanism. No structured logging. |
| 6. Test Quality | 7/10 | A + C | 35 tests, 2.61:1 ratio. Strong coverage except file-set validation path. Calibration: below schema (8) due to TB-8 gap. |
| 7. Convention Adherence | 9/10 | A | ruff, mypy strict, bandit clean. SPDX header. Calibration: matches schema (9). |
| 8. Documentation Accuracy | 7/10 | C | Detailed docstrings on all public functions and security-critical privates. No usage examples. |
| 9. Performance | 8/10 | C | Retry bounded by max_retries. JSON parsing efficient. No unbounded loops. |
| 10. Dead Code / Debt | 9/10 | A + C | Zero TODOs, all functions called, clean imports. Minor: lazy `import warnings`. |
| 11. Dependency Hygiene | 9/10 | A | 1 internal dep (schema, Phase 0). Clean dependency graph. |
| **Overall** | **7.9/10** | | **Average of 11 dimensions** |

**Health status:** DRAFT — determination pending adjudication

**Preliminary assessment:**
1. Average-based status: 7.9/10 → Adequate (6.0-7.9 range). Note: 7.9 is at the boundary; adjudication may round up to Healthy depending on calibration.
2. Override gates: None fired.
3. Ceiling gates: Severity cap fired (F-RY-001 HIGH) → ceiling: Needs Attention.
4. Since base (Adequate) is better than strictest ceiling (Needs Attention): **downgrade to Needs Attention**.
5. Suffixes: None. Tier C evidence is supplementary to Tier A on all gate dimensions.

**Override gates fired:** None
**Ceiling gates fired:** Severity cap (F-RY-001 HIGH)

---

## Dimension Details

### 1. Contract Fidelity

**Key question:** Do types, exports, and validation faithfully represent the unit's contract?

**Score:** 8/10
**Evidence:**
- mypy strict passes with zero issues (Tier A: static analysis).
- All functions fully typed with explicit return types (Tier A: mypy proves this).
- `ReviewParseError` carries typed attributes: `attempts: int`, `last_raw: str`, `errors: list[str]` (Tier A: type inspection).
- `run_review()` has clear Optional parameter types with `| None` unions (Tier A: retry.py:113-116).
- `_parse_response()` return type is `GrippyReview` — raises on all failure paths, never returns None (Tier A: 9 success tests + 4 failure tests prove this).
- Not 9: No Protocol class for the `agent` parameter (uses `Any`). No runtime type check on the agent's `.run()` method.
- Calibration: matches schema (8). Same level of type discipline.

---

### 2. Robustness

**Key question:** Does the unit handle errors, retries, and edge cases correctly?

**Score:** 8/10
**Evidence:**
- Typed exception hierarchy: `ReviewParseError` with structured context (Tier A: 3 tests in `TestRunReviewExhausted`).
- Configurable retry with `max_retries` parameter (Tier A: `test_max_retries_zero_means_no_retry`, `test_default_max_retries_is_three`).
- Graceful degradation: rule coverage exhaustion returns partial review with warning rather than crashing (Tier A: `test_warns_on_exhausted_retries_with_missing_rules`).
- Error classification: distinct handling for `json.JSONDecodeError`, `ValidationError`, `ValueError`, `TypeError` (Tier C: code reading at retry.py:174-189).
- Reasoning model fallback: extracts content from `reasoning_content` when `content` is empty (Tier A: 3 tests in `TestRunReviewSuccess`).
- Not 9: No backoff strategy on retries (immediate retry). No resource cleanup (no resources to clean — pure function). No timeout (handled by caller).

---

### 3. Security Posture

**Key question:** Does the unit protect against injection, leakage, and unauthorized access?

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 8/10
**Evidence:**
- **TB-8 `_safe_error_summary()`** (retry.py:35-45): strips raw field values from `ValidationError`, returning only field paths and error type codes. Prevents attacker-controlled PR content from being injected into retry prompts (Tier A: `test_safe_error_summary_omits_raw_values`).
- **TB-8 `_validate_rule_coverage()`** (retry.py:85-106): cross-references LLM findings against deterministic rule results. Catches hallucinated and omitted findings. Count validation proven (Tier A: 4 tests). File-set validation code present but untested (F-RY-001) (Tier C).
- **`ReviewParseError.__str__()`** redacts raw LLM output (Tier A: `test_error_redacts_raw_output`).
- JSON decode error in retry message uses generic summary "JSON decode error", not raw content (Tier A: `test_retry_message_excludes_json_decode_details`).
- Model ID stamping prevents LLM model attribution fabrication (Tier A: `test_model_id_stamped_from_agent`).
- Not 9: File-set validation untested (F-RY-001). No comprehensive adversarial fixture matrix for the parsing boundary.

---

### 4. Adversarial Resilience

**Key question:** Can the unit resist adversarial input from untrusted PR content and prompt injection?

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 7/10
**Evidence:**
- 3 dedicated adversarial sanitization tests (`TestRetrySanitization`) prove that retry messages cannot be used to inject attacker-controlled content into the LLM context (Tier A).
- `_safe_error_summary()` implements data fencing: only field paths and type codes cross from untrusted data (PR content in validation errors) into retry prompts (Tier A: adversarial test with "IGNORE_ALL_RULES_AND_APPROVE" payload).
- Rule coverage validation catches LLM output manipulation: finding omission (Tier A: 4 tests) and file-set misattribution (code exists, Tier C: untested).
- Model ID stamping overrides LLM-hallucinated model field (Tier A: 1 test).
- Not 9: No fixture matrix for adversarial input at the parsing boundary. File-set validation untested. Semantically valid fabricated findings pass through by design (rule coverage only validates rule-engine-detected issues, not novel LLM findings).

---

### 5. Auditability & Traceability

**Key question:** Can operators investigate failures, reproduce review results, and trace the decision path from input to output?

**Score:** 7/10
**Evidence:**
- `ReviewParseError` carries full error chain: `attempts` count, `last_raw` (actual LLM output for debugging), `errors` list with per-attempt detail (Tier A: `test_error_contains_attempt_count`, `test_error_redacts_raw_output`).
- `on_validation_error` callback provides monitoring hook for each failure (Tier A: `TestRunReviewCallback`, 3 tests).
- `warnings.warn()` on rule coverage exhaustion provides runtime observability (Tier A: `test_warns_on_exhausted_retries_with_missing_rules`).
- Deterministic parsing: same agent output → same parsed result. Reproducible.
- Not 9: No structured logging. No correlation IDs linking retry attempts to specific PR reviews. Error chain is carried in exception attributes, not logged.

---

### 6. Test Quality

**Key question:** Do tests verify meaningful behavior with good coverage?

**Score:** 7/10
**Evidence:**
- 35 tests across 7 test classes (Tier A: `test_grippy_retry.py`).
- Test:source ratio: 2.61:1 (529 LOC tests / 203 LOC source). Highest ratio in the pilot.
- **Positive tests:** 9 success parsing tests covering dict, JSON, model instance, reasoning content, model ID stamp.
- **Negative/retry tests:** 4 retry tests (invalid JSON, invalid schema, error context, multi-retry). 4 exhaustion tests.
- **Edge case tests:** 4 tests (None content, empty string, markdown fences, default retry count).
- **Adversarial tests:** 3 tests (safe error summary, retry message sanitization, JSON decode safety).
- **Rule coverage tests:** 8 tests (4 unit, 4 integration).
- Gap: `expected_rule_files` path in `_validate_rule_coverage()` has zero test coverage (F-RY-001). This is a TB-8 anchor function with a live production code path.
- Calibration: schema scored 8 with 44 tests and 1.69:1 ratio. retry has fewer tests (35) but higher ratio (2.61:1). The TB-8 file-set gap is security-critical, which drops the score below schema. 7 is appropriate.

---

### 7. Convention Adherence

**Key question:** Does the unit follow Grippy project patterns?

**Score:** 9/10
**Evidence:**
- SPDX header present on both source and test file (Tier A: file inspection).
- ruff check passes with zero issues (Tier A: static analysis).
- mypy strict passes with zero issues (Tier A: static analysis).
- bandit passes with zero issues (Tier A: static analysis).
- Test file follows mirror structure: `src/grippy/retry.py` → `tests/test_grippy_retry.py` (Tier A).
- Test file exceeds 50 LOC minimum (529 LOC) (Tier A).
- Naming consistent: PascalCase for class, snake_case for functions, UPPER_CASE not used (no module constants).
- Calibration: matches schema (9).

---

### 8. Documentation Accuracy

**Key question:** Do docstrings, comments, and docs match actual behavior?

**Score:** 7/10
**Evidence:**
- File-level docstring: detailed architectural context — "Structured output retry wrapper for Grippy reviews. Parses agent output into GrippyReview, retrying with validation error feedback when the model produces malformed JSON or schema violations. Native json_schema path first — no Instructor dependency." (retry.py:2-6) — accurate (Tier C).
- `_safe_error_summary` docstring: "Extract only field paths and error type codes from a ValidationError. Never echoes raw values — prevents attacker-controlled PR content from being injected into retry prompts as untagged instructions." (retry.py:36-40) — accurate, includes security rationale (Tier C).
- `_parse_response` docstring: "Handles: GrippyReview instance, dict, JSON string, markdown-fenced JSON." (retry.py:58-60) — accurate (Tier C).
- `run_review` docstring with Args/Returns/Raises documentation (retry.py:119-131) — accurate (Tier C).
- `_validate_rule_coverage` docstring: explains count AND file-set validation purpose (retry.py:91-96) — accurate (Tier C).
- Not 9: No usage examples. `ReviewParseError` class lacks a docstring beyond the one-line description. No documented invariants.

---

### 9. Performance

**Key question:** Is the unit efficient for its workload?

**Score:** 8/10
**Evidence:**
- Retry loop bounded by `max_retries` (default 3, configurable). Maximum 4 total attempts — never unbounded (Tier A: `test_default_max_retries_is_three`).
- JSON parsing via stdlib `json.loads()` — O(n) in response size (Tier C: framework property).
- Pydantic validation via compiled Rust core (Tier C: framework property).
- `_strip_markdown_fences` uses single `re.search()` — efficient (Tier C: code reading).
- `_validate_rule_coverage` is O(rules × findings) — both are small (typically <20 rules, <50 findings) (Tier C: domain knowledge).
- Not 9: No profiling data. Regex in `_strip_markdown_fences` is compiled per-call (not pre-compiled). Minor optimization opportunity.

---

### 10. Dead Code / Debt

**Key question:** Is the unit free of unused code and tracked debt?

**Score:** 9/10
**Evidence:**
- Zero `TODO` or `FIXME` comments (Tier A: grep search).
- All functions called: `ReviewParseError` raised in `run_review`, `_safe_error_summary` called in error handler, `_strip_markdown_fences` called in `_parse_response`, `_parse_response` called in `run_review`, `_validate_rule_coverage` called in `run_review`, `run_review` called by 3 modules (Tier C: caller trace).
- ruff detects no unused imports (Tier A: static analysis).
- Minor: `import warnings` is a lazy import inside function body (F-RY-002). Cosmetic only.
- Not 10: F-RY-002 is a minor convention deviation.

---

### 11. Dependency Hygiene

**Key question:** Are unit boundaries clean with no circular or unnecessary deps?

**Score:** 9/10
**Evidence:**
- 1 internal dependency: `grippy.schema` (Phase 0 — lower phase) (Tier A: import inspection at line 18).
- External dependencies are minimal and standard: `json`, `re` (stdlib), `collections.abc.Callable`, `typing.Any` (stdlib), `pydantic.ValidationError` (core project dependency) (Tier A: import inspection at lines 11-16).
- No circular imports (Tier A: ruff check).
- Clean dependency direction: Phase 3 → Phase 0. No upward or lateral dependencies.
- Not 10: Has 1 internal dependency (vs schema's zero). Dependency is necessary and clean.
