<!-- SPDX-License-Identifier: MIT -->

# Audit Scorecard: rule-workflows

**Audit date:** 2026-03-13
**Commit:** b40d4ec
**Auditor:** Claude Opus 4.6 (AI draft) / Nelson Spence (human reviewer)
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
| 1. Contract Fidelity | 7/10 | A | All functions typed, mypy strict clean, RuleResult/RuleContext used correctly |
| 2. Robustness | 6/10 | C | Pure function -- no error handling needed. No bounds on result count. |
| 3. Security Posture | 7/10 | C | No I/O, no secrets in findings. YAML workflow content is non-secret. |
| 4. Adversarial Resilience | 6/10 | A + C | ReDoS tests on 3 regexes (Tier A). No adversarial fixture matrix beyond ReDoS. |
| 5. Auditability & Traceability | 6/10 | C | Findings include rule_id/file/line/evidence. Deterministic. No logging. |
| 6. Test Quality | 7/10 | A | 15 tests. Positive, negative, adversarial (ReDoS), proximity window coverage. |
| 7. Convention Adherence | 9/10 | A | ruff, mypy strict, bandit clean. SPDX header. Mirror test structure. |
| 8. Documentation Accuracy | 7/10 | C | File-level docstring, class docstring, all helpers documented. |
| 9. Performance | 8/10 | C | Compiled regexes, linear scan, proximity window bounded. |
| 10. Dead Code / Debt | 9/10 | A + C | Zero TODOs, all functions called, clean imports. |
| 11. Dependency Hygiene | 9/10 | A | 2 internal deps (rules.base, rules.context) -- same phase. No circular deps. |
| **Overall** | **7.4/10** | | **Average of 11 dimensions** |

**Health status:** Adequate (provisional)

**Determination:**
1. Average-based status: 7.4/10 falls in 6.0-7.9 range = Adequate
2. Override gates: None fired.
3. Ceiling gates: None fired. All gate dimensions >= 6.
4. Suffixes: `(provisional)` -- dims 2, 3, 5, 8, 9 include Tier C evidence components.

**Override gates fired:** None
**Ceiling gates fired:** None

---

## Checklist: SR-01 through SR-09

| ID | Verdict | Evidence | Notes |
|----|---------|----------|-------|
| SR-01 | PASS | Tier A: 5 positive tests cover all 3 detection branches (permissions block: `test_write_permission_on_added_line` + `test_admin_permission`, pull_request_target: `test_pull_request_target`, unpinned actions: `test_unpinned_action`, scalar permissions: `test_scalar_permissions_write_all`). 5 negative tests confirm non-matches. | All documented patterns detected. |
| SR-02 | PASS | Tier A: 3 ReDoS tests (`test_redos_permissions_re`, `test_redos_uses_re`, `test_redos_sha_pin_re`) exercise all 3 compiled regexes with 100K-char adversarial inputs under 5s timeout guard. | Patterns are word-boundary anchored or `^`-anchored with no nested quantifiers. _PR_TARGET_RE and _WRITE_ADMIN_RE use `\b` word boundaries -- structurally safe, not separately tested (same pattern class as tested regexes). |
| SR-03 | PASS | Tier C: ERROR severity for permissions/pull_request_target (lines 76, 89), WARN for unpinned actions (line 112). Tier A: `test_write_permission_on_added_line` asserts ERROR, `test_unpinned_action` asserts WARN. | Matches gate thresholds: ERROR gates on security/strict, WARN gates on strict only. |
| SR-04 | PASS (design note) | Tier A: `test_proximity_window_inside` proves context line within +/-2 of added line IS detected. `test_proximity_window_outside` proves context line >2 away is NOT detected. | Unpinned actions use `dl.type == "add"` (added-only, line 99). Permissions/pull_request_target use `_is_near_added()` proximity (+/-2 lines). This is an **accepted design choice** -- YAML block structure means a pre-existing `permissions: write-all` near newly added code is security-relevant context. The proximity window is bounded and tested. |
| SR-05 | PASS | Tier C: All `RuleResult` instances include `rule_id=self.id`, `severity`, `message`, `file=f.path`, `line=dl.new_lineno or dl.old_lineno`, `evidence=content.strip()` (lines 73-80, 88-95, 109-117). | Sufficient for human triage. |
| SR-06 | N/A | Ownership: engine-owned. Individual rule units do not own profile dispatch logic. The engine selects which rules to run based on profile configuration. | Per SR-06 scope note: "Mark N/A when auditing individual rule units." |
| SR-07 | PASS | Tier C: Evidence contains YAML workflow content -- permissions keys (`contents: write`), action references (`actions/checkout@v4`), trigger names (`pull_request_target`). None of these are secret values. | YAML workflow patterns are public configuration, not credentials. |
| SR-08 | PASS | Tier C: All findings use standard `RuleResult` dataclass (imported from rules.base). Fields are compatible with `ResultEnrichment` post-processing (blast_radius, recurrence, suppression). | Standard format matches enrichment contract. |
| SR-09 | Partial | Tier A: Positive tests (5), negative tests (5), adversarial (3 ReDoS + 2 proximity). Missing categories: renamed/binary workflow files, deeply nested YAML permissions blocks, workflow files with unusual extensions. | See F-RW-001. |

