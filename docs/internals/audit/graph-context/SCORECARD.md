<!-- SPDX-License-Identifier: MIT -->

# Audit Scorecard: graph-context

**Audit date:** 2026-03-14
**Commit:** e4d24a8
**Auditor:** Claude Opus 4.6 (AI draft) / Nelson Spence (human reviewer)
**Unit type:** infrastructure (primary)
**Subprofile:** config (reclassified from state in v1.2 — 3/5 state items N/A)
**Methodology version:** 1.2

---

## Checklist: IN-01, IN-02, IN-C01, IN-C02

| ID | Invariant | Status | Evidence |
|----|-----------|--------|----------|
| IN-01 | Missing config produces clear error | N/A | No configuration. `build_context_pack()` takes a graph store instance + parameters. No env vars, no config files. |
| IN-02 | Unit follows project conventions | PASS | SPDX header (line 1). ruff clean, mypy strict clean (Tier A: CI). Test mirror: `test_grippy_graph_context.py` (Tier A). |
| IN-C01 | Edge case inputs handled gracefully | PASS | Empty graph returns ContextPack with all empty fields (Tier A: `test_empty_graph`). Empty touched_files returns pack with empty blast/findings (Tier A: `test_build_context_pack_no_touched_files`). Truncation at `max_chars` boundary verified (Tier A: `test_format_context_truncation_boundary`). |
| IN-C02 | AST/parsing operations do not crash on malformed input | PARTIAL | No AST operations. Query operations against unexpected graph state: closed connection propagates `ProgrammingError` (Tier A: `test_build_context_pack_graph_exception_propagates`). Docstring claims non-fatal behavior but function lacks try/except — see F-GC-001. |

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
| 1. Contract Fidelity | 7/10 | A | ContextPack dataclass, typed functions, explicit returns. Small API surface. |
| 2. Robustness | 6/10 | A | No internal exception handling — exceptions propagate to caller. Truncation bounds output. |
| 3. Security Posture | 7/10 | A | `navi_sanitize.clean()` on severity/title. Truncation prevents oversized output. Output feeds TB-3 indirectly. |
| 4. Adversarial Resilience | 6/10 | A | Sanitization strips invisible chars and bidi overrides (tested). Low test count overall. Indirect LLM-adjacent exposure. |
| 5. Auditability & Traceability | 5/10 | C | No structured logging. ContextPack fields are traceable but format output is opaque text. |
| 6. Test Quality | 7/10 | A | 15 tests across 6 classes. Covers positive, negative, sanitization, determinism. Thin but targeted. |
| 7. Convention Adherence | 9/10 | A | ruff, mypy strict, SPDX, naming, test mirror all clean. |
| 8. Documentation Accuracy | 6/10 | C | F-GC-001: docstring claims non-fatal but no try/except. Sanitization rationale undocumented. |
| 9. Performance | 7/10 | C | Graph queries bounded by store's walk limits. Truncation at max_chars. No unbounded operations. |
| 10. Dead Code / Debt | 9/10 | A | All functions called. Zero TODOs. Clean imports. |
| 11. Dependency Hygiene | 8/10 | A | Imports graph_store (Phase 2), graph_types (Phase 1), navi_sanitize. Cross-phase import justified. |
| **Overall** | **7.0/10** | | **Average of 11 dimensions** |

**Health status:** Adequate

**Determination:**
1. Average-based status: 7.0/10 falls in 6.0-7.9 range = **Adequate**
2. Override gates: None fired.
3. Ceiling gates: None fired. All gate dimensions >= 6.
4. Suffixes: No `(provisional)` — under v1.2 rules, only Dim 3 and Dim 4 trigger the suffix. Dim 3 (7/10) has Tier A evidence (sanitization tests). Dim 4 (6/10) has Tier A evidence (invisible chars + bidi tests). Non-security dims 5, 8, 9 using Tier C do not trigger the suffix.

**Override gates fired:** None
**Ceiling gates fired:** None

---

## Findings

### F-GC-001: Docstring claims non-fatal but function propagates exceptions (LOW)

**Severity:** LOW
**Status:** OPEN
**Evidence tier:** A (test: `test_build_context_pack_graph_exception_propagates`)

**Location:** `graph_context.py:32`

**Description:** `build_context_pack()` docstring says "Non-fatal — empty on errors" but the function has no try/except wrapper. When the graph store raises an exception (e.g., closed connection), it propagates to the caller. The actual non-fatal wrapper is in `review.py:577-587`, which catches `Exception` from `build_context_pack()` and logs a warning.

**Current behavior documented by test:** `test_build_context_pack_graph_exception_propagates` verifies that `sqlite3.ProgrammingError` propagates when the store's connection is closed.

