<!-- SPDX-License-Identifier: MIT -->

# Audit Scorecard: rule-sql

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
| 2. Robustness | 6/10 | A + C | Pure function. `break` limits to one finding per line. No bounds on total. |
| 3. Security Posture | 7/10 | C | No I/O, no secrets in findings. Evidence truncated at 120 chars. |
| 4. Adversarial Resilience | 6/10 | A + C | ReDoS tests on 3 patterns incl. primary targets _PERCENT_SQL/_CONCAT_SQL (Tier A). 1MB long-line tolerance (Tier A). |
| 5. Auditability & Traceability | 6/10 | C | Findings include rule_id/file/line/evidence. Deterministic. No logging. |
| 6. Test Quality | 7/10 | A | 15 tests. Positive (5), negative (3), edge (1), metadata (1), adversarial (5). |
| 7. Convention Adherence | 9/10 | A | ruff, mypy strict, bandit clean. SPDX header. Mirror test structure. |
| 8. Documentation Accuracy | 7/10 | C | File-level docstring, class docstring accurate. Inline regex comments. |
| 9. Performance | 8/10 | C | Compiled regexes, linear scan, `break` per line. Early exit on extension. |
| 10. Dead Code / Debt | 9/10 | A + C | Zero TODOs, all functions called, all patterns used. |
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
| SR-01 | PASS | Tier A: 5 positive tests cover all 4 compiled patterns: `test_fstring_select` (_FSTRING_SQL), `test_format_string_query` (_PERCENT_SQL), `test_concat_query` (_CONCAT_SQL), `test_execute_with_fstring` (_EXECUTE_FSTRING), `test_multiple_findings` (multiple _FSTRING_SQL matches). 3 negative tests (`test_parameterized_safe`, `test_sqlalchemy_text_safe`, `test_comment_ignored`) verify non-matches. | All documented patterns detected. |
| SR-02 | PASS | **Primary stress test for this batch.** Tier A: 4 ReDoS tests exercise the 3 patterns with backtracking risk: `test_redos_percent_sql_near_miss` — 100K chars of near-keyword fragments (`"sel " * 25_000`) against `_PERCENT_SQL`. `test_redos_percent_sql_keyword_no_trail` — real keyword early + 100K trailing chars against `_PERCENT_SQL`. `test_redos_concat_sql` — same near-miss input against `_CONCAT_SQL`. `test_redos_fstring_sql` — 100K chars against `_FSTRING_SQL`. All complete under 5s timeout. `_EXECUTE_FSTRING` has no `.*` quantifier — structurally safe. | **The `.*\b...\b.*` patterns in _PERCENT_SQL and _CONCAT_SQL do NOT exhibit catastrophic backtracking.** Python's `re` engine handles these efficiently due to the anchoring provided by `['"]` quote delimiters and `\b` word boundaries. |
| SR-03 | PASS | Tier A: `test_fstring_select` asserts `results[0].severity == RuleSeverity.ERROR`. Tier C: `default_severity = RuleSeverity.ERROR` (line 55), used consistently in `RuleResult` constructor (line 69). | All SQL injection findings are ERROR severity. Matches gate thresholds: ERROR gates on both security and strict-security profiles. |
| SR-04 | PASS | Tier C: `ctx.added_lines_for(f.path)` at line 62 explicitly filters to added lines only. This is the engine's canonical added-line filter. | Uses the standard helper -- consistent with rule-crypto and rule-sinks. |
| SR-05 | PASS | Tier C: All `RuleResult` instances include `rule_id=self.id`, `severity=self.default_severity`, `message`, `file=path`, `line=lineno`, `evidence=content.strip()[:120]` (lines 67-76). Evidence truncated at 120 chars -- prevents excessively long evidence while preserving enough context. | Sufficient for human triage. |
| SR-06 | N/A | Ownership: engine-owned. Individual rule units do not own profile dispatch logic. | Per SR-06 scope note: "Mark N/A when auditing individual rule units." |
| SR-07 | PASS | Tier C: Evidence contains SQL query patterns (e.g., `f"SELECT * FROM users WHERE id = {user_id}"`), not secret values. SQL patterns are code, not credentials. | No leakage risk. |
| SR-08 | PASS | Tier C: All findings use standard `RuleResult` dataclass (imported from rules.base). Fields are compatible with `ResultEnrichment` post-processing. | Standard format matches enrichment contract. |
| SR-09 | Partial | Tier A: Positive (5: fstring, percent, concat, execute, multiple), negative (3: parameterized, sqlalchemy, comment), edge (1: non-Python file), metadata (1: rule ID + severity), adversarial (5: 4 ReDoS + 1 long-line). Missing: renamed/binary files, multi-line SQL strings, ORM-style queries as near-miss negatives. | See F-SQL-001. Adversarial coverage is strong (5 tests, including the primary stress targets). |

