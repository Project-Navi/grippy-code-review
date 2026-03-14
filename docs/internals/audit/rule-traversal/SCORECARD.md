<!-- SPDX-License-Identifier: MIT -->

# Audit Scorecard: rule-traversal

**Audit date:** 2026-03-13
**Commit:** ab7cc93
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
| 3. Security Posture | 7/10 | C | No I/O, no secrets in findings. Evidence contains file operation code. |
| 4. Adversarial Resilience | 6/10 | A + C | ReDoS tests on 2 quantifier-bearing regexes (Tier A). 1MB long-line tolerance (Tier A). No adversarial fixtures beyond ReDoS. |
| 5. Auditability & Traceability | 6/10 | C | Findings include rule_id/file/line/evidence. Deterministic. No logging. |
| 6. Test Quality | 7/10 | A | 15 tests. Positive (6), negative (2), file-type edge (3), metadata (1), adversarial (3). |
| 7. Convention Adherence | 9/10 | A | ruff, mypy strict, bandit clean. SPDX header. Mirror test structure. |
| 8. Documentation Accuracy | 7/10 | C | File-level docstring, class docstring, helpers documented. |
| 9. Performance | 8/10 | C | Compiled regexes, linear scan, early exits on file extension. |
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
| SR-01 | PASS | Tier A: 4 positive taint tests (`test_open_with_user_input`, `test_open_with_request`, `test_path_join_with_input`, `test_path_join_with_upload`) exercise `_FILE_OPS_RE` + `_has_taint_indicator()`. 2 traversal tests (`test_traversal_unix`, `test_traversal_windows`) exercise `_TRAVERSAL_RE`. 2 negative tests (`test_string_literal_not_flagged`, `test_no_taint_indicator_not_flagged`) verify exemptions. | All 3 regexes and both detection paths exercised. |
| SR-02 | PASS | Tier A: `test_redos_file_ops_re` exercises `_FILE_OPS_RE` with 100K-char adversarial input under 5s timeout. `test_redos_string_literal_only_re` exercises `_STRING_LITERAL_ONLY_RE` with unmatched-quote input forcing `[^"']*` to scan full 100K input. `_TRAVERSAL_RE` is a simple literal alternation (`\.\./` or `\.\.\\`) with no quantifiers -- structurally immune to backtracking. | All quantifier-bearing patterns proven safe. |
| SR-03 | PASS | Tier A: `test_severity_is_warn` asserts all findings are WARN. Tier C: `default_severity = RuleSeverity.WARN` (line 68), used consistently in both `RuleResult` constructors (lines 92, 110). | Matches gate thresholds: WARN gates on strict-security only. |
| SR-04 | PASS (design note) | Tier C: `line.type != "add"` check at line 78, direct iteration over `hunk.lines`. Functionally equivalent to `ctx.added_lines_for()` but uses direct iteration instead of the helper. | **Design observation (Dim 7):** uses direct hunk iteration rather than `ctx.added_lines_for()`. Same correctness, different convention from rule-sql/rule-crypto. Not a finding -- both approaches are valid. |
| SR-05 | PASS | Tier C: All `RuleResult` instances include `rule_id=self.id`, `severity`, `message`, `file=f.path`, `line=line.new_lineno`, `evidence=content.strip()` (lines 88-97, 103-111). Evidence is NOT truncated (unlike rule-sql/rule-crypto which truncate at 120 chars). | Sufficient for human triage. Untruncated evidence is more informative but could be verbose for very long lines. |
| SR-06 | N/A | Ownership: engine-owned. Individual rule units do not own profile dispatch logic. | Per SR-06 scope note: "Mark N/A when auditing individual rule units." |
| SR-07 | PASS | Tier C: Evidence contains file operation code patterns (e.g., `open(user_path)`, `os.path.join(base, "../../../etc/passwd")`). These are code snippets, not secret values. | No leakage risk. |
| SR-08 | PASS | Tier C: All findings use standard `RuleResult` dataclass (imported from rules.base). Fields are compatible with `ResultEnrichment` post-processing. | Standard format matches enrichment contract. |
| SR-09 | Partial | Tier A: Positive (6: 4 taint + 2 traversal), negative (2: string literal + no taint), file-type edge (3: non-code, JS, TS), metadata (1: severity), adversarial (3: 2 ReDoS + 1 long-line). Missing: renamed/binary files, `.tsx`/`.jsx` file types, Unicode identifiers as taint names. | See F-TRV-001. |

