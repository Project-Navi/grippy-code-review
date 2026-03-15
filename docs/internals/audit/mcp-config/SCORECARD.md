<!-- SPDX-License-Identifier: MIT -->

# Audit Scorecard: mcp-config

**Audit date:** 2026-03-15
**Commit:** 6216aca
**Auditor:** Claude Opus 4.6 (AI draft) / Nelson Spence (human reviewer)
**Unit type:** infrastructure (primary)
**Subprofile:** config

---

## Checklist

Infrastructure checklist (IN-01, IN-02) + Config subprofile (IN-C01, IN-C02).

| ID | Invariant | Status | Evidence |
|----|-----------|--------|----------|
| IN-01 | Missing config produces clear error | PASS | Missing file: `_load_config` returns `{}`, `add_to_client` creates new file. Missing config path (unsupported client): returns `None`/`False`. Error path is silent but clear — returns empty/false, never crashes (Tier A: `test_is_configured_no_file`, `test_add_returns_false_on_none_path`, `test_missing_file_returns_empty_dict`). |
| IN-02 | Unit follows project conventions | PASS | SPDX header (mcp_config.py:1). ruff + mypy clean (CI). Test mirror: `test_grippy_mcp_config.py` (Tier A). |
| IN-C01 | Edge case inputs handled gracefully | PASS | Malformed JSON → `{}` (Tier A: `test_malformed_json_returns_empty_dict`). Non-dict root → `{}` (Tier A: `test_non_dict_root_returns_empty_dict`). Missing file → `{}` (Tier A: `test_missing_file_returns_empty_dict`). None config path → `False` (Tier A: `test_add_returns_false_on_none_path`, `test_remove_returns_false_on_none_path`). |
| IN-C02 | AST/parsing no crash on malformed input | PASS | JSON parsing via `json.loads` catches `JSONDecodeError` (mcp_config.py:155). Non-dict root checked with `isinstance` (mcp_config.py:157-158). Both tested directly (Tier A). |

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
| 1. Contract Fidelity | 8/10 | A | All functions typed. mypy strict clean. `MCPClient` Enum. |
| 2. Robustness | 8/10 | A + C | Graceful degradation on all paths. Returns `None`/`False`/`{}`. |
| 3. Security Posture | 7/10 | A + C | No trust boundaries. Clean file I/O with UTF-8. |
| 4. Adversarial Resilience | 7/10 | C | No untrusted input. Programmer-provided inputs only. |
| 5. Auditability & Traceability | 6/10 | C | No logging. Return values clear but no operational visibility. |
| 6. Test Quality | 7/10 | A | 22 tests, 1.38:1 ratio. Positive/negative/edge cases. Platform coverage. |
| 7. Convention Adherence | 9/10 | A | SPDX, ruff, mypy strict, test mirror. Calibration: matches ignore (9). |
| 8. Documentation Accuracy | 8/10 | C | All functions have accurate docstrings with returns documented. |
| 9. Performance | 8/10 | C | Simple JSON I/O. O(1) per function. No unnecessary allocations. |
| 10. Dead Code / Debt | 9/10 | A + C | Zero TODOs. All functions called. `pragma: no cover` on unreachable else. |
| 11. Dependency Hygiene | 9/10 | A | stdlib only. Zero internal grippy deps. True leaf node. |
| **Overall** | **7.8/10** | | **Average of 11 dimensions** |

**Health status:** Adequate

**Determination:**
1. Average-based status: 7.8/10 falls in 6.0-7.9 range = **Adequate**
2. Override gates: None fired.
3. Ceiling gates: None fired. Average stands.
4. Suffixes: None. No trust boundaries, no untrusted input. Dims 3 and 4 reflect absence of exposure.

**Override gates fired:** None
**Ceiling gates fired:** None

---

## Findings

No findings. Clean config utility with comprehensive graceful degradation.

---

## Compound Chain Exposure

None identified. mcp-config does not participate in any known compound chain (CH-1 through CH-5). It manages local JSON config files for MCP clients. It does not process untrusted input, touch the review pipeline, or interact with external APIs.

---

## Dimension Details

### 1. Contract Fidelity

**Score:** 8/10
**Evidence:**
- mypy strict passes with zero issues (Tier A: CI).
- All public functions typed with explicit returns: `get_config_path(...) -> Path | None`, `get_available_clients() -> list[MCPClient]`, `generate_server_entry(...) -> dict[str, Any]`, `add_to_client(...) -> bool`, `remove_from_client(...) -> bool`, `is_configured(...) -> bool` (Tier A: mypy).
- `MCPClient` uses `Enum` for client discrimination — exhaustive by construction (Tier C: mcp_config.py:18-23).
- Not 9: No Protocol classes or runtime type checks. Inputs are simple types; validation is structural (isinstance check on JSON root).
- Calibration: matches ignore (8) and mcp-response (8).

---

### 2. Robustness

**Score:** 8/10
**Evidence:**
- `_load_config`: catches `FileNotFoundError` and `JSONDecodeError` → returns `{}`. Non-dict root → returns `{}`. Three paths tested directly (Tier A: `TestLoadConfig` — 3 tests).
- `add_to_client` / `remove_from_client` / `is_configured`: catch `OSError` → return `False`. `None` config path short-circuits before I/O (Tier A: `test_add_returns_false_on_none_path`, `test_remove_returns_false_on_none_path`).
- `_save_config`: creates parent dirs with `mkdir(parents=True, exist_ok=True)` — no crash on missing parents (Tier A: `test_add_creates_config` verifies end-to-end).
- `get_available_clients`: skips `None` config paths (mcp_config.py:59-60) — no crash on unsupported platform for a client.
- Not 9: No retry logic (not needed for local file I/O). No resource cleanup (no open file handles — uses `read_text`/`write_text`).

