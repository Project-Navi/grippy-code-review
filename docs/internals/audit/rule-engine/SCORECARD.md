<!-- SPDX-License-Identifier: MIT -->

# Audit Scorecard: rule-engine

**Audit date:** 2026-03-13
**Commit:** aa19594
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
| Adversarial collapse | Adversarial Resilience < 2 | No (score: 7) |

### Ceiling Gates (cap the best allowed status)

| Ceiling Gate | Condition | Fired? |
|---|---|---|
| Severity cap | Any unresolved HIGH finding | No |
| Security hard floor | Security Posture < 4 | No (score: 7) |
| Adversarial hard floor | Adversarial Resilience < 4 | No (score: 7) |
| Security soft floor | Security Posture < 6 | No (score: 7) |
| Adversarial soft floor | Adversarial Resilience < 6 | No (score: 7) |
| Accepted critical risk | Any ACCEPTED_RISK at CRITICAL | No |
| Accepted high risk | Any ACCEPTED_RISK at HIGH | No |

---

## Summary

| Dimension | Score | Evidence Tier | Notes |
|-----------|------:|:---:|-------|
| 1. Contract Fidelity | 8/10 | A | All functions typed, mypy strict clean, Rule Protocol + RuleResult contract |
| 2. Robustness | 7/10 | A + C | Typed exceptions, fallback for malformed hunks, empty-input safe |
| 3. Security Posture | 7/10 | A + C | nogrip suppression, profile gating, no I/O. TB-2 anchor (RuleEngine.run) |
| 4. Adversarial Resilience | 7/10 | A | ReDoS tests on all 4 regexes, malformed diff recovery, 1MB line test |
| 5. Auditability & Traceability | 7/10 | C | RuleResult carries rule_id/file/line/evidence. Deterministic dispatch. |
| 6. Test Quality | 7/10 | A | 46 tests across 2 files. Positive, negative, adversarial, edge cases covered. |
| 7. Convention Adherence | 9/10 | A | ruff, mypy strict, bandit clean. SPDX headers. Mirror test structure. |
| 8. Documentation Accuracy | 7/10 | C | All public APIs docstringed. Regex patterns self-describing. |
| 9. Performance | 8/10 | C | Compiled regexes, linear scan, early breaks. O(files x hunks x lines). |
| 10. Dead Code / Debt | 9/10 | A + C | Zero TODOs, all functions called, clean imports. |
| 11. Dependency Hygiene | 8/10 | A | 3 internal deps (base, context, ignore). No circular deps. Phase 0 siblings. |
| **Overall** | **7.6/10** | | **Average of 11 dimensions** |

**Health status:** Adequate (provisional)

**Determination:**
1. Average-based status: 7.6/10 -> Adequate (6.0-7.9 range)
2. Override gates: None fired.
3. Ceiling gates: None fired. All gate dimensions >= 6.
4. Suffixes: `(provisional)` -- dims 2, 3, 5, 8, 9 include Tier C evidence components.

**Override gates fired:** None
**Ceiling gates fired:** None

---

## Checklist: SR-01 through SR-09

| ID | Verdict | Evidence | Notes |
|----|---------|----------|-------|
| SR-01 | N/A | Ownership | Engine dispatches rules; it does not detect patterns. Pattern detection is the responsibility of individual `rule-*` units. |
| SR-02 | PASS | Tier A: 3 ReDoS timeout tests (file header, hunk header, rename headers) in `test_grippy_rules_context.py` | All 4 compiled regexes are `^`-anchored with non-nested quantifiers. 100K-char adversarial inputs complete under 5s timeout guard. |
| SR-03 | PASS | Tier A: 5 gate tests in `test_grippy_rules_engine.py` (security, strict, general profiles + suppressed + unsuppressed) | `check_gate()` correctly compares severity IntEnum values against profile `fail_on` threshold. |
| SR-04 | N/A | Ownership | Individual rules enforce added-line-only detection. Engine dispatches all results from `rule.run()`. |
| SR-05 | PASS | Tier A + C: `RuleResult` dataclass (base.py:36-46) has rule_id, severity, message, file, line, evidence fields. Verified by `TestResultEnrichment` tests. | Sufficient for human triage. |
| SR-06 | PASS | Tier A: `test_run_rules_detects_known_pattern` + `test_check_gate_wrapper` verify engine-level profile activation. Engine owns profile dispatch via `RuleContext.config`. | General profile sets `fail_on=CRITICAL`, effectively disabling gate for lower severities. |
| SR-07 | N/A | Ownership | Finding message content is the responsibility of individual rule `run()` methods, not the engine. |
| SR-08 | PASS | Tier A: `test_check_gate_skips_suppressed` + `test_check_gate_still_fails_on_unsuppressed` verify enrichment.suppressed integration in gate logic. | `ResultEnrichment.suppressed` field correctly influences gate check. |
| SR-09 | PASS | Tier A: Test fixture matrix covers positive (rule detection), negative (clean diff, no findings), adversarial (ReDoS, malformed diff, 1MB line), edge cases (empty diff, empty rules, no-findings rule, nogrip pragma). | Missing categories: renamed/binary/submodule diffs for parse_diff -- already covered in existing `test_renamed_file` and `test_binary_file`. |

