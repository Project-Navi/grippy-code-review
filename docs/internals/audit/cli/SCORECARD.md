<!-- SPDX-License-Identifier: MIT -->

# Audit Scorecard: cli

**Audit date:** 2026-03-15
**Commit:** 6216aca
**Auditor:** Claude Opus 4.6 (AI draft) / Nelson Spence (human reviewer)
**Unit type:** infrastructure (primary)
**Subprofile:** boundary

---

## Checklist

Infrastructure checklist (IN-01, IN-02) + Boundary subprofile (IN-B01, IN-B02, IN-B04).

| ID | Invariant | Status | Evidence |
|----|-----------|--------|----------|
| IN-01 | Missing config produces clear error | PASS | Missing `--transport`: interactive prompt (explicit fallback path). Unknown `--clients` value: `sys.exit(1)` with message. No available clients: `sys.exit(1)` with message. Missing GITHUB_TOKEN for CI: fails in `review.main()` (Tier A: `test_install_unknown_client_exits`, `test_install_no_available_clients_exits`, `test_no_subcommand_requires_github_env`). |
| IN-02 | Unit follows project conventions | PASS | SPDX header (__main__.py:1). ruff + mypy clean (CI). Test mirror: `test_grippy_cli_mcp.py` (Tier A). |
| IN-B01 | Subprocess uses list args with timeout | N/A | No `subprocess.run` or `subprocess.Popen` in `__main__.py`. Delegates to `mcp_server.main()` and `review.main()` which handle their own subprocess calls (Tier C: code reading). |
| IN-B02 | CLI dispatch correct, invalid subcommands → helpful error | PASS | `serve` → `_serve()`, `install-mcp` → `_install_mcp()`, no subcommand → `review.main()`. Unknown args → argparse error with usage (Tier A: `test_main_dispatches_serve`, `test_main_dispatches_install_mcp`, `test_main_dispatches_legacy_ci`, `test_ci_review_help_exits_zero`). |
| IN-B04 | External system timeouts enforced | N/A | No external calls directly. Delegates to `mcp_server` (git timeout via local_diff) and `review` (full pipeline). Timeout responsibility belongs to those units (Tier C: code reading). |

---

## Gate Rules

### Override Gates

| Override Gate | Condition | Fired? |
|---|---|---|
| Critical finding | Any unresolved CRITICAL finding | No |
| Multi-HIGH block | 2+ unresolved HIGH findings | No |
| Security collapse | Security Posture < 2 | No (score: 7) |
| Adversarial collapse | Adversarial Resilience < 2 | No (score: 7) |

### Ceiling Gates

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
| 1. Contract Fidelity | 7/10 | A | All functions typed. Void returns on dispatch functions. |
| 2. Robustness | 7/10 | A + C | argparse handles most cases. One silent fallback on invalid input. |
| 3. Security Posture | 7/10 | A + C | No trust boundaries. Uses `getpass` for API keys. |
| 4. Adversarial Resilience | 7/10 | C | No untrusted input. CLI args from operator. |
| 5. Auditability & Traceability | 6/10 | C | Prints [OK]/[FAIL] per client. No structured logging. |
| 6. Test Quality | 8/10 | A | 29 tests, 1.78:1 ratio. All subcommands, interactive + subprocess. |
| 7. Convention Adherence | 9/10 | A | SPDX, ruff, mypy strict, test mirror. Lazy imports. |
| 8. Documentation Accuracy | 8/10 | C | Module docstring lists subcommands. Function docstrings accurate. |
| 9. Performance | 8/10 | C | Lazy imports avoid heavy deps on fast paths. |
| 10. Dead Code / Debt | 9/10 | A + C | Zero TODOs. All functions called. |
| 11. Dependency Hygiene | 8/10 | A + C | stdlib + 4 lazy internal imports. No import-time coupling. |
| **Overall** | **7.6/10** | | **Average of 11 dimensions** |

**Health status:** Adequate

**Determination:**
1. Average-based status: 7.6/10 falls in 6.0-7.9 range = **Adequate**
2. Override gates: None fired.
3. Ceiling gates: None fired. Average stands.
4. Suffixes: None. No trust boundaries, no untrusted input.

**Override gates fired:** None
**Ceiling gates fired:** None

---

## Findings

