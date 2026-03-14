# Audit Scorecard Template — Grippy

**Usage:** Copy to `docs/internals/audit/{unit_id}/SCORECARD.md` and fill during Phase D.

---

## Scorecard: `{unit_id}`

**Audit date:** {YYYY-MM-DD}
**Commit:** {short hash}
**Auditor:** {name}
**Unit type:** {type_primary} (primary){, type_secondary (secondary)}
**Subprofile:** {subprofile_primary | N/A}

---

## Gate Rules

These rules override average-based health status. See METHODOLOGY.md Section C for severity definitions and Section D for evidence tier requirements.

### Override Gates (force a specific status)

| Override Gate | Condition | Forced Status |
|---|---|---|
| Critical finding | Any unresolved CRITICAL finding | Critical |
| Multi-HIGH block | 2+ unresolved HIGH findings (including provisional) | Critical |
| Security collapse | Security Posture < 2 | Critical |
| Adversarial collapse | Adversarial Resilience < 2 | Critical |

### Ceiling Gates (cap the best allowed status)

| Ceiling Gate | Condition | Max Allowed |
|---|---|---|
| Severity cap | Any unresolved HIGH finding | Needs Attention |
| Security hard floor | Security Posture < 4 | Needs Attention |
| Adversarial hard floor | Adversarial Resilience < 4 | Needs Attention |
| Security soft floor | Security Posture < 6 | Adequate |
| Adversarial soft floor | Adversarial Resilience < 6 | Adequate |
| Accepted critical risk | Any ACCEPTED_RISK at CRITICAL | Needs Attention |
| Accepted high risk | Any ACCEPTED_RISK at HIGH | Adequate |

### Determination Algorithm

1. **Compute average-based status** from dimension scores (8.0+ Healthy, 6.0-7.9 Adequate, 4.0-5.9 Needs Attention, <4.0 Critical).
2. **Evaluate all override gates.** If any fire, base status = worst override. If override is worse than average, override wins.
3. **Evaluate all ceiling gates.** Strictest (lowest) ceiling applies. If base status is better than ceiling, downgrade to ceiling. Ceilings never rescue -- they only restrict upward. **Tiebreak:** If an override gate has already forced the status to Critical, no ceiling gate can soften that result. Ceilings only cap upward movement from the average; they do not override a forced-downward result.
4. **Append suffixes independently:**
   - `(accepted risk)` if any ACCEPTED_RISK at HIGH or CRITICAL
   - `(provisional)` if **Security Posture (Dim 3)** or **Adversarial Resilience (Dim 4)** is supported exclusively by Tier C evidence. This is an **evidence-maturity signal** scoped to the two gate dimensions — non-security dimensions using Tier C evidence do not trigger the suffix. The suffix drops when Dims 3 and 4 each have at least one Tier A or B evidence source. **Retroactive policy (v1.2):** This redefinition applies prospectively only. Existing CURRENT units retain their v1.1 suffixes until next scheduled re-audit (triggered by STALE or BOUNDARY_CHANGED status).

---

## Summary

| Dimension | Score | Evidence Tier | Notes |
|-----------|------:|:---:|-------|
| 1. Contract Fidelity | /10 | | |
| 2. Robustness | /10 | | |
| 3. Security Posture | /10 | | |
| 4. Adversarial Resilience | /10 | | |
| 5. Auditability & Traceability | /10 | | |
| 6. Test Quality | /10 | | |
| 7. Convention Adherence | /10 | | |
| 8. Documentation Accuracy | /10 | | |
| 9. Performance | /10 | | |
| 10. Dead Code / Debt | /10 | | |
| 11. Dependency Hygiene | /10 | | |
| **Overall** | **/10** | | **Average** |

**Health status:** {Healthy | Adequate | Needs Attention | Critical} {(accepted risk)} {(provisional)}

**Override gates fired:** {none | list}
**Ceiling gates fired:** {none | list}

---

## Dimension Details

**Score anchoring:** When a dimension score matches a previously audited unit's score for the same dimension, add a calibration note for cross-unit scoring consistency.

### 1. Contract Fidelity

**Key question:** Do types, exports, and validation faithfully represent the unit's contract?

| Level | Criteria |
|------:|----------|
| **3** | Some public functions lack type annotations. No input validation on public API. |
| **5** | All public functions typed. Pydantic models used for external-facing data. Some internal functions untyped. |
| **7** | All functions typed. Pydantic validation on inputs. Return types explicit. |
| **9** | Strict mypy passes with no ignores. Runtime type checks at boundaries. Protocol classes for DI. |

**Score:** /10
**Evidence:**

---

### 2. Robustness

