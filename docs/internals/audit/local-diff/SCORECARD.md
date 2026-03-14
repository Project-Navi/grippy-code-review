<!-- SPDX-License-Identifier: MIT -->

# Audit Scorecard: local-diff

**Audit date:** 2026-03-13
**Commit:** ea9be04
**Auditor:** Claude Opus 4.6 (AI draft) / Nelson Spence (human reviewer)
**Unit type:** infrastructure (primary)
**Subprofile:** boundary

---

## Gate Rules

### Override Gates (force a specific status)

| Override Gate | Condition | Fired? |
|---|---|---|
| Critical finding | Any unresolved CRITICAL finding | No |
| Multi-HIGH block | 2+ unresolved HIGH findings (including provisional) | No (0 HIGH findings) |
| Security collapse | Security Posture < 2 | No (score: 9) |
| Adversarial collapse | Adversarial Resilience < 2 | No (score: 8) |

### Ceiling Gates (cap the best allowed status)

| Ceiling Gate | Condition | Fired? |
|---|---|---|
| Severity cap | Any unresolved HIGH finding | No |
| Security hard floor | Security Posture < 4 | No (score: 9) |
| Adversarial hard floor | Adversarial Resilience < 4 | No (score: 8) |
| Security soft floor | Security Posture < 6 | No (score: 9) |
| Adversarial soft floor | Adversarial Resilience < 6 | No (score: 8) |
| Accepted critical risk | Any ACCEPTED_RISK at CRITICAL | No |
| Accepted high risk | Any ACCEPTED_RISK at HIGH | No |

---

## Summary

| Dimension | Score | Evidence Tier | Notes |
|-----------|------:|:---:|-------|
| 1. Contract Fidelity | 8/10 | A | All functions typed, mypy strict clean, DiffError exception, clear signatures |
| 2. Robustness | 8/10 | A | Typed exceptions, timeouts on both subprocess calls, graceful fallbacks |
| 3. Security Posture | 9/10 | A | shell=False, regex whitelist, dash-prefix guard, list args. Exemplary subprocess safety. |
| 4. Adversarial Resilience | 8/10 | A | 10 injection tests, flag injection, timeout tests. Strong defense in depth. |
| 5. Auditability & Traceability | 7/10 | A + C | DiffError messages descriptive. Subprocess args traceable. Deterministic. |
| 6. Test Quality | 8/10 | A | 30 tests. Positive, negative, adversarial (10 injection), edge cases. |
| 7. Convention Adherence | 9/10 | A | ruff, mypy strict, bandit clean. SPDX header. Mirror test structure. |
| 8. Documentation Accuracy | 8/10 | C | All functions docstringed with Args/Returns/Raises. Scope syntax documented. |
| 9. Performance | 8/10 | C | Compiled regex, subprocess with timeout. No unnecessary work. |
| 10. Dead Code / Debt | 9/10 | A + C | Zero TODOs, all functions called, clean imports. |
| 11. Dependency Hygiene | 10/10 | A | Zero internal grippy deps. 3 stdlib deps only (re, subprocess, pathlib). |
| **Overall** | **8.4/10** | | **Average of 11 dimensions** |

**Health status:** Healthy (provisional)

**Determination:**
1. Average-based status: 8.4/10 -> Healthy (8.0+ range)
2. Override gates: None fired.
3. Ceiling gates: None fired. All gate dimensions >= 6.
4. Suffixes: `(provisional)` -- dims 5, 8, 9 include Tier C evidence components.

**Override gates fired:** None
**Ceiling gates fired:** None

---

## Checklist: IN-01, IN-02, IN-B01, IN-B04