### F-CLI-01: Silent fallback to "local" transport on invalid interactive input

**Severity:** LOW
**Status:** OPEN
**Evidence tier:** C (code reading)

**Location:** `src/grippy/__main__.py:113-116`

**Current behavior:**
```python
try:
    transport = transports[int(choice) - 1]
except (ValueError, IndexError):
    transport = "local"
```

When the user enters an invalid choice during interactive transport selection (e.g., "abc", "0", "99"), the code silently defaults to `"local"` without informing the user. The operator may not notice until they attempt `audit_diff` and discover the wrong transport is configured.

**Why it matters:** Masks operator intent. An operator who types "openai" (the name) instead of "1" (the index) gets silently configured for local mode. The mismatch would surface during first `audit_diff` call, not during install — a delayed error.

**Mitigating factors:** The install flow continues to collect transport-specific config (base URL for local, API key for cloud), so the mismatch would be partially visible during the same session. The default to "local" is safe (no API key needed, works offline).

**Suggested improvement:** Print the selected transport after resolution, or print a warning when falling back to default:
```python
except (ValueError, IndexError):
    transport = "local"
    print(f"  Invalid choice, defaulting to: {transport}")
```

---

## Compound Chain Exposure

None identified. cli (`__main__.py`) is a pure dispatch layer. It routes to `mcp_server.main()`, `review.main()`, and `mcp_config` functions. It does not process untrusted input, touch PR content, or participate in the review pipeline data flow. All 5 known chains (CH-1 through CH-5) operate entirely within the downstream modules.

---

## Dimension Details

### 1. Contract Fidelity

**Score:** 7/10
**Evidence:**
- mypy strict passes (Tier A: CI).
- All functions typed: `_serve(argv: list[str]) -> None`, `_install_mcp(argv: list[str]) -> None`, `main() -> None`, `_get_version() -> str` (Tier A: mypy).
- Not 8: Dispatch functions are void — contract is "call the right downstream function." No Pydantic models, no complex return types. Type annotations are correct but minimal.
- Calibration: below mcp-config (8) and ignore (8) which have richer return types.

---

### 2. Robustness

**Score:** 7/10
**Evidence:**
- argparse handles invalid flags/args → `SystemExit(2)` with usage (Tier A: `test_ci_review_help_exits_zero`, `test_serve_help_exits_zero`).
- Unknown `--clients` value → `sys.exit(1)` with message (__main__.py:153-155) (Tier A: `test_install_unknown_client_exits`).
- No available clients → `sys.exit(1)` with message (__main__.py:160-161) (Tier A: `test_install_no_available_clients_exits`).
- `add_to_client` failure → prints `[FAIL]` per client (__main__.py:181) (Tier A: `test_install_add_failure_prints_fail`).
- Silent fallback to "local" on invalid interactive transport input — see F-CLI-01.
- Not 8: The silent fallback (F-CLI-01) prevents full-marks robustness. Interactive client selection also lacks error handling on invalid numeric input (__main__.py:169 — `int(x)` can raise `ValueError`), though this produces a clear traceback.

---

### 3. Security Posture

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 7/10
**Evidence:**
- No trust boundaries (Tier A: `registry.yaml` confirms `boundaries: []`).
- API keys collected via `getpass.getpass()` (__main__.py:142) — not echoed to terminal (Tier A: `test_install_interactive_transport` uses `patch("getpass.getpass")`).
- API keys stored in server entry env dict, written to client config files by `mcp_config.add_to_client`. Not logged, not printed (Tier C: code reading).
- `_PROJECT_ROOT` derived from `__file__` — no user-controlled path injection (Tier C: __main__.py:26).
- Not 8: No active defense needed. Score reflects absence of exposure.

---

### 4. Adversarial Resilience

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 7/10
**Evidence:**
- Does not process untrusted input. All inputs are operator-provided CLI arguments or interactive prompts (Tier C: code reading).
- `argparse` validates `--transport` choices and `--profile` choices (Tier A: argparse enforced).
- Not 8: No adversarial fixture matrix. Low-value for a CLI dispatch layer.

---

### 5. Auditability & Traceability

