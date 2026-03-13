<!-- SPDX-License-Identifier: MIT -->

# Audit Scorecard: rule-secrets

**Audit date:** 2026-03-13
**Commit:** 259d0b8
**Auditor:** Claude Opus 4.6 (AI draft) / Nelson Spence (human reviewer -- pending)
**Unit type:** security-rule (primary)
**Subprofile:** N/A

---

## Gate Rules

### Override Gates (force a specific status)

| Override Gate | Condition | Fired? |
|---|---|---|
| Critical finding | Any unresolved CRITICAL finding | No |
| Multi-HIGH block | 2+ unresolved HIGH findings (including provisional) | No (0 HIGH findings) |
| Security collapse | Security Posture < 2 | No (score: 7) |
| Adversarial collapse | Adversarial Resilience < 2 | No (score: 5) |

### Ceiling Gates (cap the best allowed status)

| Ceiling Gate | Condition | Fired? |
|---|---|---|
| Severity cap | Any unresolved HIGH finding | No (F-RS-001 downgraded to MEDIUM during adjudication) |
| Security hard floor | Security Posture < 4 | No (score: 7) |
| Adversarial hard floor | Adversarial Resilience < 4 | No (score: 5) |
| Security soft floor | Security Posture < 6 | No (score: 7) |
| Adversarial soft floor | Adversarial Resilience < 6 | **Yes** (score: 5) — ceiling: Adequate |
| Accepted critical risk | Any ACCEPTED_RISK at CRITICAL | No |
| Accepted high risk | Any ACCEPTED_RISK at HIGH | No |

---

## Summary

| Dimension | Score | Evidence Tier | Notes |
|-----------|------:|:---:|-------|
| 1. Contract Fidelity | 7/10 | A | All functions typed, mypy clean, RuleResult/RuleContext used correctly |
| 2. Robustness | 6/10 | C | Pure function — no error handling needed. No bounds on result count. |
| 3. Security Posture | 7/10 | A + C | Redaction prevents leakage (test-proven). Comment/placeholder/tests-dir filtering. No trust boundaries owned. |
| 4. Adversarial Resilience | 5/10 | C | Placeholder filtering, redaction. No adversarial test fixtures. No ReDoS tests (F-RS-001). |
| 5. Auditability & Traceability | 6/10 | C | Findings include rule_id/file/line/evidence. No logging (appropriate for rule). |
| 6. Test Quality | 6/10 | A + C | 14 tests, positive+negative coverage. Missing adversarial/edge-case categories (F-RS-002). |
| 7. Convention Adherence | 9/10 | A | ruff, mypy strict, bandit clean. SPDX header. Calibration: matches schema (9). |
| 8. Documentation Accuracy | 7/10 | C | All functions have docstrings. Class docstring accurate. Placeholder list undocumented but self-describing. |
| 9. Performance | 8/10 | C | Compiled regexes, linear scan, early breaks. Efficient for workload. |
| 10. Dead Code / Debt | 9/10 | A + C | Zero TODOs, all functions called, clean imports. |
| 11. Dependency Hygiene | 9/10 | A | 2 internal deps (rules.base, rules.context) — same phase. No circular deps. |
| **Overall** | **7.2/10** | | **Average of 11 dimensions** |

**Health status:** Adequate (provisional)

**Determination:**
1. Average-based status: 7.2/10 → Adequate (6.0-7.9 range)
2. Override gates: None fired.
3. Ceiling gates: Adversarial soft floor fired (dim 4 = 5 < 6) → ceiling: Adequate. Severity cap no longer fires (F-RS-001 downgraded to MEDIUM during adjudication).
4. Base (Adequate) = ceiling (Adequate) → no change.
5. Suffixes: `(provisional)` — Adversarial Resilience (dim 4) supported only by Tier C evidence.

**Override gates fired:** None
**Ceiling gates fired:** Adversarial soft floor (dim 4 = 5)

---

## Dimension Details

### 1. Contract Fidelity

**Key question:** Do types, exports, and validation faithfully represent the unit's contract?

