<!-- SPDX-License-Identifier: MIT -->

# Audit Scorecard: schema

**Audit date:** 2026-03-13
**Commit:** cebbcab
**Auditor:** Claude Opus 4.6 (AI draft) / Nelson Spence (human reviewer -- pending)
**Unit type:** data-model (primary)
**Subprofile:** N/A

---

## Gate Rules

These rules override average-based health status. See METHODOLOGY.md Section C for severity definitions and Section D for evidence tier requirements.

### Override Gates (force a specific status)

| Override Gate | Condition | Fired? |
|---|---|---|
| Critical finding | Any unresolved CRITICAL finding | No |
| Multi-HIGH block | 2+ unresolved HIGH findings (including provisional) | No |
| Security collapse | Security Posture < 2 | No (score: 7) |
| Adversarial collapse | Adversarial Resilience < 2 | No (score: 6) |

### Ceiling Gates (cap the best allowed status)

| Ceiling Gate | Condition | Fired? |
|---|---|---|
| Severity cap | Any unresolved HIGH finding | No |
| Security hard floor | Security Posture < 4 | No (score: 7) |
| Adversarial hard floor | Adversarial Resilience < 4 | No (score: 6) |
| Security soft floor | Security Posture < 6 | No (score: 7) |
| Adversarial soft floor | Adversarial Resilience < 6 | No (score: 6) |
| Accepted critical risk | Any ACCEPTED_RISK at CRITICAL | No |
| Accepted high risk | Any ACCEPTED_RISK at HIGH | No |

---

## Summary

| Dimension | Score | Evidence Tier | Notes |
|-----------|------:|:---:|-------|
| 1. Contract Fidelity | 8/10 | A | Strict mypy, pydantic validation, field_validator |
| 2. Robustness | 7/10 | C | Pure data models; validator is only error path |
| 3. Security Posture | 7/10 | A + C | _sanitize_file_path proactive defense; no trust boundaries owned |
| 4. Adversarial Resilience | 6/10 | A + C | max_length + sanitizer limit injection surface; limited exposure as data model |
| 5. Auditability & Traceability | 6/10 | C | Clean structure, Field descriptions; no logging (appropriate for data models) |
| 6. Test Quality | 8/10 | A | 44 tests, boundary testing, parametrized, round-trip |
| 7. Convention Adherence | 9/10 | A | ruff clean, mypy strict, SPDX header, exemplary |
| 8. Documentation Accuracy | 7/10 | C | File-level docstring, Field descriptions; frozen asymmetry undocumented |
| 9. Performance | 8/10 | C | Pure data models, no algorithms, no I/O; optimal for workload |
| 10. Dead Code / Debt | 9/10 | A + C | No dead code, no TODOs, no orphans, all functions called |
| 11. Dependency Hygiene | 10/10 | A | Zero internal deps, minimal external (enum, typing, pydantic) |
| **Overall** | **7.7/10** | | **Average of 11 dimensions** |

**Health status:** Adequate (provisional)

**Determination:**
1. Average-based status: 7.7/10 falls in 6.0-7.9 range = **Adequate**
2. Override gates: None fired.
3. Ceiling gates: None fired. Average stands.
4. Suffixes: `(provisional)` — Dimensions 2, 5, 8, 9 are supported only by Tier C evidence. Per template rule: "any dimension with Tier C only" triggers the provisional suffix. Gate dimensions (3, 4) have Tier A support, so the provisional suffix does not indicate gate-level uncertainty.

**Override gates fired:** None
**Ceiling gates fired:** None

---

## Dimension Details

### 1. Contract Fidelity

**Key question:** Do types, exports, and validation faithfully represent the unit's contract?

| Level | Criteria |
|------:|----------|
| **3** | Some public functions lack type annotations. No input validation on public API. |
| **5** | All public functions typed. Pydantic models used for external-facing data. Some internal functions untyped. |
| **7** | All functions typed. Pydantic validation on inputs. Return types explicit. |
| **9** | Strict mypy passes with no ignores. Runtime type checks at boundaries. Protocol classes for DI. |

**Score:** 8/10
**Evidence:**
- mypy strict passes with zero issues (Tier A: static analysis output).
- All 11 BaseModel subclasses use typed fields with Pydantic validation (Tier A: mypy proves this).
- `field_validator` on `Finding.file` provides runtime sanitization at parse time (schema.py:104-108).
- Field constraints (`ge`, `le`, `max_length`) enforce domain invariants: confidence 0-100, title max 280, description max 2000, suggestion max 1000, evidence max 1000, grippy_note max 280, ScoreBreakdown fields 0-100 (Tier A: 18 tests at test_grippy_schema.py:154-209, :277-301).
- `frozen=True` on Finding prevents post-construction mutation (Tier A: test at test_grippy_schema.py:327-331).
- Not 9: No Protocol classes for DI (not applicable for a leaf data model). No runtime type checks beyond pydantic's built-in validation.

