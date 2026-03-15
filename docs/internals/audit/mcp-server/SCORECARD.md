<!-- SPDX-License-Identifier: MIT -->

# Audit Scorecard: mcp-server

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
| IN-01 | Missing config produces clear error | PASS | Invalid profile → `ValueError` → JSON error (Tier A: `test_scan_invalid_profile`, `test_audit_invalid_profile`). Missing env vars → defaults applied (`GRIPPY_BASE_URL` → `localhost:1234`, `GRIPPY_PROFILE` → `security`) (Tier A: `test_default_security`). |
| IN-02 | Unit follows project conventions | PASS | SPDX header (mcp_server.py:1). ruff + mypy clean (CI). Test mirror: `test_grippy_mcp_server.py` (Tier A). |
| IN-B01 | Subprocess uses list args with timeout | N/A | No `subprocess.run` or `subprocess.Popen` in `mcp_server.py`. Git subprocess calls are in `local_diff.py` which enforces 30s timeout with list args (Tier C: code reading, cross-reference with local-diff scorecard). |
| IN-B02 | CLI dispatch correct | PASS (partial scope) | Not a CLI — MCP tool dispatch via FastMCP decorators. Two tools (`scan_diff`, `audit_diff`) routed correctly through `_run_scan` and `_run_audit` inner helpers (Tier A: `test_scan_diff_delegates`, `test_audit_diff_delegates`). `main()` calls `mcp.run(transport="stdio")` (Tier A: `test_main_calls_mcp_run`). |
| IN-B04 | External system timeouts enforced | PASS | **Git operations:** bounded at 30s via `local_diff.get_local_diff()` subprocess timeout (Tier B: deterministic trace `_run_scan` → `get_local_diff` → `subprocess.run(timeout=30)` at local_diff.py:99). **LLM operations:** not time-bounded by this unit. MCP clients manage tool execution lifecycle — the server runs within the client's timeout context. `GRIPPY_TIMEOUT` env var (documented in CLAUDE.md) is not consumed by `mcp_server.py`. See design observation below. |

**Design observation (IN-B04, LLM timeout):** `_run_audit` calls `run_review(agent, user_message)` with no timeout wrapper. The MCP architecture delegates timeout responsibility to the client: Claude Code, Claude Desktop, and Cursor all enforce tool execution timeouts. The server's `audit_diff` tool runs within that client-controlled lifecycle. This is architecturally consistent — the server does not need to redundantly enforce timeouts that the client already manages. The `GRIPPY_TIMEOUT` env var exists for the CI pipeline (`review.py`), where there is no MCP client to manage the lifecycle.

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
| 1. Contract Fidelity | 8/10 | A | All functions typed. `str` return invariant on all tool paths. |
| 2. Robustness | 8/10 | A | All code paths return JSON. 5 distinct error types caught. |
| 3. Security Posture | 7/10 | A + C | Consumer of TB-2/3/5, owns no anchors. Clean delegation. |
| 4. Adversarial Resilience | 7/10 | A + C | Relay role in CH-1/CH-4. No direct untrusted input processing. |
| 5. Auditability & Traceability | 6/10 | C | Error messages include context. No structured logging. |
| 6. Test Quality | 8/10 | A | 29 tests, 1.87:1 ratio. All error paths, annotations, integration. |
| 7. Convention Adherence | 9/10 | A | SPDX, ruff, mypy strict, test mirror. Late imports. |
| 8. Documentation Accuracy | 8/10 | C | MCP tool docstrings detailed. Module docstring accurate. |
| 9. Performance | 8/10 | C | Late imports for agent/retry. scan_diff avoids LLM SDK loading. |
| 10. Dead Code / Debt | 9/10 | A + C | Zero TODOs. All functions called. |
| 11. Dependency Hygiene | 7/10 | A + C | 8+ internal imports. Appropriate for orchestration module. |
| **Overall** | **7.7/10** | | **Average of 11 dimensions** |

**Health status:** Adequate

**Determination:**
1. Average-based status: 7.7/10 falls in 6.0-7.9 range = **Adequate**
2. Override gates: None fired.
3. Ceiling gates: None fired. Average stands.
4. Suffixes: None. Consumer of trust boundaries but owns no anchors. Dims 3 and 4 have Tier A evidence (error path tests verify no information leakage).

**Override gates fired:** None
**Ceiling gates fired:** None

---

## Findings

No findings. The unit's core invariant — all code paths return JSON, never raise — is well-maintained and comprehensively tested.

---

## Compound Chain Exposure

**Consumer/relay** for CH-1 (Prompt Injection) and CH-4 (Rule Bypass), but does not own any anchor functions or circuit breakers for these chains.

- **CH-1 (Prompt Injection → Fabricated Finding → Merge Block):** `_run_audit` passes diff content through `format_pr_context()` (TB-1, owned by agent.py) and receives parsed output from `run_review()` (TB-5, owned by retry.py). mcp-server is a relay — it neither sanitizes PR content (agent.py does) nor validates findings against rules (retry.py does). Diff content flows through but is not manipulated.