| ID | Verdict | Evidence | Notes |
|----|---------|----------|-------|
| IN-01 | PASS | Tier A: `test_invalid_scope`, `test_empty_scope`, `test_range_missing_dotdot` verify `DiffError`/`ValueError` with descriptive messages. `test_git_failure_raises_diff_error` verifies git stderr is surfaced. | Error messages include the failing value and explanation. |
| IN-02 | PASS | Tier A: ruff, mypy strict, bandit all clean. SPDX header present. | Follows all project conventions. |
| IN-B01 | PASS | Tier A: 10 injection tests in `TestParseScopeInjection`. Code path: `subprocess.run()` uses list args (no shell interpolation), `shell=False` explicit, `_validate_ref()` with `_REF_PATTERN` regex whitelist + dash-prefix check. | Defense in depth: regex whitelist blocks special characters, dash-prefix check blocks flag injection, `shell=False` prevents shell interpretation even if whitelist is bypassed. |
| IN-B02 | N/A | Ownership | local-diff is not a CLI dispatcher. CLI dispatch is owned by the `cli` unit (`__main__.py`). |
| IN-B03 | N/A | Ownership | local-diff is not an MCP client detector. MCP client detection is owned by `mcp-config`. |
| IN-B04 | PASS | Tier A: `test_git_timeout_raises_diff_error` (30s on `get_local_diff`), `test_returns_none_on_timeout` (5s on `get_repo_root`). Both tested with `subprocess.TimeoutExpired` mock. | Both subprocess calls have explicit timeouts. Timeout produces clean `DiffError` or `None`, not a crash. |

**N/A items:** 2/6 (IN-B02, IN-B03). These are not owned by local-diff. At 33%, well below the >50% reclassification threshold. local-diff is correctly typed as infrastructure/boundary -- it owns subprocess ingestion and ref validation.

---

## Findings

No findings. All checklist items PASS with Tier A evidence or are N/A by ownership design.

### Compound Chain Exposure

This unit participates in **CH-4 (Rule Bypass -> Silent Vulnerability Pass)**.

- **Role:** Origin. `get_local_diff()` is the TB-2 ingestion point for MCP mode. If diff acquisition fails or returns a truncated/empty diff, downstream rules have no content to scan.
- **Circuit breaker:** `get_local_diff()` raises `DiffError` on any git failure (non-zero exit) or timeout. It does not silently return empty on error -- the error propagates. Empty output from a successful git command (no staged changes) is a valid state, not a failure.
- **Residual risk:** If git itself is compromised or produces malformed diff output, this unit passes it through without validation. This is inherent -- the unit trusts git's diff format. The `parse_diff()` function in rule-engine handles malformed content gracefully (tested).

---

## Dimension Details

### 1. Contract Fidelity

**Key question:** Do types, exports, and validation faithfully represent the unit's contract?

**Score:** 8/10
**Evidence:**
- mypy strict passes with zero issues (Tier A: static analysis).
- `DiffError` custom exception provides typed error discrimination (Tier A).
- `parse_scope()` signature: `(scope: str) -> list[str]` -- returns argv list, raises `DiffError`/`ValueError` on invalid input (Tier A).
- `get_local_diff()` signature: `(scope: str = "staged") -> str` -- returns raw diff text, raises `DiffError` (Tier A).
- `get_repo_root()` signature: `() -> Path | None` -- returns `None` on failure instead of raising. Clean API for optional results.
- `diff_stats()` signature: `(diff: str) -> dict[str, int]` -- pure function, no side effects.
- `_validate_ref()` is private, raises `DiffError` for unsafe refs.
- Not 9: No Protocol classes. `dict[str, int]` return type for `diff_stats()` could be a typed dataclass.

---

### 2. Robustness

**Key question:** Does the unit handle errors, retries, and edge cases correctly?

**Score:** 8/10
**Evidence:**
- **Typed exceptions:** `DiffError` for all diff acquisition failures. `ValueError` raised by `parse_scope()` for invalid scope format (Tier A: tested).
- **Timeouts:** 30s on `get_local_diff()`, 5s on `get_repo_root()`. Both have explicit `timeout=` parameter to `subprocess.run()` (Tier A: tested with mocks).
- **Graceful fallback:** `get_repo_root()` catches `TimeoutExpired` and `OSError`, returns `None` (Tier A: 2 tests).
- **Error propagation:** `get_local_diff()` re-raises `TimeoutExpired` as `DiffError` with descriptive message. Git stderr surfaced in `DiffError` on non-zero exit (Tier A: tested).
- **Empty input:** `diff_stats("")` returns zeroes. `get_local_diff()` with empty staged returns empty string (Tier A: tested).
- Not 9: No retry logic (appropriate -- retrying git commands is unlikely to help for the failure modes encountered).

