<!-- SPDX-License-Identifier: MIT -->

# Audit Scorecard: imports

**Audit date:** 2026-03-13
**Commit:** 6a85523
**Auditor:** Claude Opus 4.6 (AI draft) / Nelson Spence (human reviewer -- pending)
**Unit type:** infrastructure (primary)
**Subprofile:** config

---

## Checklist

Infrastructure checklist (IN-01, IN-02) + Config subprofile (IN-C01, IN-C02).

| ID | Invariant | Status | Evidence |
|----|-----------|--------|----------|
| IN-01 | Missing config produces clear error | PASS | `extract_imports()` returns `[]` on OSError (imports.py:77). `resolve_import_to_path()` returns `None` for non-existent modules (test_grippy_imports.py:25-27). No cryptic tracebacks. |
| IN-02 | Unit follows project conventions | PASS | SPDX header (imports.py:1). ruff + mypy clean (CI). Test mirror: `test_grippy_imports.py` (Tier A). |
| IN-C01 | Edge case inputs handled gracefully | PASS | Empty file returns `[]` (test_grippy_imports.py:172-175). Syntax error returns `[]` (test_grippy_imports.py:96-100). OSError returns `[]` (test_grippy_imports.py:177-180). Level exceeding depth returns `[]` (test_grippy_imports.py:155-160). Outside-repo resolution returns `[]` (test_grippy_imports.py:162-170). `from . import X` with `module=None` handled (test_grippy_imports.py:172-176). |
| IN-C02 | AST/parsing operations do not crash on malformed input | PASS | `ast.parse()` wrapped in `try/except (SyntaxError, OSError)` (imports.py:74-78). `relative_to()` wrapped in `try/except ValueError` in both `resolve_import_to_path` (imports.py:30-33, 38-41) and `_resolve_relative_import` (imports.py:61-63, 66-68). Regression tests verify all paths (Tier A). |

---

## Gate Rules

### Override Gates (force a specific status)

| Override Gate | Condition | Fired? |
|---|---|---|
| Critical finding | Any unresolved CRITICAL finding | No |
| Multi-HIGH block | 2+ unresolved HIGH findings (including provisional) | No |
| Security collapse | Security Posture < 2 | No (score: 6) |
| Adversarial collapse | Adversarial Resilience < 2 | No (score: 6) |

### Ceiling Gates (cap the best allowed status)

| Ceiling Gate | Condition | Fired? |
|---|---|---|
| Severity cap | Any unresolved HIGH finding | No |
| Security hard floor | Security Posture < 4 | No (score: 6) |
| Adversarial hard floor | Adversarial Resilience < 4 | No (score: 6) |
| Security soft floor | Security Posture < 6 | No (score: 6) |
| Adversarial soft floor | Adversarial Resilience < 6 | No (score: 6) |
| Accepted critical risk | Any ACCEPTED_RISK at CRITICAL | No |
| Accepted high risk | Any ACCEPTED_RISK at HIGH | No |

---

## Summary

| Dimension | Score | Evidence Tier | Notes |
|-----------|------:|:---:|-------|
| 1. Contract Fidelity | 7/10 | A | All functions typed, explicit returns. `Path | None` return patterns. |
| 2. Robustness | 8/10 | A | SyntaxError, OSError, ValueError all caught. Graceful degradation to None/[]. |
| 3. Security Posture | 6/10 | A + C | No trust boundaries owned. Path traversal via `relative_to()` now guarded. No secrets. |
| 4. Adversarial Resilience | 6/10 | C | Not exposed to untrusted input directly. Processes repo files only. Limited attack surface. |
| 5. Auditability & Traceability | 5/10 | C | Logger defined but unused. No structured logging. Pure-function returns are the only signal. |
| 6. Test Quality | 7/10 | A | 20 tests across 2 classes. 1.55:1 test:source ratio. Covers fix regression + edge cases. |
| 7. Convention Adherence | 9/10 | A | SPDX, ruff, mypy strict, naming, test mirror. Calibration: matches schema (9). |
| 8. Documentation Accuracy | 7/10 | C | Detailed docstrings on all public functions. File-level docstring accurate. |
| 9. Performance | 8/10 | C | AST parse is O(file). Import resolution O(search_roots). No unbounded operations. |
| 10. Dead Code / Debt | 8/10 | A + C | All functions called. Clean imports. Logger defined but unused (minor). |
| 11. Dependency Hygiene | 10/10 | A | Zero internal deps. External: ast, logging, pathlib (all stdlib). |
| **Overall** | **7.4/10** | | **Average of 11 dimensions** |

**Health status:** Adequate (provisional)

**Determination:**
1. Average-based status: 7.4/10 falls in 6.0-7.9 range = **Adequate**
2. Override gates: None fired.
3. Ceiling gates: None fired. Average stands.
4. Suffixes: `(provisional)` — Dimensions 4, 5, 8, 9 are supported only by Tier C evidence.

**Override gates fired:** None
**Ceiling gates fired:** None

---

## Findings