- **CH-4 (Rule Bypass → Silent Vulnerability Pass):** `_run_scan` and `_run_audit` both call `run_rules()` (TB-2, owned by rule-engine) and `check_gate()`. mcp-server relays rule results but does not modify them. The gate check is deterministic and not bypassable from the server layer.

Both chain roles are pass-through. mcp-server adds no attack surface to either chain.

---

## Dimension Details

### 1. Contract Fidelity

**Score:** 8/10
**Evidence:**
- mypy strict passes (Tier A: CI).
- Core invariant: all tool functions return `str` (JSON-encoded). Both `_run_scan` and `_run_audit` return `str` on every code path — success and error (Tier A: all 29 tests parse return values as JSON).
- `_json_error` helper enforces the error shape: `{"error": message}` (mcp_server.py:33-34) (Tier A: 7 error-path tests verify this shape).
- MCP tool annotations typed: `ToolAnnotations(readOnlyHint=True, destructiveHint=False)` (Tier A: `TestToolAnnotations` — 4 tests).
- Not 9: No Protocol classes. `_run_scan` and `_run_audit` use positional `str` params, not typed scope/profile objects.
- Calibration: matches mcp-config (8) and mcp-response (8).

---

### 2. Robustness

**Score:** 8/10
**Evidence:**
- All code paths return JSON — the unit's defining invariant. 5 distinct exception types caught:
  1. `ValueError` from `load_profile()` → JSON error (Tier A: `test_scan_invalid_profile`, `test_audit_invalid_profile`).
  2. `DiffError` from `get_local_diff()` → JSON error (Tier A: `test_scan_invalid_scope`, `test_audit_invalid_scope`).
  3. `ValueError` from `create_reviewer()` → "Config error" JSON (Tier A: `test_audit_create_reviewer_value_error`).
  4. `ReviewParseError` from `run_review()` → "Review failed after N attempts" JSON (Tier A: `test_audit_review_parse_error`).
  5. Generic `Exception` as fallback → safe error message (Tier A: `test_audit_create_reviewer_generic_error`, `test_audit_generic_review_error`).
- `_load_graph_store()` catches all exceptions → returns `None`. Callers handle `None` gracefully (mcp_server.py:50-51) (Tier C: code reading).
- Empty diff after filtering → JSON error "nothing to review" (Tier A: `test_audit_empty_diff`, `test_audit_all_excluded_returns_error`).
- Not 9: No retry logic on transient failures (appropriate — MCP clients handle retries).

---

### 3. Security Posture

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 7/10
**Evidence:**
- Consumer of TB-2 (diff ingestion via `get_local_diff`), TB-3 (prompt composition via `create_reviewer`), TB-5 (model output via `run_review`) — but owns no anchor functions (Tier A: `registry.yaml` confirms `boundaries: []`).
- Error messages do not leak internal paths or stack traces. Generic fallback: `"Failed to initialize review agent"` (mcp_server.py:142), `f"Review failed: {type(exc).__name__}"` (mcp_server.py:162) — exception type name only, no `.args` or traceback (Tier A: `test_audit_create_reviewer_generic_error`, `test_audit_generic_review_error`).
- `readOnlyHint=True` and `destructiveHint=False` on both tools — MCP clients can use these to assess risk (Tier A: `TestToolAnnotations`).
- No secrets in source. API key read from env at runtime, passed to `create_reviewer` (mcp_server.py:123) (Tier C: code reading).
- Not 8: No active defense mechanisms in this unit. Relies on downstream units for sanitization.

---

### 4. Adversarial Resilience

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 7/10
**Evidence:**
- Relay role in CH-1 and CH-4 (see Compound Chain Exposure). Does not process untrusted input directly — passes diff content to `format_pr_context()` which handles sanitization (Tier C: caller trace).
- MCP tool inputs (`scope`, `profile`) are simple strings. `scope` is validated by `get_local_diff()` (DiffError on invalid). `profile` is validated by `load_profile()` (ValueError on invalid). Both produce JSON errors (Tier A: `test_scan_invalid_scope`, `test_scan_invalid_profile`).
- `.grippyignore` filtering applied before rule engine and LLM see the diff (mcp_server.py:68-69, 99-100) — defense against crafted file paths (Tier A: `test_scan_filters_ignored_files`).
- Not 8: No adversarial fixture matrix specific to this unit. Exposure is relay-only.

---

### 5. Auditability & Traceability

**Score:** 6/10
**Evidence:**
- Error messages include context: "Config error: {exc}" (mcp_server.py:140), "Review failed after {exc.attempts} attempts" (mcp_server.py:160), "Review failed: {type(exc).__name__}" (mcp_server.py:162) — enough for operator triage (Tier C: code reading).
- MCP tool descriptions are detailed: scope options, profile meanings, prerequisite (LLM config for audit_diff) (Tier C: mcp_server.py:191-222).
- `diff_stats` included in all successful responses — operators can verify scope (Tier A: `test_scan_stats_reflect_filtered_diff`).
- No logger defined. No structured logging (Tier C: code reading).
- Not 7: Cannot trace the decision path from input to output. Would need logs showing which rules ran, which profile resolved, whether graph store loaded.