**N/A items:** 1/9 (SR-06 only). Well below the >50% reclassification threshold.

---

## Findings

### F-SQL-001: Fixture matrix missing near-miss negatives and multi-line SQL

**Severity:** LOW
**Status:** OPEN
**Checklist:** SR-09
**Evidence tier:** C (manual review of test file)

**Description:** The fixture matrix has strong adversarial coverage (5 ReDoS tests including the primary stress targets) and reasonable positive/negative balance. However, it lacks tests for:
- Near-miss negatives: ORM-style queries that look like SQL but use safe abstractions (e.g., `User.query.filter_by(id=user_id)`)
- Multi-line SQL strings split across lines (rule only scans single lines)
- Renamed/binary files

**Impact:** LOW -- ORM-style queries don't match the patterns because they lack SQL keywords inside string literals. Multi-line SQL is a genuine detection gap but is inherent to the line-by-line scanning approach -- not fixable without architectural changes. Renamed/binary files are handled by the diff parser.

**Recommendation:** Add 1-2 near-miss negative tests in a future batch to prove specificity. The multi-line SQL gap is a known limitation of the line-by-line rule architecture and would be better addressed by the LLM review layer.

### Compound Chain Exposure

`None identified` -- rule-sql produces RuleResult findings consumed by the engine/enrichment layer. No I/O, no subprocess, no prompt composition. Does not own trust-boundary behavior.

---

## Dimension Details

### 1. Contract Fidelity

**Key question:** Do types, exports, and validation faithfully represent the unit's contract?

**Score:** 7/10
**Evidence:**
- mypy strict passes with zero issues (Tier A: static analysis).
- All functions fully typed: `run(self, ctx: RuleContext) -> list[RuleResult]`, `_file_ext(path: str) -> str`, `_is_comment(content: str) -> bool` (Tier A: mypy proves this).
- Rule follows duck-typed Rule protocol: exposes `id`, `description`, `default_severity`, `run()`.
- `_SQL_KEYWORDS` is a raw string constant used in regex composition (Tier C: line 11).
- 4 compiled patterns typed as `re.Pattern[str]` (Tier A: mypy).
- Not 9: No explicit Protocol class. No runtime type checks beyond type annotations.
- Calibration: matches rule-secrets (7), rule-workflows (7), rule-sinks (7), rule-traversal (7).

---

### 2. Robustness

**Key question:** Does the unit handle errors, retries, and edge cases correctly?

**Score:** 6/10
**Evidence:**
- Pure function design: `run()` takes context, returns findings list. If no patterns match, returns empty list (Tier C).
- `break` at line 77 limits to one finding per line -- prevents duplicate findings for lines matching multiple patterns (e.g., a line with `cursor.execute(f"SELECT ...")` would match both `_FSTRING_SQL` and `_EXECUTE_FSTRING`; `break` reports only the first match).
- `_file_ext()` handles files with no extension gracefully (returns `""`) (Tier C: line 41).
- `_is_comment()` handles empty strings gracefully (`"".strip().startswith("#")` -> False) (Tier C).
- >1MB line tolerance proven (Tier A: `test_extremely_long_line`).
- No bounds on total result count.
- Not 7: Rubric criteria for 7+ structurally inapplicable.
- Calibration: matches rule-secrets (6), rule-workflows (6), rule-sinks (6), rule-traversal (6).

---

### 3. Security Posture

**Key question:** Does the unit protect against injection, leakage, and unauthorized access?

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 7/10
**Evidence:**
- No I/O, no network, no subprocess, no logging (Tier C: module-level inspection).
- Evidence field contains SQL query patterns, not secret values (Tier C: SR-07 analysis).
- Evidence truncated at 120 chars (`content.strip()[:120]`) -- prevents excessively long evidence from leaking additional context (Tier C: line 74).
- Uses `ctx.added_lines_for(path)` -- delegates line filtering to the engine's canonical helper (Tier C: defense delegation).
- Does not own trust boundaries.
- Not 9: No input sanitization (appropriate -- processes structured data). Single detection layer.
- Calibration: matches rule-secrets (7), rule-workflows (7), rule-sinks (7), rule-traversal (7).

---

### 4. Adversarial Resilience