---

### 3. Security Posture

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 7/10
**Evidence:**
- No trust boundaries (Tier A: `registry.yaml` confirms `boundaries: []`).
- File I/O is local config management only — reads/writes JSON in user-controlled directories (home dir, XDG config). No untrusted input from PR content or network (Tier C: code reading).
- Uses UTF-8 encoding consistently for reads and writes (mcp_config.py:154, 168) (Tier C: code reading).
- `_save_config` writes pretty-printed JSON with trailing newline — no injection vector (Tier C: code reading).
- Not 8: No attack surface to defend. Score reflects absence of exposure rather than active defense.

---

### 4. Adversarial Resilience

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 7/10
**Evidence:**
- Does not process untrusted input. All inputs are programmer-provided: `MCPClient` enum values, `dict[str, Any]` server entries, `Path` objects (Tier C: code reading).
- Config file content is treated as untrusted (via `_load_config` → `isinstance` check) — but this is local user config, not attacker-controlled (Tier C: code reading).
- Not 8: No adversarial fixture matrix. Limited exposure makes dedicated adversarial testing low-value.

---

### 5. Auditability & Traceability

**Score:** 6/10
**Evidence:**
- No logger defined. All functions return success/failure as typed values (`bool`, `dict`, `Path | None`) — clear but not observable (Tier C: code reading).
- Deterministic behavior: same config file contents → same return values (Tier C: code reading).
- Not 7: No structured logging. Callers cannot distinguish "file missing" from "JSON malformed" from "non-dict root" — all return `{}` from `_load_config`.

---

### 6. Test Quality

**Score:** 7/10
**Evidence:**
- 22 tests across 5 test classes. Test:source ratio 1.38:1 (236 LOC / 169 LOC) (Tier A).
- **Positive:** config paths for all 3 clients, server entry generation, add/remove/is_configured (Tier A).
- **Negative:** remove when not present, is_configured when no file, None config path (Tier A).
- **Edge cases:** malformed JSON, non-dict root, missing file, parent-only detection (Tier A).
- **Platform:** darwin, win32, linux config paths (Tier A: `TestGetConfigPath`).
- Not 8: Lower test:source ratio than peers (1.38 vs 1.87 for mcp-server). No adversarial fixtures (low-value for this unit).
- KRC-01 applicable: no adversarial test category. Low impact given no untrusted input processing.

---

### 7. Convention Adherence

**Score:** 9/10
**Evidence:**
- SPDX header (mcp_config.py:1) (Tier A).
- ruff check + format clean (Tier A: CI).
- mypy strict clean (Tier A: CI).
- Test mirror: `src/grippy/mcp_config.py` → `tests/test_grippy_mcp_config.py` (Tier A).
- Test file exceeds 50 LOC minimum (236 LOC) (Tier A).
- snake_case functions, UPPER_CASE not used (no module constants).
- Calibration: matches ignore (9) and mcp-response (9).

---

### 8. Documentation Accuracy

**Score:** 8/10
**Evidence:**
- Module docstring: "MCP client detection and registration." — accurate (Tier C: mcp_config.py:2).
- All 8 functions have docstrings. Returns documented where non-obvious (Tier C: code reading).
- `generate_server_entry`: documents both dev-mode and published-package paths with Returns section (Tier C: mcp_config.py:67-75).
- `_load_config`: "Returns an empty dict if the file is missing or contains invalid JSON." — accurate and important for callers (Tier C: mcp_config.py:149-151).
- Not 9: No usage examples. No invariant documentation.

---

### 9. Performance

**Score:** 8/10
**Evidence:**
- All functions are O(1) — single file read/write, single JSON parse/serialize (Tier C: code reading).
- `get_available_clients` is O(k) where k = 3 (enum members) — effectively constant (Tier C: code reading).
- Uses `Path.read_text()` and `Path.write_text()` — no open file handles to leak (Tier C: code reading).
- Not 9: File I/O is inherently slower than pure computation (cf. mcp-response at 9). Appropriate for the workload.
- Calibration: below mcp-response (9, pure computation), matches ignore (8, pathspec + regex).

---

### 10. Dead Code / Debt

**Score:** 9/10
**Evidence:**
- Zero `TODO` or `FIXME` comments (Tier A: grep search).
- All public functions called: by `__main__.py` (`get_available_clients`, `add_to_client`, `generate_server_entry`, `MCPClient`) and tests (all) (Tier C: caller trace).
- `# pragma: no cover` on unreachable else at mcp_config.py:51 — correct, all `MCPClient` variants handled above (Tier C: code reading).
- Clean imports — ruff detects no unused imports (Tier A).

---

### 11. Dependency Hygiene

**Score:** 9/10
**Evidence:**
- Dependencies: `json`, `os`, `sys`, `enum`, `pathlib`, `typing` — all stdlib (Tier A: import inspection).
- Zero internal grippy imports (Tier A: import inspection).
- Zero external dependencies (Tier A).
- True leaf node — consumed by `__main__.py` (Phase 4) only within grippy (Tier C: caller trace).
- Not 10: No Protocol-based decoupling. Not needed for this complexity level, but the rubric's 9-level criteria fit well.
- Calibration: matches mcp-response (9, 2 internal deps) — mcp-config is arguably cleaner (0 internal deps) but the difference is not worth a score distinction.
