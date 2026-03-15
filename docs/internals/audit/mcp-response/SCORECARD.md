<!-- SPDX-License-Identifier: MIT -->

# Audit Scorecard: mcp-response

**Audit date:** 2026-03-14
**Commit:** c415a22
**Auditor:** Claude Opus 4.6 (AI draft) / Nelson Spence (human reviewer)
**Unit type:** infrastructure (primary)
**Subprofile:** config

---

## Checklist

Infrastructure checklist (IN-01, IN-02) + Config subprofile (IN-C01, IN-C02).

| ID | Invariant | Status | Evidence |
|----|-----------|--------|----------|
| IN-01 | Missing config produces clear error | N/A | No configuration. Pure function serializers with no env vars, settings, or files. |
| IN-02 | Unit follows project conventions | PASS | SPDX header (mcp_response.py:1). ruff + mypy clean (CI). Test mirror: `test_grippy_mcp_response.py` (Tier A). |
| IN-C01 | Edge case inputs handled gracefully | PASS | `enrichment=None` (default) omits key — tested by 16 existing tests that all pass `None`. `enrichment` present — tested by `test_enrichment_serialized_when_present` (Tier A). `rule_findings=None` default — tested by `test_rule_findings_empty_by_default` (Tier A). |
| IN-C02 | AST/parsing operations do not crash on malformed input | N/A | No parsing. Pure dict construction from Pydantic-validated inputs. |

---

## Gate Rules

### Override Gates (force a specific status)

| Override Gate | Condition | Fired? |
|---|---|---|
| Critical finding | Any unresolved CRITICAL finding | No |
| Multi-HIGH block | 2+ unresolved HIGH findings (including provisional) | No |
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
| 1. Contract Fidelity | 8/10 | A | All functions typed with explicit returns. mypy strict clean. |
| 2. Robustness | 8/10 | A + C | No error paths needed — pure dict construction from validated inputs. |
| 3. Security Posture | 7/10 | A + C | No trust boundaries. Personality stripping verified by test. |
| 4. Adversarial Resilience | 7/10 | A + C | No untrusted input processed. Inputs are Pydantic-validated upstream. |
| 5. Auditability & Traceability | 6/10 | C | Deterministic pure functions — same input always produces same output. No logging. |
| 6. Test Quality | 8/10 | A | 18 tests, 3.27:1 test:source ratio. Positive, negative, edge case categories covered. |
| 7. Convention Adherence | 9/10 | A | SPDX, ruff, mypy strict, naming, test mirror. Calibration: matches ignore (9). |
| 8. Documentation Accuracy | 7/10 | C | Module docstring and per-function docstrings accurate. No stale references. |
| 9. Performance | 9/10 | C | O(n) list comprehensions over findings. No allocation beyond output dicts. Zero I/O. |
| 10. Dead Code / Debt | 9/10 | A + C | Zero TODOs. All 3 functions called (2 public by mcp_server.py, 1 internal by both). `_SEVERITY_NAMES` dict used by `_serialize_rule_finding`. |
| 11. Dependency Hygiene | 9/10 | A | 2 internal imports (schema, rules.base). 0 external. True config leaf. |
| **Overall** | **7.9/10** | | **Average of 11 dimensions** |

**Health status:** Adequate

**Determination:**
1. Average-based status: 7.9/10 falls in 6.0-7.9 range = **Adequate**
2. Override gates: None fired.
3. Ceiling gates: None fired. Average stands.
4. Suffixes: None. Dims 3 and 4 both have Tier A evidence (personality stripping test, enrichment test). No `(provisional)` needed.

**Override gates fired:** None
**Ceiling gates fired:** None

---

## Findings

No findings. Small serializer, low risk, clean code.

---

## Compound Chain Exposure

None identified. mcp-response does not participate in any known compound chain (CH-1 through CH-5). It serializes already-validated data (Pydantic `GrippyReview` from retry/agent, `RuleResult` from rule-engine) into JSON dicts consumed by mcp-server. It does not process untrusted input, post to external APIs, or modify system state.

---

## Dimension Details

### 1. Contract Fidelity

**Key question:** Do types, exports, and validation faithfully represent the unit's contract?