---

### 2. Robustness

**Key question:** Does the unit handle errors, retries, and edge cases correctly?

| Level | Criteria |
|------:|----------|
| **3** | Catch-all exception handlers. Some error paths return sentinel values. No retry logic. |
| **5** | Exceptions caught at appropriate granularity. Error paths distinguishable from success. Basic retry on transient failures. |
| **7** | Typed exceptions. Retry with backoff. Timeouts on external calls. Resources cleaned up in finally/context-manager. |
| **9** | Comprehensive error taxonomy. Graceful degradation under partial failure. No resource leaks under any code path. |

**Score:** 7/10
**Evidence:**
- As a pure data model module, robustness concerns are limited to validation behavior. There are no error handlers, retries, timeouts, or resource management -- none are needed.
- Pydantic's `ValidationError` is the only exception path. It is typed and carries structured field-level error details (Tier C: framework guarantee).
- `_sanitize_file_path` handles edge case input (newlines, backticks) without raising -- it sanitizes in place (Tier C: code reading at schema.py:106-108).
- Score reflects that the unit does exactly what a data model should: validate or raise. The rubric criteria for 7+ (retry, timeout, resource cleanup) are structurally inapplicable.

---

### 3. Security Posture

**Key question:** Does the unit protect against injection, leakage, and unauthorized access?

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

| Level | Criteria |
|------:|----------|
| **3** | Basic input validation exists but is incomplete. Some injection vectors unmitigated. Sensitive data may appear in logs. |
| **5** | All user-facing inputs validated. Known injection vectors mitigated. Secrets not hardcoded. Error messages don't leak internals. |
| **7** | Defense in depth on all trust boundaries this unit touches. Input sanitization covers known and novel attack classes. Security-relevant operations logged. |
| **9** | Defense in depth across all trust boundaries. Every input path from untrusted sources has independent sanitization. Comprehensive adversarial test coverage with fixture matrices for each attack class. |

**Score:** 7/10
**Evidence:**
- `_sanitize_file_path` (schema.py:104-108) provides proactive defense-in-depth: strips `\n`, `\r`, and backtick from file paths at parse time. This is a second line of defense -- primary sanitization occurs in agent.py (`_escape_xml`) and github_review.py (5-stage pipeline) (Tier C: code reading + caller trace).
- `max_length` constraints on all free-text fields (title: 280, description: 2000, suggestion: 1000, evidence: 1000, grippy_note: 280) limit the surface area for prompt injection payloads that survive into downstream consumers (Tier A: tests at test_grippy_schema.py:168-208).
- No secrets, no logging, no I/O, no error messages that could leak internals (Tier C: module-level code inspection).
- `frozen=True` on Finding prevents post-construction tampering (Tier A: test at test_grippy_schema.py:327-331).
- Not 9: schema.py does not own trust boundaries. It provides parse-time defense but the primary boundary logic lives elsewhere. No adversarial test suite within the schema test file (adversarial tests are in test_hostile_environment.py, which tests the consuming modules).

---

### 4. Adversarial Resilience

**Key question:** Can the unit resist adversarial input from untrusted PR content and prompt injection?

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

| Level | Criteria |
|------:|----------|
| **3** | Unit processes untrusted input but has minimal protection. Prompt injection or data injection plausible. |
| **5** | Data fencing separates instructions from untrusted content. Known injection patterns blocked. |
| **7** | Multi-layer defense: sanitization + data fencing + output validation. NL injection patterns neutralized. Tool output sanitization prevents context flooding. |
| **9** | Adversarial test suite covers all known attack vectors with fixture matrices. Novel attack classes considered. History poisoning mitigated. Cross-unit injection paths traced and defended. |

