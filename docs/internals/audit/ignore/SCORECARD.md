<!-- SPDX-License-Identifier: MIT -->

# Audit Scorecard: ignore

**Audit date:** 2026-03-13
**Commit:** 463ae6f
**Auditor:** Claude Opus 4.6 (AI draft) / Nelson Spence (human reviewer)
**Unit type:** infrastructure (primary)
**Subprofile:** config

---

## Checklist

Infrastructure checklist (IN-01, IN-02) + Config subprofile (IN-C01, IN-C02).

| ID | Invariant | Status | Evidence |
|----|-----------|--------|----------|
| IN-01 | Missing config produces clear error | PASS | `load_grippyignore()` returns `None` when file missing (test_grippy_ignore.py:53-54). Warning logged on parse failure with `exc_info=True` (ignore.py:56). |
| IN-02 | Unit follows project conventions | PASS | SPDX header (ignore.py:1). ruff + mypy clean (CI). Test mirror: `test_grippy_ignore.py` (Tier A). |
| IN-C01 | Edge case inputs handled gracefully | PASS | Empty file returns spec matching nothing (test_grippy_ignore.py:80-85). Comments-only file matches nothing (test_grippy_ignore.py:87-93). Invalid UTF-8 returns `None` (test_grippy_ignore.py:184-188). Malformed diff header kept (test_grippy_ignore.py:194-199). |
| IN-C02 | AST/parsing operations do not crash on malformed input | N/A | ignore.py uses regex (`NOGRIP_RE`) and `pathspec` library for gitignore-style matching — no AST parsing. |

---

## Gate Rules

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
| 1. Contract Fidelity | 8/10 | A | All functions typed, explicit returns, Optional/tuple patterns. Calibration: matches schema (8). |
| 2. Robustness | 7/10 | A + C | Broad except in `load_grippyignore` with warning log. Graceful degradation to None. |
| 3. Security Posture | 7/10 | C | No trust boundaries owned. Delegates to pathspec. No secrets, no sensitive data in logs. |
| 4. Adversarial Resilience | 6/10 | A + C | Regex is bounded (no ReDoS). Malformed pragma returns None (fail-closed). Limited exposure as config module. |
| 5. Auditability & Traceability | 6/10 | C | Logger defined. Warning with exc_info on parse failure. No structured context beyond that. |
| 6. Test Quality | 8/10 | A | 27 tests across 7 classes. Positive, negative, edge case, CI integration. 2.11:1 test:source ratio. |
| 7. Convention Adherence | 9/10 | A | SPDX, ruff, mypy strict, naming, test mirror. Calibration: matches schema (9). |
| 8. Documentation Accuracy | 7/10 | C | Docstrings on all public functions with Returns section. `parse_nogrip` has comprehensive 3-case doc. |
| 9. Performance | 8/10 | C | Compiled regex. PathSpec efficient. filter_diff O(n) in chunks. No unbounded operations. |
| 10. Dead Code / Debt | 9/10 | A + C | Zero TODOs. All functions called. Both compiled regexes used. Clean imports. |
| 11. Dependency Hygiene | 9/10 | A | External: pathspec (core dep). Internal: TYPE_CHECKING-only import of RuleContext. True leaf. |
| **Overall** | **7.6/10** | | **Average of 11 dimensions** |

**Health status:** Adequate (provisional)

**Determination:**
1. Average-based status: 7.6/10 falls in 6.0-7.9 range = **Adequate**
2. Override gates: None fired.
3. Ceiling gates: None fired. Average stands.
4. Suffixes: `(provisional)` — Dimensions 3, 5, 8, 9 are supported only by Tier C evidence.

**Override gates fired:** None
**Ceiling gates fired:** None

---

## Findings

| ID | Severity | Status | Title |
|----|----------|--------|-------|
| F-IGN-001 | LOW | RESOLVED | Empty .grippyignore file had no test coverage |
| F-IGN-002 | LOW | RESOLVED | Comments-only .grippyignore file had no test coverage |

### F-IGN-001: Empty .grippyignore file had no test coverage

**Severity:** LOW
**Status:** RESOLVED (this commit)
**Checklist item:** IN-C01

**Description:** An empty `.grippyignore` file was not tested. The `pathspec` library handles this correctly (returns a spec that matches nothing), but the behavior was unverified.

**Evidence:** Added `test_empty_grippyignore_returns_spec` (test_grippy_ignore.py:80-85).

### F-IGN-002: Comments-only .grippyignore file had no test coverage

**Severity:** LOW
**Status:** RESOLVED (this commit)
**Checklist item:** IN-C01

**Description:** A `.grippyignore` containing only comments and blank lines was not tested. Pathspec handles this correctly, but the behavior was unverified.