**Risk:** LOW — the docstring is misleading but the caller handles it correctly. No production impact since review.py catches the exception. A developer reading graph_context.py in isolation would incorrectly assume the function is safe to call without error handling.

**Suggested improvement:** Either:
(a) Update docstring to "Caller should handle exceptions — query errors propagate." OR
(b) Add try/except in `build_context_pack()` to match the docstring's promise, returning an empty ContextPack on error.

### KRC-01 instance: Fixture matrix gap (LOW)

**Severity:** LOW (known recurring class — see METHODOLOGY.md Section E.1)
**Status:** OPEN
**Evidence tier:** C

**Description:** The 15-test suite covers positive, edge case, sanitization, and determinism categories. No adversarial fixtures specifically targeting crafted graph data that could exploit `format_context_for_llm()` output in the LLM prompt path (e.g., graph node data containing prompt injection payloads that survive `navi_sanitize.clean()`).

**Rationale for LOW vs MEDIUM:** `navi_sanitize.clean()` handles the Unicode-level attack surface (invisible chars, bidi, homoglyphs). Content-level prompt injection in severity/title fields is a concern, but `navi_sanitize.clean()` is not designed to block semantic prompt injection — that defense layer is in `_escape_xml()` (agent.py) and data-fence boundaries (agent.py). The sanitization here prevents Unicode-level evasion of downstream defenses, which is verified by tests.

### Compound Chain Exposure

graph-context participates in **CH-2 (Path Traversal -> Data Exfiltration -> Prompt Leakage)** as a **relay**.

**Data flow:**
```
graph_store (graph data) → build_context_pack() → ContextPack
  → format_context_for_llm() → navi_sanitize.clean() on severity/title
  → sanitized text → review.py wraps in <graph-context> tags
  → agent prompt (TB-3) → LLM
```

**Two distinct risk categories (scored independently):**

1. **Error resilience:** `build_context_pack()` propagates exceptions. The caller (`review.py`) catches them and continues without graph context. Circuit breaker is in the caller, not this unit.

2. **Prompt-safety / sanitization:** `format_context_for_llm()` sanitizes severity and title fields via `navi_sanitize.clean()` before output. This handles Unicode-level evasion (invisible chars, bidi overrides, homoglyphs). Content-level prompt injection defense is delegated to downstream `_escape_xml()` in agent.py. Evidence: `test_format_context_sanitizes_invisible_chars`, `test_format_context_sanitizes_bidi_override`.

**Residual risk:** `file_history` observations (line 125: `lines.append(f"- {path}: {o}")`) and `blast_radius_files` paths (line 110: `lines.append(f"- {path}: imported by {count} module(s)")`) are NOT sanitized by `navi_sanitize.clean()`. These fields pass through `format_context_for_llm()` unsanitized. File paths originate from codebase indexing (which processes PR content) and observation content originates from review pipeline output. If either contains crafted content, it enters the LLM prompt without Unicode normalization. This is LOW risk because the downstream `<graph-context>` XML wrapper and `_escape_xml()` in agent.py provide content-level defense.

### Hypotheses

None.

---

## Dimension Details

### 1. Contract Fidelity

**Score:** 7/10
**Evidence:**
- mypy strict passes with zero issues (Tier A).
- `ContextPack` is a dataclass with typed fields: `touched_files: list[str]`, `blast_radius_files: list[tuple[str, int]]`, `recurring_findings: list[dict[str, Any]]`, `file_history: dict[str, list[str]]`, `author_risk_summary: dict[str, int]` (Tier A).
- `build_context_pack()` signature: explicit parameter types and return type `-> ContextPack` (Tier A).
- `format_context_for_llm()` signature: `(pack: ContextPack, max_chars: int = 2000) -> str` (Tier A).
- Not 8: `recurring_findings` uses `list[dict[str, Any]]` — no typed finding model. `ContextPack` is not frozen.
- Calibration: matches imports (7). Both have typed functions but use unstructured dict fields.

---

### 2. Robustness

**Score:** 6/10
**Evidence:**
- **Truncation:** `format_context_for_llm()` enforces `max_chars` with `"... (truncated)"` suffix (Tier A: `test_format_truncation`, `test_format_context_truncation_boundary`).
- **Empty inputs:** Empty touched_files returns empty string from `format_context_for_llm()`. Empty graph returns ContextPack with all empty fields (Tier A: `test_empty_graph`, `test_empty_pack`).
- **No exception handling:** `build_context_pack()` has no try/except despite docstring claiming non-fatal behavior (F-GC-001). Exceptions from graph store propagate to caller.
- **No retry or degradation:** Single query path. If any graph query fails, the entire function fails.
- Not 7: No internal exception handling. The non-fatal wrapper is in the caller (review.py), not this unit. The "return empty" degradation strategy promised by the docstring is not implemented.
- Calibration: below imports (8, which wraps all AST/path operations in try/except). graph-context delegates error handling to its caller.