**Score:** 6/10
**Evidence:**
- `_sanitize_file_path` strips newlines and backticks (schema.py:106-108), which are common injection vectors in markdown rendering and code fence escaping (Tier C: code reading).
- `max_length` constraints bound the size of attacker-controlled content that can survive into structured output (Tier A: tests at test_grippy_schema.py:168-208).
- `frozen=True` on Finding prevents mutation of findings after construction, which could otherwise allow post-validation tampering (Tier A: test at test_grippy_schema.py:327-331).
- Limited exposure: schema.py is a data model, not a processing module. Adversarial input arrives via retry.py (which parses LLM JSON into these models) and the models' validation layer is one of several defenses in that path.
- Not 7+: No data fencing (that is agent.py's responsibility). No adversarial test fixtures in the schema test file. The defenses present are real but narrow -- `_sanitize_file_path` covers one field on one model.

---

### 5. Auditability & Traceability

**Key question:** Can operators investigate failures, reproduce review results, and trace the decision path from input to output?

| Level | Criteria |
|------:|----------|
| **3** | No structured logging. Errors produce generic messages. Cannot reproduce a review given the same inputs. |
| **5** | Errors logged with context. Diff and findings recoverable. Review can be approximately reproduced. |
| **7** | Structured error context on all failure paths. Review inputs (diff, rules, prompt chain) are reconstructable. Findings traceable to specific evidence. |
| **9** | Full decision trace: input diff -> rules fired -> prompt composed -> LLM response -> parsed findings -> posted comments. Forensic reconstruction possible. Correlation between findings and evidence is machine-verifiable. |

**Score:** 6/10
**Evidence:**
- Clean module structure with descriptive `Field(description=...)` annotations on most fields: `Finding.id` ("F-001 through F-999"), `PRMetadata.branch` ("source -> target"), `GrippyReview.timestamp` ("ISO-8601") (Tier C: code reading at schema.py:82, :97, :121, :186).
- File-level docstring accurately describes purpose (schema.py:2).
- Pydantic's `ValidationError` provides structured, field-level error context when validation fails (Tier C: framework property).
- No logging within the module -- appropriate for a data model, but means validation failures are only visible when a caller catches and logs the `ValidationError`.
- Not 7: No structured error context beyond what Pydantic provides by default. No trace correlation IDs.

---

### 6. Test Quality

**Key question:** Do tests verify meaningful behavior with good coverage?

| Level | Criteria |
|------:|----------|
| **3** | Few or no tests. Existing tests are smoke tests only. No adversarial inputs tested. |
| **5** | Positive and negative test cases. Core paths covered. Some edge cases. |
| **7** | Fixture matrices: positive, negative, adversarial, edge cases. Integration tests for cross-unit flows. Mocks used only at true boundaries. |
| **9** | Comprehensive fixture matrices for each public function. Property-based testing where applicable. Mutation testing or equivalent. No untested public paths. |

**Score:** 8/10
**Evidence:**
- 44 tests across 6 test classes (Tier A: test_grippy_schema.py).
- Test:source ratio of 1.69:1 (332 LOC tests / 196 LOC source).
- **Positive tests:** Enum value mapping (11 tests, :114-145), optional field acceptance (:217-243), round-trip serialization (:252-271), version default (:273-275), escalation inclusion (:303-318).
- **Negative tests:** Confidence below/above bounds (:154-160), max_length violations on 4 fields (:168-208), score overall boundary (:277-282), score breakdown rejects negative and >100 (parametrized x5 each, :284-301).
- **Boundary value tests:** Confidence at 0 and 100 (:162-166), fields at exact max_length (:173-176, :182-184, :190-192, :198-200, :206-208).
- **Frozen model test:** Mutation raises ValidationError (:327-331).
- **Round-trip test:** model_dump -> model_validate (:262-271).
- Helper functions `_minimal_finding()` and `_minimal_review()` provide clean fixture construction with override support (:26-105).
- Not 9: No property-based testing. No adversarial fixture matrix (though adversarial testing of schema consumers exists in test_hostile_environment.py). Minor gap: no test for missing required field rejection (F-SCH-002).

---

### 7. Convention Adherence

**Key question:** Does the unit follow Grippy project patterns?

| Level | Criteria |
|------:|----------|
| **3** | Inconsistent naming. Missing SPDX headers. Ignores project style. |
| **5** | Follows naming conventions. SPDX headers present. ruff-clean. |
| **7** | Follows all project patterns. Consistent with peer units. mypy strict compatible. |
| **9** | Exemplary adherence. Could serve as reference for new units. |

**Score:** 9/10
**Evidence:**
- SPDX header present on both source and test file: `# SPDX-License-Identifier: MIT` (Tier A: schema.py:1, test_grippy_schema.py:1).
- ruff check passes with zero issues (Tier A: static analysis).
- ruff format check passes (Tier A: static analysis).
- mypy strict passes with zero issues (Tier A: static analysis).
- bandit passes with one justified `# nosec B105` (Tier A: static analysis).
- Test file follows mirror structure convention: `src/grippy/schema.py` -> `tests/test_grippy_schema.py` (Tier A: file inspection).
- Test file exceeds 50 LOC minimum (332 LOC) (Tier A: line count).
- Naming conventions consistent: PascalCase for classes, snake_case for fields, UPPER_CASE for enum values.
- Could serve as a reference for new data model units.

---

### 8. Documentation Accuracy

**Key question:** Do docstrings, comments, and docs match actual behavior?

| Level | Criteria |
|------:|----------|
| **3** | Missing or misleading docstrings. Comments describe old behavior. |
| **5** | Public functions have docstrings. Major behaviors documented. Some drift. |
| **7** | All public functions documented accurately. Comments match code. No stale references. |
| **9** | Documentation is comprehensive, accurate, and includes usage examples. Invariants documented. |

**Score:** 7/10
**Evidence:**
- File-level docstring: "Pydantic models mapping Grippy's output-schema.md to typed Python objects." (schema.py:2) -- accurate (Tier C: code reading).
- `GrippyReview` class docstring: "Complete structured output from a Grippy review. Maps 1:1 to the JSON schema defined in output-schema.md." (schema.py:179-182) -- accurate (Tier C: code reading).
- `_sanitize_file_path` docstring: "Strip newlines and backticks from file paths." (schema.py:107) -- accurate (Tier C: code reading).
- `Field(description=...)` on key fields provides inline documentation for consumers and LLM prompt generation.
- Not 9: Frozen model asymmetry is undocumented (F-SCH-001). No usage examples. No documented invariants beyond what Field descriptions provide. Most models lack class-level docstrings.

---

### 9. Performance

**Key question:** Is the unit efficient for its workload?

| Level | Criteria |
|------:|----------|
| **3** | O(n^2) or worse where O(n) is possible. Unbounded resource consumption. |
| **5** | Reasonable algorithms. Resources bounded. No obvious bottlenecks. |
| **7** | Efficient algorithms. Lazy evaluation where appropriate. Bounded memory. |
| **9** | Optimal for workload. Profiled and validated. Streaming where applicable. |

**Score:** 8/10
**Evidence:**
- Pure data model definitions with no algorithms, loops, or I/O (Tier C: module-level code inspection).
- `_sanitize_file_path` performs three O(n) string replacements -- minimal overhead per Finding construction (Tier C: code reading at schema.py:108).
- Pydantic v2 model validation is compiled to Rust via pydantic-core, providing near-native validation performance (Tier C: framework property).
- Memory footprint is bounded by field constraints (max_length on all free-text fields) and by the number of findings/escalations (bounded by LLM output and retry.py).
- Not 9: No profiling data. "Optimal for workload" is assessed by structural argument, not measurement.

---

### 10. Dead Code / Debt

**Key question:** Is the unit free of unused code and tracked debt?

| Level | Criteria |
|------:|----------|
| **3** | Significant dead code. Untracked debt. Orphaned functions. |
| **5** | Minor dead code. Known debt tracked. No orphaned public functions. |
| **7** | No dead code. All debt tracked with priority. Clean imports. |
| **9** | Zero dead code. Zero untracked debt. Every function called. |

**Score:** 9/10
**Evidence:**
- Zero `TODO` or `FIXME` comments (Tier A: grep search).
- All 8 StrEnum classes and all 11 BaseModel subclasses are consumed by downstream modules: `__init__.py` re-exports, `agent.py` constructs, `retry.py` validates, `github_review.py` reads, `mcp_response.py` serializes (Tier C: caller trace).
- ruff detects no unused imports (Tier A: static analysis).
- Clean import block: 3 external imports only (enum, typing, pydantic) (Tier C: code reading at schema.py:4-9).
- Not 10: One minor undocumented design decision (frozen asymmetry, F-SCH-001) could be considered implicit debt.

---

### 11. Dependency Hygiene

**Key question:** Are unit boundaries clean with no circular or unnecessary deps?

| Level | Criteria |
|------:|----------|
| **3** | Circular imports. Unnecessary dependencies. Tight coupling. |
| **5** | No circular imports. Dependencies reasonable. Some unnecessary coupling. |
| **7** | Clean dependency graph. Depends only on lower phases. Minimal coupling. |
| **9** | Optimal dependency structure. Protocol-based decoupling. No leaky abstractions. |

**Score:** 10/10
**Evidence:**
- Zero internal dependencies: schema.py imports nothing from `grippy.*` (Tier A: static analysis via ruff, confirmed by manual inspection at schema.py:4-9).
- External dependencies are minimal and standard: `enum.StrEnum` (stdlib), `typing.Literal` (stdlib), `pydantic.BaseModel`, `pydantic.Field`, `pydantic.field_validator` (core project dependency).
- True leaf module in the dependency graph -- depended on by 5 modules, depends on nothing within the project.
- No leaky abstractions: all models expose only typed fields and standard Pydantic methods.
- This is the optimal dependency structure for a data model unit.