**Score:** 7/10
**Evidence:**
- mypy strict passes with zero issues (Tier A: static analysis).
- All functions fully typed: `run(ctx: RuleContext) -> list[RuleResult]`, `_redact(value: str) -> str`, helpers return `bool` (Tier A: mypy proves this).
- `_SECRET_PATTERNS` is a typed list of `tuple[str, re.Pattern[str], RuleSeverity]` (Tier A: mypy).
- Rule follows the duck-typed Rule protocol: exposes `id`, `description`, `default_severity`, `run()`. Compatible with `RULE_REGISTRY` and `RuleEngine` expectations.
- Not 9: No explicit `Protocol` class defining the Rule interface. No runtime type checks beyond type annotations.

---

### 2. Robustness

**Key question:** Does the unit handle errors, retries, and edge cases correctly?

**Score:** 6/10
**Evidence:**
- Pure function design: `run()` takes context, returns findings list. No exceptions raised, no error states. If no patterns match, returns empty list — a valid success state, not a sentinel (Tier C: code reading).
- No bounds on output: if a diff has 10,000 added lines each matching a pattern, 10,000 findings are returned. The engine/pipeline must handle this. Minor concern for extreme inputs.
- `break` at line 129 limits to one finding per line, providing some output bounding.
- No retries, timeouts, or resource management needed — appropriate for a stateless pattern scanner.
- Not 7: Rubric criteria for 7+ (retry, timeout, resource cleanup) are structurally inapplicable.

---

### 3. Security Posture

**Key question:** Does the unit protect against injection, leakage, and unauthorized access?

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 7/10
**Evidence:**
- `_redact()` (line 133-138) ensures raw secrets never appear in findings (Tier A: `test_evidence_is_redacted` at test line 110-116).
- `_is_comment_line()` suppresses comment-embedded patterns (Tier A: `test_comment_line_skipped` at test line 77-80).
- `_is_placeholder()` suppresses known placeholder values (Tier A: `test_placeholder_skipped`, `test_placeholder_your_dash_skipped` at test lines 82-89).
- `_in_tests_dir()` suppresses test directory patterns (Tier A: `test_tests_directory_skipped` at test line 91-95).
- No I/O, no network, no logging of sensitive data (Tier C: module-level inspection).
- Not 9: Does not own trust boundaries. Defense is focused on output safety (redaction) not input sanitization.

---

### 4. Adversarial Resilience

**Key question:** Can the unit resist adversarial input from untrusted PR content and prompt injection?

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 5/10
**Evidence:**
- Placeholder filtering blocks 15 known non-secret values from triggering findings (Tier A: 2 tests).
- Redaction prevents secret leakage through findings (Tier A: 1 test).
- No adversarial test fixtures: no long-input tests, no Unicode tests, no nested pattern tests (F-RS-001, F-RS-002).
- Manual regex analysis indicates patterns are structurally safe from ReDoS (Tier C: see F-RS-001), but no Tier A evidence exists.
- Limited adversarial exposure: rule processes parsed diff lines (already structured data), not raw user input. The attack surface is constrained to: (1) ReDoS via crafted line content, (2) false positive/negative manipulation.
- Not 7: No adversarial test suite. No multi-layer defense (rule has one detection layer with one output safety layer).

---

### 5. Auditability & Traceability

**Key question:** Can operators investigate failures, reproduce review results, and trace the decision path from input to output?

**Score:** 6/10
**Evidence:**
- Each `RuleResult` includes `rule_id`, `severity`, `message`, `file`, `line`, `evidence` — sufficient for human triage (Tier C: code inspection at lines 96-128).
- Pattern names in `_SECRET_PATTERNS` tuples appear in finding messages (e.g., "AWS access key detected in diff") — traceable to specific detection logic.
- No logging within the module (Tier C: appropriate for a rule — logging is engine-level).
- Deterministic: same diff input → same findings output. Fully reproducible.
- Not 7: No structured error context (no errors to contextualize). No trace correlation IDs.

---

### 6. Test Quality

**Key question:** Do tests verify meaningful behavior with good coverage?