**Score:** 8/10
**Evidence:**
- mypy strict passes with zero issues (Tier A: static analysis).
- All 3 functions fully typed: `_serialize_rule_finding(r: RuleResult) -> dict[str, Any]`, `serialize_scan(...) -> dict[str, Any]`, `serialize_audit(...) -> dict[str, Any]` (Tier A: mypy).
- `_SEVERITY_NAMES` module-level constant is typed as `dict[int, str]` (mcp_response.py:15) (Tier C: code reading).
- Not 9: No Protocol classes. No runtime type checks (inputs are Pydantic-validated upstream, so runtime checks would be redundant).
- Calibration: matches schema (8) and ignore (8) — all have strict mypy, typed returns, no Protocols.

---

### 2. Robustness

**Key question:** Does the unit handle errors, retries, and edge cases correctly?

**Score:** 8/10
**Evidence:**
- Pure functions with no error paths to handle. Inputs are Pydantic-validated `GrippyReview` and `RuleResult` — invalid data is rejected before reaching this unit (Tier C: caller trace from mcp_server.py → serialize_scan/serialize_audit).
- `rule_findings` defaults to `None`, handled with `or []` (mcp_response.py:92) — no crash on missing optional (Tier A: `test_rule_findings_empty_by_default`).
- `enrichment` conditional: `if r.enrichment is not None` (mcp_response.py:29) — both branches tested (Tier A: `test_enrichment_serialized_when_present` + all existing tests pass None).
- `evidence` conditional: `if r.evidence is not None` (mcp_response.py:27) — tested with both present and absent (Tier A: `test_finding_serialization` lines 258, 266).
- Scored 8 (not 7) because the unit genuinely has no error conditions to handle — robustness ceiling is defined by input contract, which is fully covered.

---

### 3. Security Posture

**Key question:** Does the unit protect against injection, leakage, and unauthorized access?

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 7/10
**Evidence:**
- No trust boundaries owned (Tier A: registry.yaml confirms `boundaries: []`).
- Personality stripping is the only security-relevant behavior: `serialize_audit()` constructs output dict by explicit field selection — personality fields (`tone_register`, `opening_catchphrase`, `closing_line`, `disguise_used`, `ascii_art_key`) are never referenced (Tier A: `test_personality_fields_absent_from_audit` verifies all 5 fields absent; `test_strips_personality` verifies value-level absence).
- No secrets, no logging, no error messages, no hardcoded credentials.
- Not 8: No defense-in-depth needed — no attack surface. Score reflects "no exposure" rather than "strong defenses."

---

### 4. Adversarial Resilience

**Key question:** Can the unit resist adversarial input from untrusted PR content and prompt injection?

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 7/10
**Evidence:**
- Does not process untrusted input directly. All inputs are Pydantic-validated upstream: `GrippyReview` by retry.py's `_parse_response()`, `RuleResult` by rule-engine (Tier C: caller trace).
- Output is consumed by mcp_server.py which returns it as MCP tool response — no GitHub posting, no prompt injection vector (Tier C: caller trace).
- Personality stripping prevents internal prompt/persona content from leaking to AI consumers (Tier A: `test_personality_fields_absent_from_audit`).
- Not 8: No adversarial fixture matrix specific to this unit. Limited exposure makes dedicated adversarial testing low-value.

---

### 5. Auditability & Traceability

**Key question:** Can operators investigate failures, reproduce review results, and trace the decision path from input to output?

**Score:** 6/10
**Evidence:**
- Pure functions: deterministic, same input always produces same output. No randomness, no external state (Tier C: code reading).
- No logger defined — appropriate for a pure serializer with no failure modes, but limits operational visibility.
- Output structure is self-documenting: key names match domain concepts (`findings`, `score`, `verdict`, `metadata`).
- Not 7: No structured logging. No tracing of serialization decisions. Callers must infer behavior from return values.

---

### 6. Test Quality

**Key question:** Do tests verify meaningful behavior with good coverage?

**Score:** 8/10
**Evidence:**
- 18 tests across 3 test classes (Tier A: test_grippy_mcp_response.py).
- Test:source ratio of 3.27:1 (327 LOC tests / 100 LOC source).
- **Positive tests:** required keys, finding fields, score shape, verdict shape, metadata, rule findings included, enrichment serialization (Tier A).
- **Negative tests:** rule findings empty by default, diff_truncated default false (Tier A).
- **Edge case tests:** gate passed/failed, enrichment present vs absent, personality field-level stripping, profile passthrough, diff stats passthrough (Tier A).
- Calibration: matches ignore (8) — similar test:source ratio (3.27 vs 2.11) and category coverage.
- Not 9: No property-based testing. No adversarial fixture matrix (low value given no untrusted input processing).

