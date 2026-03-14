<!-- SPDX-License-Identifier: MIT -->

# Audit Scorecard: embedder

**Audit date:** 2026-03-13
**Commit:** c606d0a
**Auditor:** Claude Opus 4.6 (AI draft) / Nelson Spence (human reviewer)
**Unit type:** infrastructure (primary)
**Subprofile:** config

---

## Checklist

Infrastructure checklist (IN-01, IN-02) + Config subprofile (IN-C01, IN-C02).

| ID | Invariant | Status | Evidence |
|----|-----------|--------|----------|
| IN-01 | Missing config produces clear error | PASS | Unknown transport raises `ValueError` with descriptive message including the bad value and expected options (embedder.py:30-31). Tests at test_grippy_embedder.py:81-88, 90-96. |
| IN-02 | Unit follows project conventions | PASS | SPDX header (embedder.py:1). ruff + mypy clean (CI). Test mirror: `test_grippy_embedder.py` (Tier A). |
| IN-C01 | Edge case inputs handled gracefully | PASS | Empty string transport raises ValueError (test_grippy_embedder.py:90-96). Empty model ID passed through to Agno (test_grippy_embedder.py:98-107). Empty base_url passed through (test_grippy_embedder.py:109-118). Input validation is Agno's responsibility — embedder is a thin factory. |
| IN-C02 | AST/parsing operations do not crash on malformed input | N/A | No AST or parsing operations. Pure factory function with string matching. |

---

## Gate Rules

### Override Gates (force a specific status)

| Override Gate | Condition | Fired? |
|---|---|---|
| Critical finding | Any unresolved CRITICAL finding | No |
| Multi-HIGH block | 2+ unresolved HIGH findings (including provisional) | No |
| Security collapse | Security Posture < 2 | No (score: 6) |
| Adversarial collapse | Adversarial Resilience < 2 | No (score: 7) |

### Ceiling Gates (cap the best allowed status)

| Ceiling Gate | Condition | Fired? |
|---|---|---|
| Severity cap | Any unresolved HIGH finding | No |
| Security hard floor | Security Posture < 4 | No (score: 6) |
| Adversarial hard floor | Adversarial Resilience < 4 | No (score: 7) |
| Security soft floor | Security Posture < 6 | No (score: 6) |
| Adversarial soft floor | Adversarial Resilience < 6 | No (score: 7) |
| Accepted critical risk | Any ACCEPTED_RISK at CRITICAL | No |
| Accepted high risk | Any ACCEPTED_RISK at HIGH | No |

---

## Summary

| Dimension | Score | Evidence Tier | Notes |
|-----------|------:|:---:|-------|
| 1. Contract Fidelity | 7/10 | A | All params typed. Return type explicit. No runtime validation of passthrough params. |
| 2. Robustness | 7/10 | A + C | ValueError on unknown transport. Passthrough params delegate validation to Agno. |
| 3. Security Posture | 6/10 | C | No trust boundaries. API key param in function signature (not hardcoded). No logging of keys. |
| 4. Adversarial Resilience | 7/10 | C | Not exposed to untrusted input. Called only by internal config resolution. Minimal attack surface. |
| 5. Auditability & Traceability | 5/10 | C | No logger. No logging. Pure factory — traceable by return value only. |
| 6. Test Quality | 8/10 | A | 10 tests, 3.90:1 ratio. Covers both transports, error case, default key, passthrough. |
| 7. Convention Adherence | 9/10 | A | SPDX, ruff, mypy strict, naming, test mirror. Calibration: matches schema (9). |
| 8. Documentation Accuracy | 8/10 | C | Comprehensive docstring with Args/Returns sections. File-level docstring accurate. |
| 9. Performance | 9/10 | C | Single if/elif/raise — O(1). No I/O. No allocation beyond return value. |
| 10. Dead Code / Debt | 10/10 | A | Zero TODOs. Every line reachable. No dead branches. Clean imports. |
| 11. Dependency Hygiene | 8/10 | A | 1 external dep (agno). Zero internal deps. True leaf module. |
| **Overall** | **7.6/10** | | **Average of 11 dimensions** |

**Health status:** Adequate (provisional)