**N/A items:** 1/9 (SR-06 only). Well below the >50% reclassification threshold.

---

## Findings

### F-RW-001: Fixture matrix incomplete for edge-case YAML structures

**Severity:** LOW
**Status:** OPEN
**Checklist:** SR-09
**Evidence tier:** C (manual review of test file)

**Description:** The fixture matrix covers all 3 detection branches with positive/negative tests and includes ReDoS adversarial tests and proximity window tests. However, it lacks tests for:
- Renamed workflow files (diff with rename header)
- Binary workflow files (should be skipped gracefully)
- Deeply nested YAML permissions blocks (3+ levels of indentation)
- Workflow files with `.yaml` extension (only `.yml` tested)

**Impact:** LOW -- these edge cases are unlikely to cause false positives/negatives in practice. The file extension check (line 55) handles both `.yml` and `.yaml`. Renamed files would still be checked if the new path matches the workflow prefix. Binary files produce no hunks so rules never fire.

**Recommendation:** Add `.yaml` extension test and renamed workflow file test in a future batch. The binary file case is handled by the diff parser (no hunks = no findings), not by this rule.

### Compound Chain Exposure

`None identified` -- rule-workflows produces RuleResult findings consumed by the engine/enrichment layer but does not own trust-boundary behavior or participate in data flow chains (no I/O, no subprocess, no prompt composition).

---

## Dimension Details

### 1. Contract Fidelity

**Key question:** Do types, exports, and validation faithfully represent the unit's contract?

**Score:** 7/10
**Evidence:**
- mypy strict passes with zero issues (Tier A: static analysis).
- All functions fully typed: `run(self, ctx: RuleContext) -> list[RuleResult]`, `_scan_hunk(self, f: ChangedFile, hunk: DiffHunk) -> list[RuleResult]`, `_check_permissions_block(...)  -> list[RuleResult]`, helpers return `int`/`bool`/`list` (Tier A: mypy proves this).
- Rule follows duck-typed Rule protocol: exposes `id`, `description`, `default_severity`, `run()`. Compatible with `RULE_REGISTRY` and `RuleEngine` expectations.
- `RuleResult` and `RuleContext` imports from rules.base/context establish the contract (Tier A: import inspection).
- Not 9: No explicit Protocol class. No runtime type checks beyond type annotations.
- Calibration: matches rule-secrets (7), rule-engine (8 -- higher due to Protocol definition ownership).

---

### 2. Robustness

**Key question:** Does the unit handle errors, retries, and edge cases correctly?

**Score:** 6/10
**Evidence:**
- Pure function design: `run()` takes context, returns findings list. If no patterns match, returns empty list -- a valid success state (Tier C: code reading).
- `_is_near_added()` handles boundary conditions: `0 <= check < len(lines)` bounds check prevents IndexError (Tier C: code reading at line 40).
- `_indent_level()` handles empty strings gracefully (`len("") - len("") = 0`) (Tier C: code reading at line 24).
- No bounds on output: a hunk with many matching lines produces correspondingly many findings. The engine/pipeline must handle this.
- No retries, timeouts, or resource management needed -- appropriate for a stateless pattern scanner.
- Not 7: Rubric criteria for 7+ (retry, timeout, resource cleanup) are structurally inapplicable. No bounds check on result count.
- Calibration: matches rule-secrets (6).