**N/A items:** 1/9 (SR-06 only). Well below the >50% reclassification threshold.

---

## Findings

### F-TRV-001: Fixture matrix missing edge-case file types and Unicode

**Severity:** LOW
**Status:** OPEN
**Checklist:** SR-09
**Evidence tier:** C (manual review of test file)

**Description:** The fixture matrix covers both detection paths (taint + traversal) with positive/negative tests, and includes ReDoS adversarial tests and 1MB line tolerance. However, it lacks tests for:
- Renamed file diffs (diff with rename header)
- Binary files (should be skipped gracefully)
- `.tsx`/`.jsx` file extensions (currently only `.py`, `.js`, `.ts` tested -- extension list is `.py`, `.js`, `.ts`)
- Unicode identifiers that contain taint-name components (e.g., `user_naïve`)

**Impact:** LOW -- `.tsx`/`.jsx` are NOT in the `_EXTENSIONS` frozenset, so they are correctly ignored. Renamed files produce valid diffs that would match normally. Binary files produce no hunks. Unicode is a theoretical edge case for identifier splitting.

**Recommendation:** Consider adding `.tsx`/`.jsx` extension tests (would verify correct exclusion) in a future batch. The binary/renamed cases are handled by the diff parser, not this rule.

### Compound Chain Exposure

`None identified` -- rule-traversal produces RuleResult findings consumed by the engine/enrichment layer. No I/O, no subprocess, no prompt composition. Does not own trust-boundary behavior.

---

## Dimension Details

### 1. Contract Fidelity

**Key question:** Do types, exports, and validation faithfully represent the unit's contract?

**Score:** 7/10
**Evidence:**
- mypy strict passes with zero issues (Tier A: static analysis).
- All functions fully typed: `run(self, ctx: RuleContext) -> list[RuleResult]`, `_file_ext(path: str) -> str`, `_has_taint_indicator(content: str) -> bool`, `_has_traversal_pattern(content: str) -> bool` (Tier A: mypy proves this).
- Rule follows duck-typed Rule protocol: exposes `id`, `description`, `default_severity`, `run()`.
- `TAINT_NAMES` typed as `frozenset` with string literals (Tier A: mypy).
- Not 9: No explicit Protocol class. No runtime type checks beyond type annotations.
- Calibration: matches rule-secrets (7), rule-workflows (7), rule-sinks (7).

---

### 2. Robustness

**Key question:** Does the unit handle errors, retries, and edge cases correctly?

**Score:** 6/10
**Evidence:**
- Pure function design: `run()` takes context, returns findings list. If no patterns match, returns empty list (Tier C).
- `_file_ext()` handles files with no extension gracefully (returns `""`) (Tier C: line 44).
- `_has_taint_indicator()` handles lines with no open-paren gracefully via fallback to full content check (Tier C: line 52).
- `re.split(r"[^a-zA-Z]+", ...)` handles empty strings and non-alpha input gracefully (Tier C).
- No bounds on total result count. No retries/timeouts needed.
- Not 7: Rubric criteria for 7+ structurally inapplicable.
- Calibration: matches rule-secrets (6), rule-workflows (6), rule-sinks (6).

---

### 3. Security Posture

**Key question:** Does the unit protect against injection, leakage, and unauthorized access?

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 7/10
**Evidence:**
- No I/O, no network, no subprocess, no logging (Tier C: module-level inspection).
- Evidence field contains code patterns (e.g., `open(user_path)`, `os.path.join(base, user_input)`) which are code snippets, not secrets (Tier C: SR-07 analysis).
- `content.strip()` on evidence prevents whitespace-based injection (Tier C: lines 95, 109).
- Does not own trust boundaries. Processes structured diff data from `parse_diff()`.
- Not 9: No input sanitization (appropriate -- processes structured data). Single detection layer.
- Calibration: matches rule-secrets (7), rule-workflows (7), rule-sinks (7).