**Determination:**
1. Average-based status: 7.6/10 falls in 6.0-7.9 range = **Adequate**
2. Override gates: None fired.
3. Ceiling gates: None fired. Average stands.
4. Suffixes: `(provisional)` — Dimensions 2, 3, 4, 5, 8, 9 are supported only by Tier C evidence.

**Override gates fired:** None
**Ceiling gates fired:** None

---

## Findings

| ID | Severity | Status | Title |
|----|----------|--------|-------|
| F-EMB-001 | LOW | OPEN | No input validation on passthrough params |

### F-EMB-001: No input validation on passthrough params

**Severity:** LOW
**Status:** OPEN (accepted as design choice)
**Checklist item:** IN-C01

**Description:** `create_embedder()` passes `model`, `base_url`, and `api_key` directly to `OpenAIEmbedder()` without validation. Empty strings, None values (if type hints were relaxed), or invalid URLs would propagate to Agno, which may or may not validate them.

**Rationale for OPEN/LOW:** This is a deliberate design choice. The embedder module is a thin factory — its contract is to map transport names to Agno embedder configurations. Input validation of model IDs, URLs, and API keys is Agno's responsibility. Adding redundant validation here would couple Grippy to Agno's internal validation rules and create a maintenance burden when Agno's accepted inputs change.

**Tests confirming passthrough behavior:** test_grippy_embedder.py:98-107 (empty model), test_grippy_embedder.py:109-118 (empty base_url).

---

## Dimension Details

### 1. Contract Fidelity

**Key question:** Do types, exports, and validation faithfully represent the unit's contract?

**Score:** 7/10
**Evidence:**
- mypy strict passes with zero issues (Tier A: static analysis).
- Single public function `create_embedder()` fully typed: 4 params (all `str`), return type `OpenAIEmbedder` (Tier A: mypy).
- Default value for `api_key` parameter explicitly typed (Tier A: embedder.py:13).
- ValueError raised for unknown transport with descriptive message including the value and expected options (Tier A: test at test_grippy_embedder.py:81-88).
- Not 8: No runtime validation of passthrough params (model, base_url). Accepts arbitrary strings without checking format.

---

### 2. Robustness

**Key question:** Does the unit handle errors, retries, and edge cases correctly?

**Score:** 7/10
**Evidence:**
- Unknown transport raises `ValueError` with clear message: `f"Unknown transport: {transport!r}. Expected 'openai' or 'local'."` (embedder.py:30-31) (Tier A: tests at test_grippy_embedder.py:81-88, 90-96).
- Empty string transport correctly hits the ValueError branch (Tier A: test at test_grippy_embedder.py:90-96).
- Passthrough params delegate to Agno — if Agno raises, it bubbles up naturally (Tier C: design choice).
- Not 8: No retry logic (not needed). No graceful degradation (ValueError is the appropriate response). Score reflects simplicity of the module.

---

### 3. Security Posture

**Key question:** Does the unit protect against injection, leakage, and unauthorized access?

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 6/10
**Evidence:**
- No trust boundaries owned (Tier A: registry.yaml confirms `boundaries: []`).
- `api_key` parameter is accepted via function argument, not hardcoded. Default `"lm-studio"` is a placeholder for local LM Studio instances, not a real secret (Tier C: embedder.py:13).
- No logging — API key cannot leak via log output (Tier C).
- No I/O, no network calls, no file access — pure configuration factory.
- Not 7: No defense-in-depth. api_key value is not validated or masked. Relies entirely on callers to handle secrets appropriately.

---

### 4. Adversarial Resilience

**Key question:** Can the unit resist adversarial input from untrusted PR content and prompt injection?

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 7/10
**Evidence:**
- Not exposed to untrusted PR content. Called by agent.py during reviewer construction, with values sourced from environment variables or config — not from PR data (Tier C: caller trace).
- Attack surface is minimal: single function, three string params, two valid transport values.
- No string interpolation into commands, queries, or prompts.
- Higher than ignore/imports (6/6) because: zero code paths process external data, and the function is called exclusively with operator-controlled configuration values.
- Not 8: No adversarial test fixtures (appropriate given zero untrusted input exposure).

---

### 5. Auditability & Traceability

**Key question:** Can operators investigate failures, reproduce review results, and trace the decision path from input to output?