---

### 3. Security Posture

**Key question:** Does the unit protect against injection, leakage, and unauthorized access?

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 7/10
**Evidence:**
- No I/O, no network, no subprocess, no logging (Tier C: module-level inspection).
- Finding evidence contains YAML content (permissions keys, action refs, trigger names) which is public configuration, not secrets (Tier C: SR-07 analysis).
- `content.strip()` on evidence prevents whitespace-based injection in downstream consumers (Tier C: code reading at lines 79, 94, 117, 145).
- Proximity-based detection (`_is_near_added()`) is bounded to +/-2 lines, preventing unbounded context expansion (Tier A: `test_proximity_window_outside`).
- Does not own trust boundaries. Processes structured diff data from parse_diff().
- Not 9: No input sanitization (appropriate -- processes structured data). No defense-in-depth (single detection layer).
- Calibration: matches rule-secrets (7), rule-engine (7).

---

### 4. Adversarial Resilience

**Key question:** Can the unit resist adversarial input from untrusted PR content and prompt injection?

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 6/10
**Evidence:**
- **ReDoS defense (Tier A):** 3 tests covering `_PERMISSIONS_RE`, `_USES_RE`, `_SHA_PIN_RE` with 100K-char adversarial inputs under 5s timeout. All patterns are `^`-anchored or word-boundary anchored with non-nested quantifiers.
- `_PR_TARGET_RE` and `_WRITE_ADMIN_RE` use `\b` word boundaries -- same structural class as tested patterns, no nested quantifiers (Tier C: regex analysis).
- **Proximity window bounded (Tier A):** `test_proximity_window_inside` and `test_proximity_window_outside` prove the +/-2 window is correctly bounded.
- Limited adversarial exposure: rule processes parsed diff lines (already structured data from parse_diff()). Attack surface is constrained to ReDoS and false positive/negative manipulation.
- Not 7: No adversarial fixture matrix beyond ReDoS + proximity (F-RW-001). No Unicode adversarial tests.
- Calibration: between rule-secrets (5, no ReDoS tests) and rule-engine (7, full adversarial matrix). Scored 6 due to ReDoS coverage but missing other adversarial categories.

---

### 5. Auditability & Traceability

**Key question:** Can operators investigate failures, reproduce review results, and trace the decision path from input to output?

**Score:** 6/10
**Evidence:**
- Each `RuleResult` includes `rule_id`, `severity`, `message`, `file`, `line`, `evidence` -- sufficient for human triage (Tier C: code inspection at lines 73-80, 88-95, 109-117, 138-146).
- Messages are descriptive: "Workflow permissions expanded to write/admin", "pull_request_target trigger detected -- runs with base repo secrets", "Unpinned action -- use SHA instead of tag: {ref}" (Tier C).
- Deterministic: same diff input -> same findings output. Fully reproducible.
- No logging within the module -- appropriate for a rule (logging is engine-level).
- Not 7: No structured error context. No trace correlation IDs.
- Calibration: matches rule-secrets (6), rule-engine (7 -- higher due to richer output context).

---

### 6. Test Quality

**Key question:** Do tests verify meaningful behavior with good coverage?

**Score:** 7/10
**Evidence:**
- **Test count:** 15 tests across 3 test classes (Tier A: test_grippy_rule_workflow.py).
- **Source:test ratio:** 1.67:1 (249 LOC tests / 149 LOC source).
- **Fixture matrix categories covered:**
  - Positive: 5 tests (permissions write, admin, scalar write-all, pull_request_target, unpinned action).
  - Negative: 5 tests (read permission, scalar read, SHA-pinned, local action, non-workflow file).
  - Adversarial: 3 tests (ReDoS on 3 regexes).
  - Edge cases: 2 tests (proximity window inside/outside).
- Missing categories (F-RW-001): renamed workflow files, binary workflow files, `.yaml` extension, nested YAML.
- Calibration: rule-secrets scored 6 (14 tests, no adversarial). rule-workflows scores higher with ReDoS coverage and proximity window evidence. rule-engine scored 7 (46 tests, full adversarial matrix) -- rule-workflows matches on category breadth despite fewer total tests.

---

### 7. Convention Adherence

**Key question:** Does the unit follow Grippy project patterns?