**Score:** 6/10
**Evidence:**
- 14 tests across 1 test class (Tier A: `test_grippy_rule_secrets.py`).
- Test:source ratio: 0.84:1 (116 LOC tests / 138 LOC source). Below schema's 1.69:1 ratio.
- **Positive tests:** 8 tests covering all 10 pattern categories (GitHub other tokens covers 4 in one parametrized loop).
- **Negative tests:** 3 tests (comment skipped, 2 placeholder variants).
- **Diff filtering tests:** 2 tests (tests directory, context line).
- **Output safety:** 1 test (redaction).
- Missing categories (F-RS-002): adversarial input, renamed/binary/submodule diffs.
- Missing SR-02 evidence: no ReDoS tests (F-RS-001).
- Calibration: schema scored 8 with 44 tests, 1.69:1 ratio, boundary value testing. rule-secrets scores lower due to thinner fixture matrix.

---

### 7. Convention Adherence

**Key question:** Does the unit follow Grippy project patterns?

**Score:** 9/10
**Evidence:**
- SPDX header present on both source and test file (Tier A: file inspection).
- ruff check passes with zero issues (Tier A: static analysis).
- mypy strict passes with zero issues (Tier A: static analysis).
- bandit passes with zero issues (Tier A: static analysis).
- Test file follows mirror structure: `src/grippy/rules/secrets_in_diff.py` → `tests/test_grippy_rule_secrets.py` (Tier A).
- Test file exceeds 50 LOC minimum (116 LOC) (Tier A).
- Naming consistent with project patterns: PascalCase for class, snake_case for functions, UPPER_CASE for module constants.
- Calibration: matches schema (9). Exemplary adherence.

---

### 8. Documentation Accuracy

**Key question:** Do docstrings, comments, and docs match actual behavior?

**Score:** 7/10
**Evidence:**
- File-level docstring: "Rule 2: secrets-in-diff — detect known secret formats, private keys, and .env files." (line 2) — accurate (Tier C).
- Class docstring: "Detect known secret formats, private keys, and .env file additions." (line 78) — accurate (Tier C).
- All 4 helper functions have docstrings: `_is_comment_line`, `_is_placeholder`, `_in_tests_dir`, `_redact` (Tier C).
- `_SECRET_PATTERNS` has inline comment "Known API key / secret patterns" (line 11) — accurate.
- `_PLACEHOLDERS` has inline comment "Known placeholder values that should not trigger findings" (line 39) — accurate.
- Not 9: No usage examples. No documented invariants. Individual pattern rationale not documented (why these specific regex patterns were chosen).

---

### 9. Performance

**Key question:** Is the unit efficient for its workload?

**Score:** 8/10
**Evidence:**
- Regex patterns compiled once at module load via `re.compile()` (Tier C: line 12-37). No per-invocation recompilation.
- Linear scan: O(files × hunks × lines × patterns). Each line tested against 10 patterns with early break on first match (line 129).
- Early exits: test directory files skipped entirely (line 88-89). Non-add lines skipped (line 112). Comment lines skipped (line 114).
- Placeholder check is O(placeholders) per match but `_PLACEHOLDERS` is a small frozenset (15 items) — negligible.
- Not 9: No profiling data. "Efficient for workload" by structural argument, not measurement.

---

### 10. Dead Code / Debt

**Key question:** Is the unit free of unused code and tracked debt?

**Score:** 9/10
**Evidence:**
- Zero `TODO` or `FIXME` comments (Tier A: grep search).
- All functions called: `SecretsInDiffRule` registered in `RULE_REGISTRY` (registry.py:13, :20), `_is_comment_line` called at line 114, `_is_placeholder` at line 118, `_in_tests_dir` at line 88, `_redact` at line 126 (Tier C: caller trace).
- ruff detects no unused imports (Tier A: static analysis).
- No orphaned patterns in `_SECRET_PATTERNS` — all 10 tested.
- Not 10: F-RS-003 identifies a minor design limitation in `_is_comment_line` that could be considered implicit debt.

---

### 11. Dependency Hygiene

**Key question:** Are unit boundaries clean with no circular or unnecessary deps?

**Score:** 9/10
**Evidence:**
- 2 internal dependencies: `grippy.rules.base` (RuleResult, RuleSeverity) and `grippy.rules.context` (RuleContext). Both are same-phase (Phase 1) sibling modules (Tier A: import inspection at lines 8-9).
- 1 external dependency: `re` (stdlib) (Tier A: import inspection at line 6).
- No circular imports (Tier A: ruff check).
- Depends only on the rule framework types it must use — minimal coupling.
- Not 10: Has 2 internal dependencies (vs schema's zero). Dependencies are necessary and clean but not zero.