**Key question:** Can the unit resist adversarial input from untrusted PR content and prompt injection?

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 6/10
**Evidence:**
- **ReDoS defense -- PRIMARY STRESS TEST (Tier A):** 4 tests exercise the 3 patterns with backtracking risk. The `.*\b{SQL_KEYWORDS}\b.*` structure in `_PERCENT_SQL` and `_CONCAT_SQL` was the primary concern for this batch. Both near-miss adversarial inputs (100K chars of `"sel "` fragments) and keyword-without-trailing-condition inputs (real keyword + 100K trailing chars) complete under 5s timeout. Python's `re` engine handles these efficiently.
- **`_EXECUTE_FSTRING` structural analysis (Tier C):** No `.*` quantifier, no backtracking risk. Simple literal sequence `\.\s*(?:execute|executemany)\s*\(\s*f['"]`.
- **Large input tolerance (Tier A):** `test_extremely_long_line` proves >1MB lines processed without crash.
- Not 7: No adversarial fixture matrix beyond ReDoS + long-line. No near-miss negatives to test specificity under adversarial conditions. No Unicode SQL keyword evasion tests.
- Calibration: matches rule-workflows (6), rule-sinks (6), rule-traversal (6). Above rule-secrets (5, no ReDoS tests). Scored 6 despite having the batch's strongest ReDoS test suite because adversarial coverage is narrow (ReDoS only). No false-positive manipulation tests, no encoding evasion.

---

### 5. Auditability & Traceability

**Key question:** Can operators investigate failures, reproduce review results, and trace the decision path from input to output?

**Score:** 6/10
**Evidence:**
- Each `RuleResult` includes `rule_id`, `severity`, `message`, `file`, `line`, `evidence` (Tier C: code inspection at lines 67-76).
- Message is generic: "SQL injection risk: query built from interpolated input" -- does not identify which specific pattern matched (Tier C).
- Deterministic: same diff input -> same findings output. Fully reproducible.
- Pattern iteration order is fixed: `(_FSTRING_SQL, _PERCENT_SQL, _CONCAT_SQL, _EXECUTE_FSTRING)` (line 65). First match wins due to `break`. This means the finding doesn't reveal which pattern triggered -- traceability gap for debugging false positives.
- No logging -- appropriate for a rule.
- Not 7: Generic message loses pattern-specificity. No trace correlation IDs.
- Calibration: matches rule-secrets (6), rule-workflows (6), rule-sinks (6). Note: rule-sinks uses `f"Dangerous execution sink: {name}"` which IS pattern-specific. rule-sql's generic message is slightly less traceable but not enough to drop a point given the overall calibration.

---

### 6. Test Quality

**Key question:** Do tests verify meaningful behavior with good coverage?

**Score:** 7/10
**Evidence:**
- **Test count:** 15 tests across 2 test classes (Tier A: test_grippy_rule_sql_injection.py).
- **Source:test ratio:** 2.03:1 (158 LOC tests / 78 LOC source).
- **Fixture matrix categories covered:**
  - Positive: 5 tests (fstring, percent, concat, execute+fstring, multiple findings).
  - Negative: 3 tests (parameterized safe, sqlalchemy text, comment ignored).
  - Edge: 1 test (non-Python file ignored).
  - Metadata: 1 test (rule ID + severity).
  - Adversarial: 5 tests (4 ReDoS + 1 long-line).
- **Adversarial coverage note:** The 5 adversarial tests include the batch's primary stress targets (`_PERCENT_SQL`, `_CONCAT_SQL` with `.*\b...\b.*` structure). This is the strongest adversarial test suite in the batch. SR-09 scores independently because fixture matrix completeness (categories covered) is separate from adversarial depth (how hard the tests push).
- Missing categories (F-SQL-001): near-miss negatives, multi-line SQL, renamed files.
- Calibration: rule-secrets scored 6 (14 tests, no adversarial). rule-workflows scored 7 (15 tests, 3 adversarial). rule-sql matches at 7: same test count, strongest adversarial suite, good positive/negative balance.

---

### 7. Convention Adherence

**Key question:** Does the unit follow Grippy project patterns?