**Key question:** Does the unit handle errors, retries, and edge cases correctly?

| Level | Criteria |
|------:|----------|
| **3** | Catch-all exception handlers. Some error paths return sentinel values. No retry logic. |
| **5** | Exceptions caught at appropriate granularity. Error paths distinguishable from success. Basic retry on transient failures. |
| **7** | Typed exceptions. Retry with backoff. Timeouts on external calls. Resources cleaned up in finally/context-manager. |
| **9** | Comprehensive error taxonomy. Graceful degradation under partial failure. No resource leaks under any code path. |

**Score:** /10
**Evidence:**

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

**Score:** /10
**Evidence:**

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

**Score:** /10
**Evidence:**

---

### 5. Auditability & Traceability

**Key question:** Can operators investigate failures, reproduce review results, and trace the decision path from input to output?

| Level | Criteria |
|------:|----------|
| **3** | No structured logging. Errors produce generic messages. Cannot reproduce a review given the same inputs. |
| **5** | Errors logged with context. Diff and findings recoverable. Review can be approximately reproduced. |
| **7** | Structured error context on all failure paths. Review inputs (diff, rules, prompt chain) are reconstructable. Findings traceable to specific evidence. |
| **9** | Full decision trace: input diff -> rules fired -> prompt composed -> LLM response -> parsed findings -> posted comments. Forensic reconstruction possible. Correlation between findings and evidence is machine-verifiable. |

**Score:** /10
**Evidence:**

---

### 6. Test Quality

**Key question:** Do tests verify meaningful behavior with good coverage?

| Level | Criteria |
|------:|----------|
| **3** | Few or no tests. Existing tests are smoke tests only. No adversarial inputs tested. |
| **5** | Positive and negative test cases. Core paths covered. Some edge cases. |
| **7** | Fixture matrices: positive, negative, adversarial, edge cases. Integration tests for cross-unit flows. Mocks used only at true boundaries. |
| **9** | Comprehensive fixture matrices for each public function. Property-based testing where applicable. Mutation testing or equivalent. No untested public paths. |

**Score:** /10
**Evidence:**

---

### 7. Convention Adherence

**Key question:** Does the unit follow Grippy project patterns?

| Level | Criteria |
|------:|----------|
| **3** | Inconsistent naming. Missing SPDX headers. Ignores project style. |
| **5** | Follows naming conventions. SPDX headers present. ruff-clean. |
| **7** | Follows all project patterns. Consistent with peer units. mypy strict compatible. |
| **9** | Exemplary adherence. Could serve as reference for new units. |

**Score:** /10
**Evidence:**

---

### 8. Documentation Accuracy

**Key question:** Do docstrings, comments, and docs match actual behavior?

| Level | Criteria |
|------:|----------|
| **3** | Missing or misleading docstrings. Comments describe old behavior. |
| **5** | Public functions have docstrings. Major behaviors documented. Some drift. |
| **7** | All public functions documented accurately. Comments match code. No stale references. |
| **9** | Documentation is comprehensive, accurate, and includes usage examples. Invariants documented. |

**Score:** /10
**Evidence:**

---

### 9. Performance

**Key question:** Is the unit efficient for its workload?

| Level | Criteria |
|------:|----------|
| **3** | O(n^2) or worse where O(n) is possible. Unbounded resource consumption. |
| **5** | Reasonable algorithms. Resources bounded. No obvious bottlenecks. |
| **7** | Efficient algorithms. Lazy evaluation where appropriate. Bounded memory. |
| **9** | Optimal for workload. Profiled and validated. Streaming where applicable. |

**Score:** /10
**Evidence:**

---

### 10. Dead Code / Debt

**Key question:** Is the unit free of unused code and tracked debt?

| Level | Criteria |
|------:|----------|
| **3** | Significant dead code. Untracked debt. Orphaned functions. |
| **5** | Minor dead code. Known debt tracked. No orphaned public functions. |
| **7** | No dead code. All debt tracked with priority. Clean imports. |
| **9** | Zero dead code. Zero untracked debt. Every function called. |

**Score:** /10
**Evidence:**

---

### 11. Dependency Hygiene

**Key question:** Are unit boundaries clean with no circular or unnecessary deps?

| Level | Criteria |
|------:|----------|
| **3** | Circular imports. Unnecessary dependencies. Tight coupling. |
| **5** | No circular imports. Dependencies reasonable. Some unnecessary coupling. |
| **7** | Clean dependency graph. Depends only on lower phases. Minimal coupling. |
| **9** | Optimal dependency structure. Protocol-based decoupling. No leaky abstractions. |

**Score:** /10
**Evidence:**