**Evidence:** Added `test_comments_only_grippyignore_matches_nothing` (test_grippy_ignore.py:87-93).

---

## Dimension Details

### 1. Contract Fidelity

**Key question:** Do types, exports, and validation faithfully represent the unit's contract?

**Score:** 8/10
**Evidence:**
- mypy strict passes with zero issues (Tier A: static analysis).
- All 5 public functions fully typed with explicit return annotations: `parse_nogrip() -> set[str] | bool | None`, `load_grippyignore() -> pathspec.PathSpec | None`, `filter_diff() -> tuple[str, int]`, `build_nogrip_index() -> dict[tuple[str, int], set[str] | bool]` (Tier A: mypy).
- `NOGRIP_RE` is module-level compiled regex (Tier C: code reading at ignore.py:19).
- Not 9: No Protocol classes for DI. No runtime type checks beyond what pathspec provides.
- Calibration: matches schema (8) — both have strict mypy, typed returns, no Protocols.

---

### 2. Robustness

**Key question:** Does the unit handle errors, retries, and edge cases correctly?

**Score:** 7/10
**Evidence:**
- `load_grippyignore()` wraps file read + parse in `try/except Exception` with `log.warning()` and `exc_info=True` — graceful degradation to `None` (ignore.py:52-57) (Tier C: code reading).
- `filter_diff()` handles empty/whitespace diffs early (ignore.py:70-71), missing `b/` in diff header (ignore.py:85-88), and all-excluded case returning empty string (ignore.py:96-97) (Tier A: tests at test_grippy_ignore.py:116-145).
- `parse_nogrip()` returns `None` for malformed targeted syntax (empty after colon) — fail-closed, never widens suppression (Tier A: test at test_grippy_ignore.py:45-49).
- Not 8: Broad `except Exception` rather than specific exceptions. No retry logic (not needed for single-shot file read).

---

### 3. Security Posture

**Key question:** Does the unit protect against injection, leakage, and unauthorized access?

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 7/10
**Evidence:**
- No trust boundaries owned (Tier A: registry.yaml confirms `boundaries: []`).
- `parse_nogrip()` fail-closed design: malformed targeted pragma returns `None` rather than widening to blanket suppression. This prevents attackers from crafting `# nogrip: ,` to suppress all rules (Tier A: test at test_grippy_ignore.py:45-49).
- `load_grippyignore()` does not log file contents — only logs parse failure existence (Tier C: code reading at ignore.py:56).
- No secrets, no hardcoded credentials, no error messages leaking internals.
- Not 8: No defense-in-depth (delegates entirely to pathspec for matching). No adversarial test fixtures specific to this module.

---

### 4. Adversarial Resilience

**Key question:** Can the unit resist adversarial input from untrusted PR content and prompt injection?

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 6/10
**Evidence:**
- `NOGRIP_RE` regex is bounded — no quantifier nesting, no catastrophic backtracking (Tier C: regex analysis of `r"#\s*nogrip(?::\s*(\S[^\n]*?))?\s*$"`).
- Malformed targeted pragma returns `None` (fail-closed), not `True` (Tier A: test_grippy_ignore.py:45-49).
- `filter_diff()` processes diff content which may contain attacker-controlled file paths. Paths are matched against pathspec — no execution, no injection vector (Tier C: code reading).
- Limited exposure: config module that reads local `.grippyignore` files (trusted) and processes diff text (partially untrusted).
- Not 7: No multi-layer defense. No data fencing. No adversarial test fixtures for this specific module (adversarial testing of the broader pipeline is in test_hostile_environment.py).

---

### 5. Auditability & Traceability

**Key question:** Can operators investigate failures, reproduce review results, and trace the decision path from input to output?

**Score:** 6/10
**Evidence:**
- Logger defined at module level: `log = logging.getLogger(__name__)` (ignore.py:16) (Tier C: code reading).
- `load_grippyignore()` logs parse failure with `log.warning("Failed to parse .grippyignore (non-fatal)", exc_info=True)` (ignore.py:56) (Tier C: code reading).
- `filter_diff()` returns excluded count enabling callers to log/report what was filtered (Tier A: all filter_diff tests verify count).
- Not 7: No structured logging. No logging in `parse_nogrip()` or `build_nogrip_index()`. Callers must infer behavior from return values.

---

### 6. Test Quality

**Key question:** Do tests verify meaningful behavior with good coverage?