---

### 4. Adversarial Resilience

**Key question:** Can the unit resist adversarial input from untrusted PR content and prompt injection?

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 6/10
**Evidence:**
- **ReDoS defense (Tier A):** 2 tests covering `_FILE_OPS_RE` and `_STRING_LITERAL_ONLY_RE` with 100K-char adversarial inputs under 5s timeout. Both patterns are structurally safe: `_FILE_OPS_RE` uses `\b` word boundaries with no nested quantifiers; `_STRING_LITERAL_ONLY_RE` uses `[^"']*` (negated character class, cannot backtrack).
- **`_TRAVERSAL_RE` structural analysis (Tier C):** Simple alternation `(?:\.\./|\.\.\\)` with no quantifiers. Immune to backtracking by construction.
- **Large input tolerance (Tier A):** `test_extremely_long_line` proves >1MB lines are processed without crash.
- Limited adversarial exposure: processes parsed diff lines (structured data from parse_diff()). Attack surface is ReDoS and false positive/negative manipulation.
- Not 7: No adversarial fixture matrix beyond ReDoS + long-line (F-TRV-001). No Unicode adversarial tests. The `TAINT_NAMES` wordlist approach means adversarial evasion (using synonyms or obfuscated names) is inherently limited -- this is a design constraint, not a fixable gap.
- Calibration: matches rule-workflows (6) and rule-sinks (6). Above rule-secrets (5, no ReDoS tests).

---

### 5. Auditability & Traceability

**Key question:** Can operators investigate failures, reproduce review results, and trace the decision path from input to output?

**Score:** 6/10
**Evidence:**
- Each `RuleResult` includes `rule_id`, `severity`, `message`, `file`, `line`, `evidence` (Tier C: code inspection at lines 88-97, 103-111).
- Messages distinguish detection paths: "File operation with user-controlled input indicator" vs "Path traversal pattern in file operation" (Tier C).
- Deterministic: same diff input -> same findings output. Fully reproducible.
- No logging -- appropriate for a rule.
- Not 7: No structured error context. No trace correlation IDs.
- Calibration: matches rule-secrets (6), rule-workflows (6), rule-sinks (6).

---

### 6. Test Quality

**Key question:** Do tests verify meaningful behavior with good coverage?

**Score:** 7/10
**Evidence:**
- **Test count:** 15 tests across 2 test classes (Tier A: test_grippy_rule_traversal.py).
- **Source:test ratio:** 1.21:1 (138 LOC tests / 114 LOC source).
- **Fixture matrix categories covered:**
  - Positive: 6 tests (4 taint indicator + 2 traversal pattern).
  - Negative: 2 tests (string literal, no taint indicator).
  - File-type edge: 3 tests (non-code ignored, JS supported, TS supported).
  - Metadata: 1 test (severity is WARN).
  - Adversarial: 3 tests (2 ReDoS + 1 long-line).
- Missing categories (F-TRV-001): renamed files, binary files, `.tsx`/`.jsx` extensions, Unicode identifiers.
- Calibration: rule-secrets scored 6 (14 tests, no adversarial). rule-workflows scored 7 (15 tests, ReDoS + proximity). rule-traversal matches rule-workflows at 7: same test count, ReDoS coverage, broader file-type edge cases.

---

### 7. Convention Adherence

**Key question:** Does the unit follow Grippy project patterns?

**Score:** 9/10
**Evidence:**
- SPDX header present on source and test file (Tier A: file inspection).
- ruff check passes with zero issues (Tier A: static analysis).
- mypy strict passes with zero issues (Tier A: static analysis).
- bandit passes with zero issues (Tier A: static analysis).
- Test file follows mirror structure: `src/grippy/rules/path_traversal.py` -> `tests/test_grippy_rule_traversal.py` (Tier A).
- Test file exceeds 50 LOC minimum (138 LOC) (Tier A).
- Naming consistent: PascalCase for class, snake_case for functions, UPPER_CASE for module constants.
- **Design observation:** Uses direct `hunk.lines` iteration (line 77) instead of `ctx.added_lines_for()`. This differs from rule-sql and rule-crypto which use the helper. Both approaches are correct; direct iteration gives more control (access to `line.type` directly) but doesn't use the canonical helper. This is a convention divergence, not a defect.
- Calibration: matches all prior units at 9.