---

### 7. Convention Adherence

**Key question:** Does the unit follow Grippy project patterns?

**Score:** 9/10
**Evidence:**
- SPDX header on both source and test file (Tier A: mcp_response.py:1, test_grippy_mcp_response.py:1).
- ruff check passes with zero issues (Tier A: static analysis).
- ruff format check passes (Tier A: static analysis).
- mypy strict passes with zero issues (Tier A: static analysis).
- Test file follows mirror structure: `src/grippy/mcp_response.py` → `tests/test_grippy_mcp_response.py` (Tier A).
- Test file exceeds 50 LOC minimum (327 LOC) (Tier A).
- Naming: snake_case for functions, `_UPPER_CASE` for module constant.
- Calibration: matches ignore (9) — both exemplary adherence.

---

### 8. Documentation Accuracy

**Key question:** Do docstrings, comments, and docs match actual behavior?

**Score:** 7/10
**Evidence:**
- Module docstring: "AI-facing response serializers for MCP tools. Strips personality fields from GrippyReview and produces dense JSON output suitable for programmatic consumption by AI agents." — accurate (Tier C: mcp_response.py:2-6).
- `_serialize_rule_finding()`: "Serialize a single deterministic rule finding." — accurate (Tier C: mcp_response.py:19).
- `serialize_scan()`: "Serialize ``scan_diff`` output (deterministic rule engine results)." — accurate (Tier C: mcp_response.py:48).
- `serialize_audit()`: "Serialize ``audit_diff`` output, stripping personality fields." — accurate (Tier C: mcp_response.py:65).
- Not 8: No usage examples. `_SEVERITY_NAMES` dict not documented beyond variable name.

---

### 9. Performance

**Key question:** Is the unit efficient for its workload?

**Score:** 9/10
**Evidence:**
- `serialize_scan()` and `serialize_audit()` are single-pass O(n) list comprehensions over findings (Tier C: code reading).
- `_serialize_rule_finding()` is O(1) per finding — fixed set of dict assignments (Tier C: code reading).
- Zero I/O, zero allocations beyond the output dicts, zero external calls.
- `_SEVERITY_NAMES` is a module-level dict lookup — O(1) (Tier C: mcp_response.py:15).
- Scored 9 (not 8) because the unit is optimal for its workload — pure dict construction with no room for improvement.
- Calibration: above ignore (8) — ignore does regex + pathspec matching; mcp-response does only dict construction.

---

### 10. Dead Code / Debt

**Key question:** Is the unit free of unused code and tracked debt?

**Score:** 9/10
**Evidence:**
- Zero `TODO` or `FIXME` comments (Tier A: grep search).
- All functions called: `serialize_scan` by mcp_server.py, `serialize_audit` by mcp_server.py, `_serialize_rule_finding` by both public functions (Tier C: caller trace).
- `_SEVERITY_NAMES` dict used by `_serialize_rule_finding` (mcp_response.py:22) (Tier C: code reading).
- All 4 severity entries in `_SEVERITY_NAMES` are reachable (RuleSeverity has 4 values: INFO=0, WARN=1, ERROR=2, CRITICAL=3) (Tier C: cross-reference with rules/base.py:17-20).
- Clean imports — ruff detects no unused imports (Tier A).

---

### 11. Dependency Hygiene

**Key question:** Are unit boundaries clean with no circular or unnecessary deps?

**Score:** 9/10
**Evidence:**
- Internal dependencies: `grippy.rules.base.RuleResult` and `grippy.schema.GrippyReview` (Tier A: import inspection at mcp_response.py:12-13).
- External dependencies: none beyond `typing` (stdlib) (Tier A: import inspection).
- No circular imports. Depends only on Phase 0 (schema) and Phase 1 (rules.base) — correct for a Phase 3 unit (Tier A: registry.yaml).
- True config leaf — consumed by mcp_server.py (Phase 4) only.
- Not 10: Two internal deps is minimal but not zero.