---

### 3. Security Posture

**Key question:** Does the unit protect against injection, leakage, and unauthorized access?

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 9/10
**Evidence:**
- **TB-2 anchor ownership:** `get_local_diff()` is a named anchor for TB-2 (diff/content ingestion boundary).
- **shell=False:** Both `subprocess.run()` calls use `shell=False` explicitly (Tier A: `test_returns_diff_output` verifies call args).
- **List arguments:** Command built as `list[str]`, never string interpolation (Tier A: `parse_scope()` tests verify output format).
- **Regex whitelist:** `_REF_PATTERN = re.compile(r"^[A-Za-z0-9\-_./~^]+$")` blocks all shell metacharacters (Tier A: 7 injection tests with `;`, backtick, `$()`, space).
- **Dash-prefix guard:** `if ref.startswith("-")` blocks flag injection (Tier A: 3 flag injection tests with `--no-patch`, `-p`, `--stat`).
- **Defense in depth:** Even if the regex whitelist were bypassed, `shell=False` + list args prevent shell interpretation. Two independent defense layers.
- **No sensitive data in output:** Function returns raw git output, no credentials or secrets involved.
- Calibration: Exceeds rule-secrets (7), ignore (7), imports (7). Exemplary subprocess safety with multi-layer defense.

---

### 4. Adversarial Resilience

**Key question:** Can the unit resist adversarial input from untrusted PR content and prompt injection?

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 8/10
**Evidence:**
- **10 injection tests (Tier A):** `TestParseScopeInjection` class covers:
  - Shell metacharacters: `;`, backtick, `$()` in commit refs (3 tests)
  - Shell metacharacters in range refs (3 tests)
  - Space injection (1 test)
  - Flag injection with `--`, `-` prefix (3 tests)
- **Timeout defense (Tier A):** Both subprocess calls have explicit timeouts preventing resource exhaustion attacks.
- **Input validation at boundary:** `_validate_ref()` is called on every user-provided ref before subprocess invocation.
- **Attack surface analysis:** User-controlled input enters only through the `scope` parameter of `parse_scope()`/`get_local_diff()`. All other functions (`diff_stats`, `get_repo_root`) take no untrusted input.
- Calibration: Exceeds rule-secrets (5), rule-engine (7). Stronger adversarial posture due to dedicated injection test suite and defense in depth.
- Not 9: No Unicode adversarial tests (though `_REF_PATTERN` implicitly rejects non-ASCII via character class). No property-based testing for ref validation.

---

### 5. Auditability & Traceability

**Key question:** Can operators investigate failures, reproduce review results, and trace the decision path from input to output?

**Score:** 7/10
**Evidence:**
- `DiffError` messages include the failing value: `f"Unsafe ref: {ref!r}"`, `f"Invalid scope: {scope!r}"`, `f"Invalid range (missing '..'): {range_str!r}"` (Tier A: tested).
- Git stderr is surfaced in `DiffError` on command failure: `raise DiffError(result.stderr.strip())` (Tier A: tested).
- Subprocess command construction is deterministic and inspectable: `parse_scope()` is a pure function returning the exact argv list.
- `diff_stats()` is a pure function -- same input produces same output.
- Not 8: No structured logging. No trace of which scope was requested when an error occurs upstream. The `DiffError` message is the only diagnostic.

---

### 6. Test Quality

**Key question:** Do tests verify meaningful behavior with good coverage?

**Score:** 8/10
**Evidence:**
- **Test count:** 30 tests across 5 test classes.
- **Source:test ratio:** 129 LOC source / 267 LOC tests = 2.07:1 test-to-source ratio (highest in project).
- **Fixture matrix categories:**
  - Positive: 6 valid scope tests (staged, commit:HEAD, commit:sha, commit:HEAD~3, range:main..HEAD, range:HEAD~3..HEAD).
  - Negative: 3 error tests (invalid scope, empty scope, missing dotdot).
  - Adversarial: 10 injection tests (7 metacharacter + 3 flag injection).
  - Edge cases: empty diff, timeout, OSError, non-git directory.