**Score:** 5/10
**Evidence:**
- No logger defined. No logging of transport selection, model choice, or embedder construction.
- ValueError message includes the transport value for debugging (embedder.py:30-31) (Tier C).
- Pure factory function — given same inputs, always returns same embedder configuration. Reproducible by definition.
- Not 6: No logging at all. Operators cannot trace which transport/model was selected without instrumenting the caller.

---

### 6. Test Quality

**Key question:** Do tests verify meaningful behavior with good coverage?

**Score:** 8/10
**Evidence:**
- 10 tests in 1 test class (Tier A: test_grippy_embedder.py).
- Test:source ratio of 3.90:1 (121 LOC tests / 31 LOC source) — highest ratio of all Phase 0 units.
- **Positive tests:** openai transport (:12-21), local transport with base_url (:23-33), local with default key (:35-43), local with custom key (:45-55).
- **Negative tests:** unknown transport (:81-88), empty string transport (:90-96).
- **Behavior tests:** openai ignores api_key (:57-68), openai doesn't set base_url (:70-79).
- **Edge case tests:** empty model ID passthrough (:98-107), empty base_url passthrough (:109-118).
- Not 9: No property-based testing. Single test class (no structural subdivision). Calibration: matches schema (8) — similar coverage depth.

---

### 7. Convention Adherence

**Key question:** Does the unit follow Grippy project patterns?

**Score:** 9/10
**Evidence:**
- SPDX header on both source and test file (Tier A: embedder.py:1, test_grippy_embedder.py:1).
- ruff check passes with zero issues (Tier A).
- ruff format check passes (Tier A).
- mypy strict passes with zero issues (Tier A).
- Test file follows mirror structure: `src/grippy/embedder.py` → `tests/test_grippy_embedder.py` (Tier A).
- Test file exceeds 50 LOC minimum (121 LOC) (Tier A).
- Error message uses f-string with `!r` for safe value quoting (embedder.py:30).
- Calibration: matches schema (9).

---

### 8. Documentation Accuracy

**Key question:** Do docstrings, comments, and docs match actual behavior?

**Score:** 8/10
**Evidence:**
- File-level docstring: "Embedder factory — selects Agno embedder based on transport mode." (embedder.py:2) — accurate (Tier C).
- `create_embedder()` has comprehensive docstring with Args section documenting all 4 parameters and Returns section (embedder.py:15-25) — accurate and complete (Tier C).
- Args descriptions match actual behavior: transport is documented as `"openai" or "local"`, base_url as "used only for local transport", api_key default documented (Tier C).
- Not 9: No usage examples. No invariants documented. No note about passthrough behavior (F-EMB-001).

---

### 9. Performance

**Key question:** Is the unit efficient for its workload?

**Score:** 9/10
**Evidence:**
- Single function with two if-branches and a raise — O(1) time and space (Tier C: embedder.py:26-31).
- No I/O, no network calls, no loops, no recursion.
- Only allocation is the `OpenAIEmbedder` return value — minimal memory.
- Called once per review session — not a hot path.
- Not 10: No profiling data. "Optimal for workload" is trivially true for a 6-line function body, but 10 requires measurement.

---

### 10. Dead Code / Debt

**Key question:** Is the unit free of unused code and tracked debt?

**Score:** 10/10
**Evidence:**
- Zero `TODO` or `FIXME` comments (Tier A: grep search).
- Every line of code is reachable: `transport == "openai"` → line 27, `transport == "local"` → line 29, else → line 30-31 (Tier A: 3 tests cover all 3 branches).
- Single import, single function — no orphaned code possible.
- ruff detects no unused imports (Tier A).
- 0 debt items.

---

### 11. Dependency Hygiene

**Key question:** Are unit boundaries clean with no circular or unnecessary deps?

**Score:** 8/10
**Evidence:**
- Zero internal dependencies: embedder.py imports nothing from `grippy.*` (Tier A: static analysis at embedder.py:6).
- Single external dependency: `agno.knowledge.embedder.openai.OpenAIEmbedder` — justified as the module's entire purpose is to configure this class (Tier A).
- True leaf module in the dependency graph.
- Not 9: Depends on a specific Agno class rather than a Protocol/interface — coupling is tight but appropriate for a factory module.
- Not 10: External dependency (agno) is heavier than stdlib-only modules like imports.py.