| ID | Severity | Status | Title |
|----|----------|--------|-------|
| F-IMP-001 | MEDIUM | RESOLVED | Uncaught ValueError in `_resolve_relative_import()` |
| F-IMP-002 | LOW | RESOLVED | Logger defined but never used |

### F-IMP-001: Uncaught ValueError in `_resolve_relative_import()`

**Severity:** MEDIUM
**Status:** RESOLVED (this commit)
**Checklist items:** IN-C01, IN-C02

**Description:** `_resolve_relative_import()` calls `candidate.relative_to(repo_root)` at lines 61 and 64 without a try/except. When the import level traversal escapes the repo root (e.g., `from .....deep import X` in a shallow directory), `relative_to()` raises `ValueError`. The sibling function `resolve_import_to_path()` already had this guard (lines 30-33, 38-41).

**Fix:** Wrapped both `relative_to()` calls in `try/except ValueError: return None`, matching the existing pattern in `resolve_import_to_path()`.

**Evidence:**
- Regression test `test_relative_import_level_exceeds_depth` (test_grippy_imports.py:155-160).
- Regression test `test_relative_import_outside_repo` (test_grippy_imports.py:162-170).

### F-IMP-002: Logger defined but never used

**Severity:** LOW
**Status:** RESOLVED (accepted as-is)

**Description:** `log = logging.getLogger(__name__)` is defined at imports.py:14 but no `log.*()` calls exist in the module. This is not dead code in the conventional sense — it follows the project convention of defining a logger at module scope for future use — but it is technically unused.

**Rationale for RESOLVED:** The logger follows project convention (ignore.py, local_diff.py, etc. all define one). Removing it would create churn. Leaving it is the correct choice.

---

## Dimension Details

### 1. Contract Fidelity

**Key question:** Do types, exports, and validation faithfully represent the unit's contract?

**Score:** 7/10
**Evidence:**
- mypy strict passes with zero issues (Tier A: static analysis).
- All 5 functions fully typed: `resolve_import_to_path() -> str | None`, `_resolve_relative_import() -> str | None`, `extract_imports() -> list[str]`, `_try_resolve() -> str | None`, `_find_search_roots() -> list[Path]` (Tier A: mypy).
- Return types correctly represent optional semantics: `None` for unresolvable, empty list for no imports.
- Not 8: No runtime type validation on inputs. `module` parameter accepts arbitrary strings without validation. No Pydantic or Protocol usage. Below schema (8) due to no input validation.

---

### 2. Robustness

**Key question:** Does the unit handle errors, retries, and edge cases correctly?

**Score:** 8/10
**Evidence:**
- `extract_imports()` catches `(SyntaxError, OSError)` from `file_path.read_text()` and `ast.parse()`, returning `[]` (imports.py:74-78) (Tier A: test at test_grippy_imports.py:96-100, 177-180).
- `resolve_import_to_path()` catches `ValueError` from `relative_to()` on both `.py` and `__init__.py` paths (imports.py:30-33, 38-41) (Tier A: tests at test_grippy_imports.py:33-66).
- `_resolve_relative_import()` now catches `ValueError` from `relative_to()` on both paths (imports.py:61-63, 66-68) (Tier A: tests at test_grippy_imports.py:155-170).
- Level traversal (`pkg_dir.parent` in loop) safely walks to filesystem root without crashing (Tier A: test_relative_import_level_exceeds_depth).
- Not 9: No error taxonomy. No logging of error conditions (logger defined but unused).

---

### 3. Security Posture

**Key question:** Does the unit protect against injection, leakage, and unauthorized access?

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 6/10
**Evidence:**
- No trust boundaries owned (Tier A: registry.yaml confirms `boundaries: []`).
- `relative_to()` guards (F-IMP-001 fix) prevent path confusion when resolved candidates escape repo root — returns `None` instead of an error or a path outside the expected tree (Tier A: test at test_grippy_imports.py:162-170).
- Module processes repo files only (not PR content). Input is a `Path` + `Path` (file_path, repo_root) — not user-controlled strings.
- No secrets, no logging of paths or content, no error messages leaking internals.
- Not 7: No defense-in-depth. No adversarial considerations (module is not exposed to untrusted input). No trust boundary ownership.

---

### 4. Adversarial Resilience

**Key question:** Can the unit resist adversarial input from untrusted PR content and prompt injection?

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 6/10
**Evidence:**
- Module is not directly exposed to untrusted PR content. It processes local repo files at index time, not PR diff content (Tier C: caller trace — `extract_imports` is called by `graph_store.py` during codebase indexing).
- `ast.parse()` processes repo files that already exist on disk — these are trusted content, not attacker-controlled (Tier C).
- The `relative_to()` ValueError guard prevents an attacker who can create deeply nested files from causing unhandled exceptions during indexing (defensive, not security-critical).
- Not 7: No data fencing needed (no untrusted input). No adversarial test fixtures (appropriate given no adversarial exposure).

---

### 5. Auditability & Traceability

**Key question:** Can operators investigate failures, reproduce review results, and trace the decision path from input to output?