---

### 8. Documentation Accuracy

**Key question:** Do docstrings, comments, and docs match actual behavior?

**Score:** 7/10
**Evidence:**
- File-level docstring: "Rule 4: path-traversal-risk — flag tainted variable names in file operations." (line 2) -- accurate (Tier C).
- Class docstring: "Flag file operations with tainted variable names or traversal patterns." (line 64) -- accurate (Tier C).
- `_has_taint_indicator` has docstring: "Check if any taint name appears as an identifier component in the arguments." -- accurate (Tier C).
- `_has_traversal_pattern` has docstring: "Check for ../ or ..\\ in the content." -- accurate (Tier C).
- Inline comments explain `TAINT_NAMES` purpose (line 11) and string literal exemption (line 35).
- Not 9: No usage examples. `TAINT_NAMES` wordlist rationale not documented. Identifier splitting algorithm not explained in docstring.
- Calibration: matches rule-secrets (7), rule-workflows (7), rule-sinks (7).

---

### 9. Performance

**Key question:** Is the unit efficient for its workload?

**Score:** 8/10
**Evidence:**
- 3 regex patterns compiled once at module load via `re.compile()` (Tier C: lines 28-38). No per-invocation recompilation.
- `TAINT_NAMES` is a `frozenset` for O(1) membership testing (Tier C: line 12).
- Linear scan: O(files x hunks x lines). Per-line work: up to 2 regex searches + 1 set intersection.
- Early exit: non-code files skipped by extension check (line 74).
- `_STRING_LITERAL_ONLY_RE` check before `_FILE_OPS_RE` + taint check prevents unnecessary taint analysis on string literal arguments (line 83-84).
- Not 9: No profiling data.
- Calibration: matches rule-secrets (8), rule-workflows (8), rule-sinks (8).

---

### 10. Dead Code / Debt

**Key question:** Is the unit free of unused code and tracked debt?

**Score:** 9/10
**Evidence:**
- Zero `TODO` or `FIXME` comments (Tier A: grep search).
- All functions called: `PathTraversalRule` registered in `RULE_REGISTRY` (registry.py), `_file_ext` at line 73, `_has_taint_indicator` at line 87, `_has_traversal_pattern` at line 101 (Tier C: caller trace).
- All 3 compiled regexes used: `_FILE_OPS_RE` at lines 83, 87, 101; `_TRAVERSAL_RE` at line 60; `_STRING_LITERAL_ONLY_RE` at line 83 (Tier C: usage trace).
- ruff detects no unused imports (Tier A).
- `_EXTENSIONS` frozenset used at line 74 (Tier C).
- Not 10: F-TRV-001 identifies a minor fixture matrix gap -- not code debt, but tracked.
- Calibration: matches rule-secrets (9), rule-workflows (9), rule-sinks (9).

---

### 11. Dependency Hygiene

**Key question:** Are unit boundaries clean with no circular or unnecessary deps?

**Score:** 9/10
**Evidence:**
- 2 internal dependencies: `grippy.rules.base` (RuleResult, RuleSeverity) and `grippy.rules.context` (RuleContext). Both are same-phase (Phase 1) sibling modules (Tier A: import inspection at lines 8-9).
- 1 external dependency: `re` (stdlib) (Tier A: import inspection at line 6).
- No circular imports (Tier A: ruff check).
- Imports only `RuleContext` (not `ChangedFile`, `DiffHunk`, `DiffLine`) despite using direct iteration -- accesses these types transitively through `ctx.files` (Tier C). This is actually slightly unusual: it accesses `DiffLine.type` and `DiffLine.new_lineno` without importing the type. Functionally correct, type-safe via structural typing.
- Not 10: Has 2 internal dependencies.
- Calibration: matches rule-secrets (9), rule-workflows (9), rule-sinks (9).