**N/A items:** 3/9 (SR-01, SR-04, SR-07). These are rule-level responsibilities, not engine-level. At 33%, well below the >50% reclassification threshold. The engine is correctly typed as security-rule -- it owns dispatch, gating, suppression, and diff parsing, not pattern detection.

---

## Findings

No findings. All checklist items either PASS with Tier A evidence or are N/A by ownership design.

### Compound Chain Exposure

This unit participates in **CH-4 (Rule Bypass -> Silent Vulnerability Pass)**.

- **Role:** Relay. The engine dispatches rules and gates results. If `parse_diff()` fails to parse a malformed diff, rules never fire, potentially allowing a vulnerability to pass undetected.
- **Circuit breaker:** `parse_diff()` handles malformed lines with a fallback (context.py:237-242) that re-processes unexpected lines as potential new file headers rather than silently dropping them. This is tested by `test_parse_diff_malformed_line_in_hunk` (Tier A).
- **Residual risk:** A diff format that no regex matches would produce zero `ChangedFile` objects, meaning zero rule findings. This is inherent to the architecture (rules scan parsed structures) and is not a vulnerability in the engine itself -- it's a limitation of any regex-based parser.

---

## Dimension Details

### 1. Contract Fidelity

**Key question:** Do types, exports, and validation faithfully represent the unit's contract?

**Score:** 8/10
**Evidence:**
- mypy strict passes with zero issues across all 6 source files (Tier A: static analysis).
- `Rule` Protocol (base.py:48-56) defines the contract: `id`, `description`, `default_severity`, `run()`. Runtime-checkable via `@runtime_checkable`.
- `RuleResult` frozen dataclass (base.py:35-46) with explicit types for all fields.
- `RuleEngine.run()` signature: `(ctx: RuleContext) -> list[RuleResult]` -- clear contract.
- `RuleEngine.check_gate()` signature: `(results: list[RuleResult], config: ProfileConfig) -> bool`.
- `RuleContext` dataclass (context.py:48-71) with typed `files`, `config`, helper `added_lines_for()`.
- `parse_diff()` signature: `(diff_text: str) -> list[ChangedFile]` -- pure function, no side effects.
- `ProfileConfig` frozen dataclass (config.py:12-14) with `name` and `fail_on` fields.
- Not 9: No runtime type checks at boundaries beyond Protocol. `parse_diff()` accepts any string without validation (appropriate -- empty/whitespace returns []).

---

### 2. Robustness

**Key question:** Does the unit handle errors, retries, and edge cases correctly?

**Score:** 7/10
**Evidence:**
- `parse_diff()` handles empty/whitespace input gracefully (returns []) (Tier A: `test_empty_diff`).
- Malformed line in hunk triggers fallback re-processing rather than crash (Tier A: `test_parse_diff_malformed_line_in_hunk`, context.py:237-242).
- >1MB lines parsed without crash (Tier A: `test_parse_diff_extremely_long_added_line`).
- `_flush_hunk()`/`_flush_file()` ensure partial state is collected even if parsing is interrupted by new headers.
- `RuleEngine.run()` with empty diff/files produces empty results (Tier A: `test_run_with_empty_diff`).
- `check_gate()` with empty results returns False (Tier A: `test_check_gate_empty_results`).
- `load_profile()` raises `ValueError` for unknown profile names with descriptive message (Tier A: implied by config.py:41).
- No retries or timeouts needed -- pure in-memory computation.
- Not 8: No bounds on output count from `parse_diff()` or `RuleEngine.run()`. A diff with millions of lines would produce correspondingly large structures. This is acceptable for the expected workload (diffs are bounded by GRIPPY_MAX_DIFF_CHARS upstream).

---

### 3. Security Posture