- **Mocking:** subprocess.run mocked at the correct boundary -- unit tests verify the unit's logic, not git's behavior.
- **Integration:** `test_returns_path_in_git_repo` tests real filesystem behavior (appropriate for this function).
- Calibration: Exceeds rule-secrets (6), rule-engine (7), schema (8). Strong adversarial coverage pushes above peers.
- Not 9: No property-based testing for ref validation. No coverage measurement cited.

---

### 7. Convention Adherence

**Key question:** Does the unit follow Grippy project patterns?

**Score:** 9/10
**Evidence:**
- SPDX header on source and test file (Tier A).
- ruff check passes with zero issues (Tier A).
- mypy strict passes with zero issues (Tier A).
- bandit passes with zero issues (Tier A).
- Test file follows mirror structure: `src/grippy/local_diff.py` -> `tests/test_grippy_local_diff.py` (Tier A).
- Test file exceeds 50 LOC minimum (267 LOC) (Tier A).
- Naming: `DiffError` (PascalCase exception), `get_local_diff` / `parse_scope` / `diff_stats` (snake_case functions), `_REF_PATTERN` (private constant).
- Calibration: matches schema (9), rule-secrets (9), rule-engine (9).

---

### 8. Documentation Accuracy

**Key question:** Do docstrings, comments, and docs match actual behavior?

**Score:** 8/10
**Evidence:**
- File-level docstring: "Local git diff acquisition for MCP server and CLI use." -- accurate (Tier C).
- `parse_scope()` docstring documents all 3 scope formats with examples, plus Raises (Tier C).
- `get_local_diff()` docstring: Args, Returns, Raises sections (Tier C).
- `get_repo_root()` docstring: "Return the git repo root, or None if not in a git repo." -- accurate (Tier C).
- `diff_stats()` docstring: "Compute basic statistics from a unified diff string." with Returns documentation (Tier C).
- `_validate_ref()` docstring: "Validate a git ref against injection attacks." with Raises (Tier C).
- `DiffError` docstring: "Raised when diff acquisition fails." -- accurate (Tier C).
- Not 9: No usage examples. No documented invariants for the ref validation regex pattern.

---

### 9. Performance

**Key question:** Is the unit efficient for its workload?

**Score:** 8/10
**Evidence:**
- `_REF_PATTERN` compiled once at module load (Tier C: local_diff.py:19).
- `parse_scope()`: O(1) string operations (startswith, split). No loops.
- `diff_stats()`: O(lines) single pass over diff text. No regex overhead.
- `get_local_diff()` and `get_repo_root()`: single subprocess call each, bounded by timeout.
- No unnecessary work -- functions do exactly what their contract requires and nothing more.
- Not 9: No profiling data.

---

### 10. Dead Code / Debt

**Key question:** Is the unit free of unused code and tracked debt?

**Score:** 9/10
**Evidence:**
- Zero `TODO` or `FIXME` comments (Tier A: grep search).
- All functions called: `get_local_diff` and `parse_scope` by mcp_server.py, `diff_stats` by mcp_response.py, `get_repo_root` by mcp_server.py, `DiffError` by callers and tests, `_validate_ref` by `parse_scope` (Tier C: caller trace).
- ruff detects no unused imports (Tier A).
- Not 10: `_validate_ref` is private but well-tested through public API. No debt.

---

### 11. Dependency Hygiene

**Key question:** Are unit boundaries clean with no circular or unnecessary deps?

**Score:** 10/10
**Evidence:**
- Zero internal grippy dependencies (Tier A: import inspection).
- 3 stdlib dependencies only: `re`, `subprocess`, `pathlib` (Tier A: import inspection).
- No circular imports (Tier A: ruff check).
- Completely self-contained module -- can be tested in isolation with zero grippy imports.
- Calibration: Unique among audited units. schema (10), ignore (9), imports (9) are the nearest peers.