**Score:** 8/10
**Evidence:**
- 27 tests across 7 test classes (Tier A: test_grippy_ignore.py).
- Test:source ratio of 2.11:1 (247 LOC tests / 117 LOC source).
- **Positive tests:** parse_nogrip bare/targeted (:17-18, :21-22, :25-26), load valid file (:56-61), filter preserving files (:101-114), CI integration (:149-173).
- **Negative tests:** no pragma (:29), string literal false positive (:31-32), empty after colon (:45-49), missing file (:53-54), None root (:78).
- **Edge case tests:** whitespace variations (:34-36), trailing whitespace (:38-39), rule IDs with spaces (:42-43), negation pattern (:63-68), preamble handling (:124-138), empty diff (:140-145), malformed header (:194-199), invalid UTF-8 (:184-188), empty file (:80-85), comments-only (:87-93).
- **Integration tests:** filter → rules → gate pass (:149-160), touched files after filter (:162-173), null-line finding (:202-231).
- Not 9: No property-based testing. No adversarial fixture matrix specific to ignore.

---

### 7. Convention Adherence

**Key question:** Does the unit follow Grippy project patterns?

**Score:** 9/10
**Evidence:**
- SPDX header on both source and test file (Tier A: ignore.py:1, test_grippy_ignore.py:1).
- ruff check passes with zero issues (Tier A: static analysis).
- ruff format check passes (Tier A: static analysis).
- mypy strict passes with zero issues (Tier A: static analysis).
- Test file follows mirror structure: `src/grippy/ignore.py` → `tests/test_grippy_ignore.py` (Tier A).
- Test file exceeds 50 LOC minimum (239 LOC) (Tier A).
- Naming conventions consistent: snake_case for functions, UPPER_CASE for module constants.
- Calibration: matches schema (9) — both exemplary adherence.

---

### 8. Documentation Accuracy

**Key question:** Do docstrings, comments, and docs match actual behavior?

**Score:** 7/10
**Evidence:**
- File-level docstring: "Suppression mechanisms: .grippyignore file filtering and # nogrip line pragma." (ignore.py:2) — accurate (Tier C).
- `parse_nogrip()` has comprehensive docstring documenting all 3 return cases (True, set, None) with explicit note about malformed-must-not-widen invariant (ignore.py:24-32) (Tier C).
- `load_grippyignore()`: "Load .grippyignore from repo root. Returns None if not found." (ignore.py:46) — accurate (Tier C).
- `filter_diff()`: detailed docstring including empty-diff semantics and return type (ignore.py:60-69) — accurate (Tier C).
- `build_nogrip_index()`: documents that it uses original line content, not truncated evidence (ignore.py:102-108) — important correctness note (Tier C).
- Not 8: No usage examples. `NOGRIP_RE` pattern not documented beyond variable name.

---

### 9. Performance

**Key question:** Is the unit efficient for its workload?

**Score:** 8/10
**Evidence:**
- `NOGRIP_RE` and `_FILE_HEADER_RE_SPLIT` are compiled at module level — no per-call compilation (Tier C: ignore.py:19, 21).
- `filter_diff()` is O(n) in diff chunks — single pass split + filter (Tier C: code reading at ignore.py:73-99).
- `pathspec.PathSpec.from_lines()` builds the matcher once; `match_file()` is O(patterns) per file (Tier C: library documentation).
- `build_nogrip_index()` is O(lines) — single pass through diff lines (Tier C: code reading at ignore.py:110-117).
- No unbounded operations, no nested loops, no I/O beyond initial file read.
- Not 9: No profiling data. Assessed by structural argument.

---

### 10. Dead Code / Debt

**Key question:** Is the unit free of unused code and tracked debt?

**Score:** 9/10
**Evidence:**
- Zero `TODO` or `FIXME` comments (Tier A: grep search).
- All functions called: `parse_nogrip` by `build_nogrip_index` and tests, `load_grippyignore` by review.py/mcp_server.py and tests, `filter_diff` by review.py/mcp_server.py and tests, `build_nogrip_index` by engine.py (Tier C: caller trace).
- Both compiled regexes used: `NOGRIP_RE` in `parse_nogrip`, `_FILE_HEADER_RE_SPLIT` in `filter_diff` (Tier A: static analysis).
- Clean imports — ruff detects no unused imports (Tier A).
- Not 10: TYPE_CHECKING import of RuleContext is used only by `build_nogrip_index` — correct but slightly unusual pattern.

---

### 11. Dependency Hygiene

**Key question:** Are unit boundaries clean with no circular or unnecessary deps?

**Score:** 9/10
**Evidence:**
- External dependencies: `pathspec` (core project dependency, used for gitignore-style matching), `re` and `logging` (stdlib) (Tier A: import inspection at ignore.py:4-11).
- Internal dependencies: `RuleContext` imported under `TYPE_CHECKING` only — zero runtime coupling to other grippy modules (Tier A: ignore.py:9, 13-14).
- True leaf module in the dependency graph at runtime.
- Not 10: `pathspec` is an external dependency, but it is well-justified (gitignore-style matching is complex and pathspec is the standard library for it).