**Score:** 6/10
**Evidence:**
- Prints `[OK]` / `[FAIL]` per client during install (__main__.py:179-181) — visible feedback (Tier A: `test_install_add_failure_prints_fail`).
- Interactive prompts provide context: transport selection menu, client selection (Tier C: code reading).
- No structured logging. No logger defined (Tier C: code reading).
- Not 7: Cannot distinguish error causes programmatically. Output is human-readable only.

---

### 6. Test Quality

**Score:** 8/10
**Evidence:**
- 29 tests across 8 test classes. Test:source ratio 1.78:1 (427 LOC / 240 LOC) (Tier A).
- **Positive:** all 3 subcommands dispatch correctly, version flag, help flags (Tier A).
- **Negative:** unknown client exits, no available clients exits, missing GitHub env fails (Tier A).
- **Interactive flows:** transport selection (numeric), client selection (numeric, "all"), API key (getpass), base URL / model ID (Tier A).
- **Subprocess integration:** `serve --help`, `install-mcp --help`, legacy CI without env — real end-to-end via `subprocess.run` (Tier A).
- Not 9: No test for invalid interactive transport choice (relates to F-CLI-01). No adversarial fixtures.
- Calibration: matches mcp-response (8) and mcp-server (8).

---

### 7. Convention Adherence

**Score:** 9/10
**Evidence:**
- SPDX header (__main__.py:1) (Tier A).
- ruff check + format clean (Tier A: CI).
- mypy strict clean (Tier A: CI).
- Test mirror: `src/grippy/__main__.py` → `tests/test_grippy_cli_mcp.py` (Tier A).
- Test file exceeds 50 LOC minimum (427 LOC) (Tier A).
- Lazy imports follow project convention for entry points (Tier C: code reading).
- Calibration: matches ignore (9) and mcp-config (9).

---

### 8. Documentation Accuracy

**Score:** 8/10
**Evidence:**
- Module docstring lists all 3 subcommands with usage examples and explains RuntimeWarning avoidance rationale (__main__.py:2-13) (Tier C).
- `_serve`: "Start the Grippy MCP server over stdio." — accurate (Tier C).
- `_install_mcp`: "Interactive MCP client installer." — accurate (Tier C).
- `main`: "Console script entry point — dispatches subcommands." — accurate (Tier C).
- `_get_version`: "Return the package version string." — accurate (Tier C).
- Not 9: No invariant documentation. No usage examples beyond module docstring.

---

### 9. Performance

**Score:** 8/10
**Evidence:**
- Lazy imports for all 4 internal dependencies: `grippy.mcp_server` (__main__.py:42), `grippy.mcp_config` (__main__.py:98), `grippy.__version__` (__main__.py:191), `grippy.review` (__main__.py:234) (Tier C: code reading).
- `serve` path: imports only `mcp_server` — avoids loading `review`, `mcp_config`, LLM SDKs.
- `install-mcp` path: imports only `mcp_config` — stdlib-only, fastest path.
- `--version` path: imports only `grippy.__init__` — no heavy deps.
- Not 9: No profiling or streaming. Appropriate for CLI entry point.
- Calibration: matches mcp-config (8) — both do I/O-bound work efficiently.

---

### 10. Dead Code / Debt

**Score:** 9/10
**Evidence:**
- Zero `TODO` or `FIXME` comments (Tier A: grep search).
- All functions called: `main()` by console script entry point, `_serve` and `_install_mcp` by `main()`, `_get_version` by argparse version action (Tier C: caller trace).
- `_SUBCOMMANDS` set used in `main()` (__main__.py:198) for fast-path dispatch (Tier C: code reading).
- `_PROJECT_ROOT` used in `_install_mcp` with `--dev` flag (__main__.py:173) (Tier C: code reading).
- Clean imports — ruff detects no unused imports (Tier A).

---

### 11. Dependency Hygiene

**Score:** 8/10
**Evidence:**
- Import-time dependencies: `argparse`, `getpass`, `sys`, `pathlib` — all stdlib (Tier A: import inspection).
- Runtime dependencies (lazy): `grippy.mcp_server`, `grippy.mcp_config`, `grippy.review`, `grippy.__version__` — 4 internal (Tier A: import inspection).
- All internal imports are deferred to function scope — no import-time coupling (Tier C: code reading).
- No circular imports possible (leaf position in import graph for runtime deps) (Tier C).
- Not 9: 4 internal deps is appropriate for an orchestration entry point but more than mcp-config (0) or mcp-response (2).