**Score:** 9/10
**Evidence:**
- SPDX header present on source and test file (Tier A: file inspection).
- ruff check passes with zero issues (Tier A: static analysis).
- mypy strict passes with zero issues (Tier A: static analysis).
- bandit passes with zero issues (Tier A: static analysis).
- Test file follows mirror structure: `src/grippy/rules/sql_injection.py` -> `tests/test_grippy_rule_sql_injection.py` (Tier A).
- Test file exceeds 50 LOC minimum (158 LOC) (Tier A).
- Uses `ctx.added_lines_for()` helper -- consistent with rule-sinks and rule-crypto conventions.
- Uses `_is_comment()` for comment filtering -- same pattern as rule-crypto.
- Uses `break` for one-finding-per-line -- same pattern as rule-sinks.
- Shared `_SQL_KEYWORDS` constant composed into 4 patterns -- DRY.
- Calibration: matches all prior units at 9.

---

### 8. Documentation Accuracy

**Key question:** Do docstrings, comments, and docs match actual behavior?

**Score:** 7/10
**Evidence:**
- File-level docstring: "Rule 7: sql-injection-risk -- detect SQL queries built from untrusted input." (line 2) -- accurate (Tier C).
- Class docstring: "Detect SQL queries built via string interpolation." (line 51) -- accurate (Tier C).
- `_file_ext` has docstring: "Get file extension including the dot." -- accurate (Tier C).
- `_is_comment` has docstring: "Check if a line is a Python comment." -- accurate (Tier C).
- Inline comments on each pattern: "f-string or .format() with SQL keyword" (line 13), "%-formatting with SQL keyword" (line 19), "String concatenation with SQL keyword" (line 25), "cursor.execute/executemany with f-string" (line 31).
- Not 9: No usage examples. No documentation of the `_SQL_KEYWORDS` composition pattern. No explanation of why `_PERCENT_SQL` requires `\s*(?:\(|[a-zA-Z_])` after `%` (answer: to distinguish `%s` parameterized from `% variable` formatting).
- Calibration: matches rule-secrets (7), rule-workflows (7), rule-sinks (7), rule-traversal (7).

---

### 9. Performance

**Key question:** Is the unit efficient for its workload?

**Score:** 8/10
**Evidence:**
- 4 regex patterns compiled once at module load via `re.compile()` (Tier C: lines 14-34). All use `re.IGNORECASE` where needed. No per-invocation recompilation.
- `_SQL_KEYWORDS` is a raw string constant composed into patterns at module load -- single compilation (Tier C: line 11).
- Linear scan: O(files x lines x patterns). Each line tested against 4 patterns.
- `break` at line 77 short-circuits after first match per line -- avoids redundant pattern testing.
- File extension check (`_file_ext`) at entry provides early exit for non-Python files (Tier C: line 60).
- `_is_comment()` check before pattern matching provides early exit for comments (Tier C: line 63).
- `frozenset` for extension lookups: O(1) per file (Tier C: line 36).
- Not 9: No profiling data.
- Calibration: matches rule-secrets (8), rule-workflows (8), rule-sinks (8), rule-traversal (8).

---

### 10. Dead Code / Debt

**Key question:** Is the unit free of unused code and tracked debt?

**Score:** 9/10
**Evidence:**
- Zero `TODO` or `FIXME` comments (Tier A: grep search).
- All functions called: `SqlInjectionRule` registered in `RULE_REGISTRY` (registry.py), `_file_ext` at line 60, `_is_comment` at line 63 (Tier C: caller trace).
- All 4 compiled patterns used at line 65: `_FSTRING_SQL`, `_PERCENT_SQL`, `_CONCAT_SQL`, `_EXECUTE_FSTRING` (Tier C).
- `_PYTHON_EXTENSIONS` frozenset used at line 60 (Tier C).
- ruff detects no unused imports (Tier A).
- Not 10: F-SQL-001 identifies fixture matrix gaps -- not code debt, but tracked.
- Calibration: matches rule-secrets (9), rule-workflows (9), rule-sinks (9), rule-traversal (9).

---

### 11. Dependency Hygiene

**Key question:** Are unit boundaries clean with no circular or unnecessary deps?

**Score:** 9/10
**Evidence:**
- 2 internal dependencies: `grippy.rules.base` (RuleResult, RuleSeverity) and `grippy.rules.context` (RuleContext). Both are same-phase (Phase 1) sibling modules (Tier A: import inspection at lines 8-9).
- 1 external dependency: `re` (stdlib) (Tier A: import inspection at line 7).
- No circular imports (Tier A: ruff check).
- Lean imports: only `RuleContext` from context module (delegates line iteration to helper). Same pattern as rule-sinks and rule-crypto.
- Not 10: Has 2 internal dependencies. Necessary and clean but not zero.
- Calibration: matches rule-secrets (9), rule-workflows (9), rule-sinks (9), rule-traversal (9).