---

### 3. Security Posture

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 7/10
**Evidence:**
- **Sanitization of severity/title:** `navi_sanitize.clean()` called on `severity` and `title` fields from recurring findings before formatting (Tier A: `test_format_context_sanitizes_invisible_chars`, `test_format_context_sanitizes_bidi_override`). Strips null bytes, invisible chars, bidi controls, normalizes homoglyphs.
- **Output truncation:** `max_chars` (default 2000) prevents oversized context from flooding LLM prompt (Tier A: `test_format_truncation`).
- **Capped iteration:** Blast radius capped at `[:10]`, recurring findings at `[:10]`, file history at `[:5]` files with `[-3:]` observations each (Tier B: code trace).
- **No trust boundary anchors:** graph-context is not a boundary anchor. Output feeds TB-3 indirectly through review.py.
- **Gap — unsanitized fields:** File paths and observation content are not passed through `navi_sanitize.clean()`. These originate from internal systems (codebase indexing, review pipeline) but could contain crafted content if the graph is populated from a malicious PR.
- Not 8: Selective sanitization — only severity/title sanitized, not paths or observations. Defense relies on downstream `_escape_xml()` for content-level protection.
- Calibration: above imports (6) and embedder (6) — has active sanitization of some fields. Below local-diff (9) — no defense-in-depth layers.

---

### 4. Adversarial Resilience

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 6/10
**Evidence:**
- **Unicode sanitization verified:** Invisible chars (zero-width space, zero-width joiner) stripped from severity/title (Tier A: `test_format_context_sanitizes_invisible_chars`). Bidi overrides (RTL override, LTR embedding) stripped (Tier A: `test_format_context_sanitizes_bidi_override`).
- **Deterministic output:** Same graph state + same inputs = identical output across repeated calls (Tier A: `test_output_ordering_deterministic`). Prevents timing-dependent adversarial exploitation.
- **Indirect exposure:** graph-context output enters LLM prompt via review.py's `<graph-context>` wrapper. Attacker-controlled content could reach this path through codebase indexing of malicious PR content → graph store → context pack → LLM.
- Not 7: Low test count (15 total, 2 sanitization). No adversarial fixtures for content-level prompt injection via graph data fields. Sanitization covers Unicode-level evasion only — semantic injection defense is delegated to downstream layers.
- Calibration: matches imports (6). Both have indirect exposure and limited adversarial testing. Below local-diff (8, which has 10 dedicated injection tests).

---

### 5. Auditability & Traceability

**Score:** 5/10
**Evidence:**
- **ContextPack fields are inspectable:** Dataclass with named fields — a debugger or log statement can dump the full pack (Tier C).
- **`format_context_for_llm()` output is structured text:** Sections ("Files with downstream dependents:", "Prior findings:", etc.) are identifiable in the formatted output (Tier C).
- **Deterministic:** Same inputs produce same output (Tier A: `test_output_ordering_deterministic`).
- Not 6: No logger. No structured logging. No log of which files were queried, how many graph results were returned, or whether truncation occurred. The only diagnostic is the formatted text output itself.
- Calibration: matches imports (5). Both have no structured logging despite defining a logger (imports has logger defined but unused; graph-context has no logger at all).

---

### 6. Test Quality

**Score:** 7/10
**Evidence:**
- **Test count:** 15 tests across 6 test classes (after Commit 2 additions).
- **Source:test ratio:** 136 LOC source / 231 LOC tests = 1.70:1 test-to-source ratio.
- **Test classes:**
  - TestBuildContextPack (5): empty graph, blast radius, recurring findings, file history, author risk.
  - TestFormatContext (4): empty pack, max length, all sections, truncation.
  - TestContextErrorResilience (2): exception propagation, no touched files.
  - TestContextSanitization (3): invisible chars, bidi override, truncation boundary.
  - TestContextDeterminism (1): output ordering determinism.
- **Fixture matrix:** Positive (5), edge case (3), sanitization (3), determinism (1), error (2). Negative tests present but thin. No adversarial content-injection fixtures (KRC-01).
- Not 8: Only 15 tests for an LLM-adjacent data flow unit. Compare to graph-store's 81 tests (similar risk, more complex API). The sanitization tests are targeted but don't cover unsanitized fields (paths, observations).
- Calibration: matches imports (7, 20 tests). Below graph-store (9, 81 tests) and local-diff (8, 30 tests).