**Score:** 9/10
**Evidence:**
- SPDX header present on source and test file (Tier A: file inspection).
- ruff check passes with zero issues (Tier A: static analysis).
- mypy strict passes with zero issues (Tier A: static analysis).
- bandit passes with zero issues (Tier A: static analysis).
- Test file follows mirror structure: `src/grippy/rules/workflow_permissions.py` -> `tests/test_grippy_rule_workflow.py` (Tier A).
- Test file exceeds 50 LOC minimum (249 LOC) (Tier A).
- Naming consistent: PascalCase for class, snake_case for functions, UPPER_CASE for module constants.
- Calibration: matches schema (9), rule-secrets (9), rule-engine (9).

---

### 8. Documentation Accuracy

**Key question:** Do docstrings, comments, and docs match actual behavior?

**Score:** 7/10
**Evidence:**
- File-level docstring: "Rule 1: workflow-permissions-expanded -- block-aware YAML scanning for GitHub Actions." (line 2) -- accurate (Tier C).
- Class docstring: "Detect expanded permissions, pull_request_target, and unpinned actions." (line 46) -- accurate (Tier C).
- All 3 helper functions have docstrings: `_indent_level`, `_collect_hunk_lines`, `_is_near_added` -- all accurate (Tier C).
- Inline comments explain intent: "Skip local actions (./)..." (line 105), "Check scalar permissions on same line" (line 69), "Also check block-style indented children" (line 82).
- Not 9: No usage examples. Proximity-based design rationale not documented in code (only in audit scorecard). Individual regex pattern rationale not documented.
- Calibration: matches rule-secrets (7), rule-engine (7).

---

### 9. Performance

**Key question:** Is the unit efficient for its workload?

**Score:** 8/10
**Evidence:**
- 5 regex patterns compiled once at module load via `re.compile()` (Tier C: lines 15-19). No per-invocation recompilation.
- Linear scan: O(files x hunks x lines) with per-line regex matching. Each line tested against 3-4 patterns max.
- `_is_near_added()` bounded to +/-2 window (5 iterations max per call) -- O(1) per invocation (Tier C: code reading at lines 38-42).
- `_check_permissions_block()` linear scan with early exit when indent level drops (Tier C: code reading at lines 135-136).
- Early exit: non-workflow files skipped entirely (line 55).
- Not 9: No profiling data. "Efficient for workload" by structural argument, not measurement.
- Calibration: matches rule-secrets (8), rule-engine (8).

---

### 10. Dead Code / Debt

**Key question:** Is the unit free of unused code and tracked debt?

**Score:** 9/10
**Evidence:**
- Zero `TODO` or `FIXME` comments (Tier A: grep search).
- All functions called: `WorkflowPermissionsRule` registered in `RULE_REGISTRY` (registry.py), `_indent_level` at line 130, `_collect_hunk_lines` at line 63, `_is_near_added` at lines 71, 86, 137, `_scan_hunk` at line 58, `_check_permissions_block` at line 83 (Tier C: caller trace).
- ruff detects no unused imports (Tier A: static analysis).
- All 5 compiled regexes used: `_PERMISSIONS_RE` at line 67, `_USES_RE` at line 100, `_SHA_PIN_RE` at line 107, `_PR_TARGET_RE` at line 86, `_WRITE_ADMIN_RE` at lines 71, 137 (Tier C: usage trace).
- Not 10: F-RW-001 identifies a minor fixture matrix gap -- not code debt, but tracked.
- Calibration: matches rule-secrets (9), rule-engine (9).

---

### 11. Dependency Hygiene

**Key question:** Are unit boundaries clean with no circular or unnecessary deps?

**Score:** 9/10
**Evidence:**
- 2 internal dependencies: `grippy.rules.base` (RuleResult, RuleSeverity) and `grippy.rules.context` (ChangedFile, DiffHunk, DiffLine, RuleContext). Both are same-phase (Phase 1) sibling modules (Tier A: import inspection at lines 8-9).
- 1 external dependency: `re` (stdlib) (Tier A: import inspection at line 6).
- No circular imports (Tier A: ruff check).
- Depends only on the rule framework types it must use -- minimal coupling.
- Not 10: Has 2 internal dependencies (vs schema's zero). Dependencies are necessary and clean but not zero.
- Calibration: matches rule-secrets (9).