**Key question:** Does the unit protect against injection, leakage, and unauthorized access?

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 7/10
**Evidence:**
- **TB-2 anchor ownership:** `RuleEngine.run()` is a named anchor for TB-2 (diff/content ingestion). It receives parsed diff structures and dispatches rules.
- nogrip suppression (engine.py:27-38) prevents targeted or blanket rule suppression per-line. Both bare `# nogrip` and targeted `# nogrip: rule-id` are handled (Tier A: 5 nogrip tests).
- Profile gating: `check_gate()` enforces severity thresholds per profile. `general` profile effectively disables gating for non-CRITICAL findings (Tier A: gate tests).
- No I/O, no network, no subprocess calls in any of the 6 source files (Tier C: module inspection).
- No logging of sensitive data -- no logging at all (appropriate for rule engine).
- `_RULE_REGISTRY` is a static list of class references, not dynamic loading (Tier C: registry.py:18-29). No code injection vector.
- Not 9: Does not perform input sanitization (appropriate -- engine processes structured data from `parse_diff()`, not raw untrusted input).

---

### 4. Adversarial Resilience

**Key question:** Can the unit resist adversarial input from untrusted PR content and prompt injection?

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 7/10
**Evidence:**
- **ReDoS defense (Tier A):** 3 tests covering all 4 compiled regexes with 100K-char adversarial inputs. All complete under 5s timeout guard. Regexes are `^`-anchored with non-nested quantifiers -- structurally safe from catastrophic backtracking.
- **Malformed diff recovery (Tier A):** `test_parse_diff_malformed_line_in_hunk` proves the fallback path (context.py:237-242) recovers gracefully when unexpected content appears mid-hunk.
- **Large input tolerance (Tier A):** `test_parse_diff_extremely_long_added_line` proves >1MB lines are parsed without crash.
- **Empty input safety (Tier A):** Empty diff through full pipeline (all 10 rules) produces no findings.
- **Attack surface:** Engine processes parsed diff structures. Direct adversarial input from PR content reaches `parse_diff()` as raw diff text. The parser's only interpretation is line-by-line regex matching -- no eval, no deserialization, no dynamic imports.
- Calibration: rule-secrets scored 5/10 (no adversarial tests). rule-engine scores higher due to 6 adversarial/edge-case tests with Tier A evidence.
- Not 9: No property-based testing. No Unicode adversarial fixtures (though diff content is opaque to the parser -- it only interprets prefix characters `+`, `-`, ` `, `\`).

---

### 5. Auditability & Traceability

**Key question:** Can operators investigate failures, reproduce review results, and trace the decision path from input to output?

**Score:** 7/10
**Evidence:**
- `RuleResult` carries `rule_id`, `severity`, `message`, `file`, `line`, `evidence` -- sufficient for human triage (Tier C: base.py:36-46).
- `ResultEnrichment` adds `blast_radius`, `is_recurring`, `prior_count`, `suppressed`, `suppression_reason`, `velocity` -- rich context for downstream consumers (Tier C: base.py:24-33).
- `RuleEngine.run()` is deterministic: same diff + same rules = same results. Fully reproducible.
- `parse_diff()` is a pure function: same input string = same `ChangedFile` list.
- nogrip suppression is silent (no logging of suppressed findings). This is a minor traceability gap -- suppressed findings are simply not returned. However, the suppression mechanism is well-tested.
- Not 8: No structured logging. No trace correlation IDs. No "explain why this finding was/wasn't generated" capability.

---

### 6. Test Quality

**Key question:** Do tests verify meaningful behavior with good coverage?

**Score:** 7/10
**Evidence:**
- **Test count:** 46 tests across 2 files (`test_grippy_rules_context.py`: 17 tests, `test_grippy_rules_engine.py`: 29 tests).
- **Source:test ratio:** 458 LOC source / 725 LOC tests = 1.58:1 test-to-source ratio.
- **Fixture matrix categories covered:**
  - Positive: file parsing, hunk parsing, rename detection, rule dispatch, gate check (multiple profiles).
  - Negative: empty diff, no findings rule, unmatched glob.
  - Adversarial: ReDoS (3 tests), malformed diff, 1MB line.
  - Edge cases: empty rules, binary file, no-newline marker, nogrip pragma (5 tests), suppressed enrichment.
- **Coverage:** context.py and engine.py have high statement coverage. `parse_diff()` exercises all major code paths: file headers, metadata, hunk headers, add/remove/context lines, no-newline markers, binary files, renames, malformed fallback.
- Calibration: rule-secrets scored 6/10 (14 tests, no adversarial). rule-engine scores higher with broader fixture matrix and adversarial coverage.
- Not 8: No coverage measurement cited as Tier A evidence. No property-based testing.

---

### 7. Convention Adherence

**Key question:** Does the unit follow Grippy project patterns?

**Score:** 9/10
**Evidence:**
- SPDX header present on all 6 source files and both test files (Tier A: file inspection).
- ruff check passes with zero issues on all source files (Tier A: static analysis).
- mypy strict passes with zero issues (Tier A: static analysis).
- bandit passes with zero issues (Tier A: static analysis).
- Test files follow mirror structure convention (Tier A).
- Both test files exceed 50 LOC minimum (Tier A).
- Naming: PascalCase for classes (`RuleEngine`, `RuleResult`, `DiffLine`), snake_case for functions/methods, UPPER_CASE for constants (`RULE_REGISTRY`, `PROFILES`).
- Calibration: matches schema (9), rule-secrets (9), ignore (9).

---

### 8. Documentation Accuracy

**Key question:** Do docstrings, comments, and docs match actual behavior?

**Score:** 7/10
**Evidence:**
- File-level docstrings on all 6 source files, all accurate (Tier C).
- `parse_diff()` docstring: "Parse a unified diff into structured ChangedFile objects. Handles: new files, deleted files, renames, binary files, no-newline markers." -- accurate (Tier C).
- `RuleEngine.run()` docstring: "Run all rules and collect results, filtering # nogrip pragmas." -- accurate (Tier C).
- `RuleEngine.check_gate()` docstring: "Return True if any non-suppressed result meets or exceeds the profile's fail_on threshold." -- accurate (Tier C).
- `RuleContext.added_lines_for()` docstring: accurate (Tier C).
- `load_profile()` has comprehensive docstring with Args/Returns/Raises sections (Tier C).
- Not 9: No usage examples. No documented invariants for `parse_diff()` behavior on edge cases. Individual regex pattern rationale not documented.

---

### 9. Performance

**Key question:** Is the unit efficient for its workload?

**Score:** 8/10
**Evidence:**
- 4 regex patterns compiled once at module load via `re.compile()` (Tier C: context.py:76-79). No per-invocation recompilation.
- `parse_diff()`: O(lines) single pass with line-by-line regex matching. Regex operations are O(line_length) per line with no backtracking risk (proven by ReDoS tests).
- `RuleEngine.run()`: O(rules x findings) with `build_nogrip_index()` called once per run.
- `check_gate()`: O(results) single pass with `any()` short-circuit.
- `added_lines_for()`: O(files x hunks x lines) with `fnmatch` filtering -- appropriate for expected workload.
- `PROFILES` dict: O(1) lookup.
- Not 9: No profiling data. "Efficient for workload" by structural argument, not measurement.
- Calibration: matches rule-secrets (8).

---

### 10. Dead Code / Debt

**Key question:** Is the unit free of unused code and tracked debt?

**Score:** 9/10
**Evidence:**
- Zero `TODO` or `FIXME` comments across all 6 source files (Tier A: grep search).
- All classes/functions used: `RuleEngine` by `__init__.py` wrappers and callers, `parse_diff` by `run_rules()`, `DiffLine`/`DiffHunk`/`ChangedFile`/`RuleContext` by rules and engine, `ProfileConfig`/`PROFILES`/`load_profile` by callers, `Rule` Protocol by `RuleEngine.__init__`, all 10 rules by `RULE_REGISTRY` (Tier C: caller trace).
- ruff detects no unused imports (Tier A: static analysis).
- `__all__` in `__init__.py` matches actual exports (Tier A: module inspection).
- Not 10: `RuleContext.diff` field stores the raw diff string alongside parsed `files`. This duplication exists so individual rules can access raw text if needed. Not debt -- intentional design.

---

### 11. Dependency Hygiene

**Key question:** Are unit boundaries clean with no circular or unnecessary deps?

**Score:** 8/10
**Evidence:**
- 3 internal dependencies: `grippy.rules.base` (Rule, RuleResult), `grippy.rules.context` (RuleContext, parse_diff), `grippy.ignore` (build_nogrip_index) (Tier A: import inspection).
- `grippy.ignore` is a Phase 0 unit already audited (7.6/10 CURRENT). Clean dependency direction.
- `grippy.rules.registry` imported lazily inside `RuleEngine.__init__()` to avoid circular imports (Tier C: engine.py:19-20).
- `grippy.rules.config` imported via `TYPE_CHECKING` in context.py, engine.py -- no runtime circular risk (Tier A).
- 1 stdlib dependency: `re`, `fnmatch`, `dataclasses`, `os`, `enum`, `typing` (Tier A: import inspection).
- No circular imports (Tier A: ruff check).
- Not 9: 3 internal deps + 1 lazy import pattern. Dependencies are necessary and clean but not minimal.
- Calibration: rule-secrets scored 9 (2 internal deps). rule-engine has more dependencies due to larger scope (6 files vs 1).