---

### 7. Convention Adherence

**Score:** 9/10
**Evidence:**
- SPDX header on source and test file (Tier A).
- ruff check passes with zero issues (Tier A).
- mypy strict passes with zero issues (Tier A).
- Test file follows mirror structure: `src/grippy/graph_context.py` -> `tests/test_grippy_graph_context.py` (Tier A).
- Test file exceeds 50 LOC minimum (231 LOC) (Tier A).
- Calibration: matches imports (9), schema (9), graph-store (9).

---

### 8. Documentation Accuracy

**Score:** 6/10
**Evidence:**
- File-level docstring: "Pre-review context builder — queries the graph for blast radius + history" — accurate (Tier C).
- `ContextPack` docstring: "Pre-review context extracted from the graph store" — accurate (Tier C).
- `build_context_pack()` docstring: "Query graph for pre-review context. Non-fatal — empty on errors." — **inaccurate** (F-GC-001). The function does not catch exceptions; the caller does.
- `format_context_for_llm()` docstring: "Format context pack as sanitized text for LLM prompt context" — accurate. Does call `navi_sanitize.clean()` on severity/title (Tier C).
- **Missing documentation:** No docstring explains why only severity/title are sanitized (not paths or observations). No explanation of the `max_chars` default value (2000). No documentation of the `<graph-context>` wrapping that happens in the caller (review.py).
- Not 7: F-GC-001 docstring/behavior mismatch. Missing sanitization rationale.
- Calibration: below imports (7) and graph-store (7). The docstring mismatch is a concrete accuracy failure, not just a gap.

---

### 9. Performance

**Score:** 7/10
**Evidence:**
- **Graph queries bounded:** `walk()` calls use `max_depth=2, max_nodes=30` for blast radius and `max_depth=2, max_nodes=100` for author history (Tier B: code trace).
- **Iteration caps:** `[:10]` on blast radius and recurring findings, `[:5]` on file history files, `[-3:]` on observations per file (Tier B: code trace).
- **Output truncation:** `max_chars` prevents unbounded output growth (Tier A: tested).
- **Single pass formatting:** `format_context_for_llm()` is O(findings + blast + history) — no nested loops.
- Not 8: No profiling data. Walk limits are hardcoded rather than configurable.
- Calibration: below graph-store (8, which has compiled pragmas and batch-touch optimization). Appropriate — graph-context does less work.

---

### 10. Dead Code / Debt

**Score:** 9/10
**Evidence:**
- Zero `TODO` or `FIXME` comments (Tier A: grep search).
- All functions called: `build_context_pack` and `format_context_for_llm` by review.py (Tier B: caller trace). `ContextPack` by tests and review.py.
- ruff detects no unused imports (Tier A).
- Not 10: `_record_id` import from graph_types is used but only within `build_context_pack` — acceptable internal use pattern.

---

### 11. Dependency Hygiene

**Score:** 8/10
**Evidence:**
- **Internal deps:** `graph_store` (Phase 2, audited at 8.0/10), `graph_types` (Phase 1, audited at 7.6/10). Two internal dependencies — both audited.
- **External deps:** `navi_sanitize` (sanitization library, external). `collections.Counter` (stdlib).
- **No circular imports** (Tier A: ruff check).
- **Cross-phase import:** graph-context (Phase 2) imports graph_store (Phase 2, same phase) and graph_types (Phase 1). Both justified — graph-context queries the store and uses graph_types for `_record_id`.
- Not 9: `navi_sanitize` is an external dependency whose behavior graph-context relies on for security properties. Changes to `navi_sanitize.clean()` contract could silently weaken sanitization.
- Calibration: matches graph-store (8). Both have small, justified dependency graphs.

---

## Calibration Assessment

graph-context scores **7.0/10** against calibration peers:
- **imports (7.4):** graph-context is smaller, has similar indirect exposure, similar test density. Lower documentation score (docstring mismatch) and lower robustness (no internal error handling) account for the 0.4 gap. Framework discriminates.
- **graph-types (7.6):** graph-types is a data model with no runtime behavior — simpler to audit. graph-context has active sanitization logic and LLM-adjacent data flow, creating more audit surface. The 0.6 gap reflects that additional risk.
- **graph-store (8.0):** graph-store has 81 vs 15 tests, broader API, stronger robustness. The 1.0 gap is the largest in this batch and reflects genuine quality difference.

The framework is discriminating: graph-context's thinner tests, selective sanitization, and docstring mismatch produce a score noticeably lower than its infrastructure peers. This is the expected outcome from the plan's calibration checkpoint.