**Score:** 5/10
**Evidence:**
- Logger defined at module level: `log = logging.getLogger(__name__)` (imports.py:14) (Tier C).
- No `log.*()` calls anywhere in the module. Failures are communicated via return values (`None` or `[]`) only.
- Pure functions with deterministic outputs — given the same file system state, `extract_imports()` always returns the same result (Tier C).
- Not 6: No logging of skipped imports, unresolvable modules, or error conditions. Operators cannot trace import resolution without adding debug logging.

---

### 6. Test Quality

**Key question:** Do tests verify meaningful behavior with good coverage?

**Score:** 7/10
**Evidence:**
- 20 tests across 2 test classes (Tier A: test_grippy_imports.py).
- Test:source ratio of 1.55:1 (204 LOC tests / 132 LOC source).
- **Positive tests:** dotted module (:13-17), package init (:19-23), import statement (:70-78), from import (:80-88), relative import (:102-109), parent level (:120-130), relative to package (:132-143).
- **Negative tests:** unresolvable (:25-27), stdlib (:29-31), syntax error (:96-100), unresolvable relative (:145-153).
- **Edge case tests:** ValueError fallback for .py (:33-49), ValueError fallback for __init__.py (:51-66), deduplication (:111-118), level exceeds depth (:155-160), outside repo (:162-170), `from . import` with None module (:172-176), empty file (:178-181), OSError (:183-186).
- Not 8: No adversarial fixtures (appropriate — module not exposed to untrusted input). Below schema (8) due to no integration tests and lower test:source ratio.

---

### 7. Convention Adherence

**Key question:** Does the unit follow Grippy project patterns?

**Score:** 9/10
**Evidence:**
- SPDX header on both source and test file (Tier A: imports.py:1, test_grippy_imports.py:1).
- ruff check passes with zero issues (Tier A).
- ruff format check passes (Tier A).
- mypy strict passes with zero issues (Tier A).
- Test file follows mirror structure: `src/grippy/imports.py` → `tests/test_grippy_imports.py` (Tier A).
- Test file exceeds 50 LOC minimum (204 LOC) (Tier A).
- Naming conventions consistent: snake_case for functions, leading underscore for private functions.
- Calibration: matches schema (9).

---

### 8. Documentation Accuracy

**Key question:** Do docstrings, comments, and docs match actual behavior?

**Score:** 7/10
**Evidence:**
- File-level docstring: "Python import extraction for dependency graph edges." (imports.py:2-6) — accurate, includes note about stdlib/third-party skip behavior (Tier C).
- `resolve_import_to_path()`: detailed docstring covering both module.py and module/__init__.py resolution paths (imports.py:21-25) — accurate (Tier C).
- `extract_imports()`: documents deduplication, skip behavior, and graceful syntax error handling (imports.py:69-73) — accurate (Tier C).
- `_resolve_relative_import()`: one-line docstring (imports.py:52) — accurate but minimal.
- Inline comment `# Common patterns: src/, lib/, .` in `_find_search_roots` (imports.py:122) — accurate (Tier C).
- Not 8: Private functions have minimal docstrings. No usage examples.

---

### 9. Performance

**Key question:** Is the unit efficient for its workload?

**Score:** 8/10
**Evidence:**
- `extract_imports()` parses each file once with `ast.parse()`, then walks the tree once with `ast.walk()` — O(AST nodes) (Tier C: imports.py:74-106).
- `_find_search_roots()` checks 3 hardcoded candidates — O(1) (Tier C: imports.py:118-126).
- `_try_resolve()` iterates search roots (max 3) × 2 filesystem checks per root — bounded (Tier C).
- Deduplication via `dict.fromkeys()` preserves insertion order with O(n) (Tier C: imports.py:106).
- No unbounded loops, no recursive descent, no I/O beyond file read + `is_file()` checks.
- Not 9: No profiling data. `_find_search_roots()` could cache results across calls but doesn't need to (called once per file, callers batch at higher level).

---

### 10. Dead Code / Debt

**Key question:** Is the unit free of unused code and tracked debt?

**Score:** 8/10
**Evidence:**
- Zero `TODO` or `FIXME` comments (Tier A: grep search).
- All 5 functions called: `extract_imports` by graph_store.py, `resolve_import_to_path` by graph_store.py, `_resolve_relative_import` by `extract_imports`, `_try_resolve` by `extract_imports`, `_find_search_roots` by `extract_imports` (Tier C: caller trace).
- ruff detects no unused imports (Tier A).
- Minor: `log` variable defined but never used (F-IMP-002). Accepted as project convention.
- Not 9: Unused logger is technically dead code, preventing a perfect score.

---

### 11. Dependency Hygiene

**Key question:** Are unit boundaries clean with no circular or unnecessary deps?

**Score:** 10/10
**Evidence:**
- Zero internal dependencies: imports.py imports nothing from `grippy.*` (Tier A: static analysis at imports.py:8-12).
- External dependencies are all stdlib: `ast`, `logging`, `pathlib` (Tier A).
- True leaf module — depended on by graph_store.py, depends on nothing within the project.
- No leaky abstractions: all functions accept/return stdlib types (`Path`, `str`, `list`, `None`).
- This is the optimal dependency structure for a utility module.