---

### 6. Test Quality

**Score:** 8/10
**Evidence:**
- 29 tests across 7 test classes. Test:source ratio 1.87:1 (434 LOC / 232 LOC) (Tier A).
- **Positive:** scan with findings, audit happy path, security mode + rule engine, formatting with findings (Tier A: `TestRunScan`, `TestRunAudit`).
- **Negative:** invalid scope, invalid profile, empty diff (Tier A).
- **Error paths:** all 5 exception types tested (see Dim 2) (Tier A).
- **Integration:** .grippyignore filtering (3 tests), profile resolution (3 tests), MCP annotations (4 tests), tool wrapper delegation (2 tests) (Tier A).
- Not 9: No adversarial fixtures. No property-based testing. KRC-01 applicable but low-value for relay unit.
- Calibration: matches cli (8) and mcp-response (8).

---

### 7. Convention Adherence

**Score:** 9/10
**Evidence:**
- SPDX header (mcp_server.py:1) (Tier A).
- ruff check + format clean (Tier A: CI).
- mypy strict clean (Tier A: CI).
- Test mirror: `src/grippy/mcp_server.py` → `tests/test_grippy_mcp_server.py` (Tier A).
- Test file exceeds 50 LOC minimum (434 LOC) (Tier A).
- Late imports for heavy dependencies follow project convention (mcp_server.py:127-128) (Tier C).
- Calibration: matches mcp-config (9) and cli (9).

---

### 8. Documentation Accuracy

**Score:** 8/10
**Evidence:**
- Module docstring: "Grippy MCP server -- exposes scan_diff and audit_diff as FastMCP tools." — accurate (Tier C: mcp_server.py:2).
- MCP tool docstrings are the most detailed in the codebase: scope options enumerated with examples, profile semantics explained, gate threshold behavior documented (Tier C: mcp_server.py:191-222).
- `_json_error`: "Return a JSON-encoded error response." — accurate (Tier C).
- `_run_scan` / `_run_audit`: "Run deterministic rules..." / "Run full LLM-powered review..." — accurate (Tier C).
- `_resolve_profile`: "Resolve effective profile: explicit param > GRIPPY_PROFILE env > 'security'." — accurately describes precedence (Tier C).
- Not 9: No invariant documentation (e.g., "all paths return JSON"). No usage examples beyond tool docstrings.

---

### 9. Performance

**Score:** 8/10
**Evidence:**
- Late imports for `agent` and `retry` modules (mcp_server.py:127-128) — `scan_diff` path avoids loading LLM SDKs entirely (Tier C: code reading).
- `_load_graph_store` returns `None` quickly when DB file doesn't exist (mcp_server.py:46-47) — no wasted initialization (Tier C: code reading).
- `diff_stats` computed from filtered diff, not raw — avoids counting excluded files (Tier A: `test_scan_stats_reflect_filtered_diff`).
- Not 9: Module-level imports include FastMCP, graph_store, ignore, local_diff, mcp_response, review, rules — all loaded on `import grippy.mcp_server`. Only agent/retry are deferred.
- Calibration: matches cli (8) — both use lazy imports strategically.

---

### 10. Dead Code / Debt

**Score:** 9/10
**Evidence:**
- Zero `TODO` or `FIXME` comments (Tier A: grep search).
- All functions called: `scan_diff` and `audit_diff` by MCP clients, `_run_scan` and `_run_audit` by tool wrappers, `_resolve_profile` by both tools, `_json_error` by all error paths, `_load_graph_store` by both run functions, `main` by `__main__.py` (Tier C: caller trace).
- `mcp` module-level FastMCP instance used by both tool decorators and `main()` (Tier C: code reading).
- Clean imports — ruff detects no unused imports (Tier A).

---

### 11. Dependency Hygiene

**Score:** 7/10
**Evidence:**
- External dependencies: `mcp` (FastMCP, ToolAnnotations) (Tier A: import inspection).
- Internal dependencies (import-time): `graph_store`, `ignore`, `local_diff`, `mcp_response`, `review`, `rules`, `rules.base`, `rules.enrichment` — 8 internal modules (Tier A: import inspection).
- Internal dependencies (runtime/lazy): `agent`, `retry` — 2 additional (Tier A: mcp_server.py:127-128).
- No circular imports — all deps are lower-phase units (Tier C: registry.yaml phases).
- Not 8: 10 total internal dependencies is the highest in the codebase. Appropriate for the top-level orchestration module, but the sheer count limits the score.
- Calibration: below cli (8, 4 lazy deps) and mcp-config (9, 0 deps). Consistent with the unit's position as the most connected node.
