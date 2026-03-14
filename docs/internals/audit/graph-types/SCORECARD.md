<!-- SPDX-License-Identifier: MIT -->

# Audit Scorecard: graph-types

**Audit date:** 2026-03-13
**Commit:** b40d4ec
**Auditor:** Claude Opus 4.6 (AI draft) / Nelson Spence (human reviewer)
**Unit type:** data-model (primary)
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
| 1. Contract Fidelity | 7/10 | A | All functions typed, mypy strict clean, frozen dataclasses |
| 2. Robustness | 7/10 | A + C | _canonical_json rejects non-dict (tested), MissingNodeError typed exception |
| 3. Security Posture | 7/10 | C | No I/O, no secrets, frozen=True. Does not own trust boundaries. |
| 4. Adversarial Resilience | 6/10 | C | Limited exposure as data model. _normalize_observation regex is safe. No adversarial fixtures. |
| 5. Auditability & Traceability | 6/10 | C | Deterministic IDs, canonical JSON. No logging (appropriate for data model). |
| 6. Test Quality | 8/10 | A | 35 tests, 1.42:1 test:source ratio. Positive, negative, edge-case coverage. |
| 7. Convention Adherence | 9/10 | A | ruff, mypy strict, bandit clean. SPDX headers. Mirror test structure. |
| 8. Documentation Accuracy | 7/10 | C | File-level docstring, all helpers have docstrings. Case sensitivity documented. |
| 9. Performance | 8/10 | C | Compiled regex, hashlib for IDs, json.dumps with sorted keys. Optimal for workload. |
| 10. Dead Code / Debt | 9/10 | A + C | Zero TODOs, all functions called, all types consumed by graph-store/graph-context/enrichment. |
| 11. Dependency Hygiene | 10/10 | A | Zero internal deps. graph.py re-exports within same unit. 5 stdlib deps only. |
| **Overall** | **7.6/10** | | **Average of 11 dimensions** |

**Health status:** Adequate (provisional)

**Determination:**
1. Average-based status: 7.6/10 falls in 6.0-7.9 range = Adequate
2. Override gates: None fired.
3. Ceiling gates: None fired. All gate dimensions >= 6.
4. Suffixes: `(provisional)` -- dims 3, 4, 5, 8, 9 include Tier C evidence components.

**Override gates fired:** None
**Ceiling gates fired:** None

---

## Checklist: DM-01 through DM-05

| ID | Verdict | Evidence | Notes |
|----|---------|----------|-------|
| DM-01 | PASS | Tier A: `test_graph_node_frozen`, `test_graph_edge_frozen` prove frozen dataclasses reject mutation. `test_rejects_non_dict`, `test_rejects_string` prove _canonical_json type enforcement. mypy strict clean. | All 6 dataclasses use `frozen=True`. All functions fully typed. |
| DM-02 | PASS | Tier A: mypy strict proves all fields required. Tier C: code inspection -- only `TraversalReceipt.reason` uses `str \| None`, which is intentional (truncation may have no reason). | No spurious Optional. |
| DM-03 | PASS (design note) | Tier C: `GraphNode.type` and `GraphEdge.relationship` are bare `str` rather than `NodeType`/`EdgeType` enum. This is an **accepted design choice** -- the graph schema is intentionally extensible so that future node/edge types can be added without schema migration. The enums define the current vocabulary; the store accepts any string. | Not a defect under current schema contract. |
| DM-04 | PASS | Tier A: `TestCanonicalJson` (5 tests) proves sorted-key, compact JSON round-trip. `test_rejects_non_dict` proves dict-only constraint. | dict fields stored as JSON in SQLite via `_canonical_json()`. |
| DM-05 | PASS | Tier A + C: All types consumed by graph_store.py (GraphNode, GraphEdge, NeighborResult, SubgraphResult, TraversalResult, TraversalReceipt, MissingNodeError), graph_context.py (_record_id), enrichment.py (EdgeType, NodeType, _record_id), review.py (EdgeType, NodeType, MissingNodeError, _record_id). No orphan types. | grep confirms 14 importing files across source and tests. |

**N/A items:** 0/5. All checklist items applicable.

---

## Findings

No findings. All checklist items PASS. DM-03 documented as accepted design choice.

### Compound Chain Exposure

`None identified` -- graph-types defines data structures consumed by graph-store and graph-context but does not own trust-boundary behavior. It consumes boundary-derived data (diff content flows into graph nodes) but performs no validation or transformation that could participate in a chain.

---

## Dimension Details

### 1. Contract Fidelity

**Key question:** Do types, exports, and validation faithfully represent the unit's contract?

**Score:** 7/10
**Evidence:**
- mypy strict passes with zero issues across both source files (Tier A: static analysis).
- All 6 dataclasses are `frozen=True` with explicit types on every field (Tier A: mypy proves this).
- All 5 helper functions fully typed: `_record_id(node_type: NodeType | str, *parts: str) -> str`, `_edge_id(source: str, relationship: str, target: str) -> str`, `_canonical_json(obj: dict[str, Any]) -> str`, `_now_ms() -> int`, `_normalize_observation(text: str) -> str` (Tier A: mypy).
- `NodeType` and `EdgeType` use `StrEnum` for type-safe enum values (Tier A: `test_v1_types`).
- `MissingNodeError` is a typed exception with `node_id` and `role` attributes (Tier A: 2 tests).
- `_canonical_json()` rejects non-dict input at runtime with `TypeError` (Tier A: `test_rejects_non_dict`, `test_rejects_string`).
- Not 9: No Protocol classes. DM-03 bare `str` fields (accepted design choice) prevent full enum-level type safety on GraphNode.type/GraphEdge.relationship.

---

### 2. Robustness

**Key question:** Does the unit handle errors, retries, and edge cases correctly?

**Score:** 7/10
**Evidence:**
- `_canonical_json()` validates input type and raises `TypeError` with descriptive message for non-dict input (Tier A: 2 tests).
- `MissingNodeError` is a typed exception carrying `node_id` and `role` for debugging (Tier A: 2 tests).
- `_normalize_observation()` handles edge cases: empty-after-strip returns `""`, newlines collapsed, internal whitespace normalized (Tier A: 5 tests including `test_empty_after_strip`).
- Pure function design: all helpers are stateless, deterministic (proven by `test_deterministic` for both `_record_id` and `_edge_id`). No error states beyond type validation.
- No retries, timeouts, or resource management needed -- appropriate for stateless data model helpers.
- Not 8: Rubric criteria for 8+ (retry, graceful degradation) are structurally inapplicable.

---

### 3. Security Posture

**Key question:** Does the unit protect against injection, leakage, and unauthorized access?

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 7/10
**Evidence:**
- No I/O, no network, no subprocess calls, no logging of sensitive data (Tier C: module-level inspection).
- `frozen=True` on all dataclasses prevents post-construction mutation (Tier A: 2 tests).
- `_canonical_json()` enforces dict-only input, preventing accidental serialization of objects that might contain sensitive attributes (Tier A: 2 tests).
- Deterministic ID generation via SHA-256 ensures no information leakage in node/edge IDs (Tier C: `_record_id` and `_edge_id` use one-way hash).
- Does not own trust boundaries. Data structures are consumed by graph-store (Phase 2) which handles I/O.
- Not 9: No input sanitization on string fields (appropriate -- graph-types is a data model, not a processing boundary).

---

### 4. Adversarial Resilience

**Key question:** Can the unit resist adversarial input from untrusted PR content and prompt injection?

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 6/10
**Evidence:**
- Limited adversarial exposure: graph-types defines data structures, not processing logic. Untrusted PR content enters via review.py/enrichment.py which construct GraphNode/GraphEdge instances -- the types themselves perform no interpretation of content.
- `_normalize_observation()` uses `\s+` regex which is structurally safe from ReDoS (single non-nested quantifier, no alternation). Compiled once at module load (Tier C: regex analysis).
- `frozen=True` prevents mutation of graph objects after construction, which would otherwise allow post-validation tampering (Tier A: 2 tests).
- `MAX_OBSERVATION_LENGTH = 500` bounds observation content size (Tier C: constant definition at line 96). Enforcement is in graph_store, not here.
- Not 7: No adversarial test fixtures. No multi-layer defense (not applicable -- pure data model). Attack surface is minimal but unproven by Tier A evidence.
- Calibration: matches schema (6). Both are data models with limited adversarial exposure.

---

### 5. Auditability & Traceability

**Key question:** Can operators investigate failures, reproduce review results, and trace the decision path from input to output?

**Score:** 6/10
**Evidence:**
- Deterministic node IDs: `_record_id()` produces `{TYPE}:{sha256[:12]}` format -- reproducible given same inputs (Tier A: `test_deterministic`).
- Deterministic edge IDs: `_edge_id()` produces full SHA-256 of canonical triple with `\x1f` separator (Tier A: `test_deterministic`, `test_uses_unit_separator`).
- `_canonical_json()` ensures sorted keys and compact separators for reproducible serialization (Tier A: `test_sorted_keys`).
- Type prefixes on node IDs (`FILE:`, `REVIEW:`, etc.) enable quick visual triage (Tier C: code reading).
- No logging within the module -- appropriate for a data model (Tier C).
- Not 7: No structured error context beyond `MissingNodeError`. No trace correlation IDs.
- Calibration: matches schema (6).

---

### 6. Test Quality

**Key question:** Do tests verify meaningful behavior with good coverage?

**Score:** 8/10
**Evidence:**
- 35 tests across 9 test classes (Tier A: test_grippy_graph_types.py).
- Test:source ratio: 1.42:1 (217 LOC tests / 153 LOC source).
- **Positive tests:** Enum value mapping (2 tests), deterministic IDs (2 tests), canonical JSON sorted keys (1 test), time range (1 test), multi-part ID (1 test).
- **Negative tests:** Type rejection for _canonical_json (2 tests: non-dict, string), frozen mutation rejection (2 tests: node, edge).
- **Edge cases:** Empty dict JSON (1 test), empty-after-strip normalization (1 test), case preservation (1 test), newline collapsing (1 test), hash length verification (1 test), unit separator proof (1 test), direction matters (1 test).
- **Dataclass construction:** All 6 dataclasses tested for construction and field access (6 tests).
- All 5 helper functions have dedicated test classes.
- Not 9: No adversarial fixtures (limited exposure as data model). No property-based testing.
- Calibration: schema scored 8 with 44 tests, 1.69:1 ratio. graph-types has fewer tests but proportional to smaller source size.

---

### 7. Convention Adherence

**Key question:** Does the unit follow Grippy project patterns?

**Score:** 9/10
**Evidence:**
- SPDX header present on both source files and test file (Tier A: file inspection).
- ruff check passes with zero issues (Tier A: static analysis).
- mypy strict passes with zero issues (Tier A: static analysis).
- bandit passes with zero issues (Tier A: static analysis).
- Test file follows mirror structure: `src/grippy/graph_types.py` -> `tests/test_grippy_graph_types.py` (Tier A).
- Test file exceeds 50 LOC minimum (217 LOC) (Tier A).
- Naming consistent: PascalCase for classes/enums, snake_case for functions, UPPER_CASE for constants (`MAX_OBSERVATION_LENGTH`).
- graph.py backward-compat shim uses `__all__` for explicit re-export control.
- Calibration: matches schema (9), rule-engine (9).

---

### 8. Documentation Accuracy

**Key question:** Do docstrings, comments, and docs match actual behavior?

**Score:** 7/10
**Evidence:**
- File-level docstring: "Graph types, enums, and helpers for Grippy's navi-graph-shaped store. Provides node/edge type enums, frozen dataclasses for query results, deterministic ID generation, canonical JSON serialization, and typed exceptions." (graph_types.py:2-8) -- comprehensive and accurate (Tier C).
- graph.py docstring: "Graph enums -- re-exported from graph_types for backward compatibility." (graph.py:2) -- accurate (Tier C).
- All 5 helper functions have docstrings: `_record_id`, `_edge_id`, `_canonical_json`, `_now_ms`, `_normalize_observation` -- all accurate (Tier C).
- `_normalize_observation` docstring explicitly documents case sensitivity: "Case-sensitive (preserves 'PASS' vs 'pass')" (Tier C + Tier A: `test_preserves_case`).
- Section comments (`# --- Enums ---`, `# --- Dataclasses ---`, etc.) organize the module clearly.
- Not 9: No usage examples. No documented invariants for ID format beyond docstrings. Dataclasses lack class-level docstrings.

---

### 9. Performance

**Key question:** Is the unit efficient for its workload?

**Score:** 8/10
**Evidence:**
- `_normalize_observation` regex compiled once at module load via `re.sub()` pattern (Tier C: code reading at line 147). Pattern `\s+` is O(n) with no backtracking risk.
- `_record_id` and `_edge_id` use SHA-256 (hashlib, C-accelerated) -- O(n) in input length (Tier C).
- `_canonical_json` uses `json.dumps(sort_keys=True)` -- O(n log n) in number of keys, which is bounded by dict size (Tier C).
- `_now_ms()` is a simple `time.time()` multiplication -- O(1) (Tier C).
- Frozen dataclasses have zero overhead beyond construction (no __setattr__ logic).
- Not 9: No profiling data. "Efficient for workload" by structural argument, not measurement.
- Calibration: matches schema (8), rule-engine (8).

---

### 10. Dead Code / Debt

**Key question:** Is the unit free of unused code and tracked debt?

**Score:** 9/10
**Evidence:**
- Zero `TODO` or `FIXME` comments (Tier A: grep search).
- All 6 dataclasses consumed: GraphNode/GraphEdge by graph_store.py, NeighborResult/SubgraphResult/TraversalResult/TraversalReceipt by graph_store.py callers (Tier C: caller trace via grep, 14 importing files).
- All 5 helper functions called: `_record_id` by graph_store.py/graph_context.py/enrichment.py/review.py, `_edge_id` by graph_store.py, `_canonical_json` by graph_store.py, `_now_ms` by graph_store.py, `_normalize_observation` by graph_store.py (Tier C: caller trace).
- Both enums (NodeType, EdgeType) used by multiple modules and re-exported via graph.py (Tier A: grep).
- `MAX_OBSERVATION_LENGTH` used by graph_store.py (Tier C).
- MissingNodeError used by graph_store.py and caught by review.py (Tier C).
- ruff detects no unused imports (Tier A).
- Not 10: graph.py backward-compat shim re-exports only NodeType/EdgeType. Other types must be imported directly from graph_types. This asymmetry is not debt -- it reflects the shim's purpose (backward-compat for the 2 originally-exported names).

---

### 11. Dependency Hygiene

**Key question:** Are unit boundaries clean with no circular or unnecessary deps?

**Score:** 10/10
**Evidence:**
- Zero internal dependencies: graph_types.py imports nothing from `grippy.*` (Tier A: import inspection at lines 10-18).
- graph.py imports from graph_types.py, but both files are within the same audit unit (Tier A: registry.yaml confirms graph.py is part of graph-types unit).
- External dependencies are minimal and standard: `hashlib`, `json`, `re`, `time` (stdlib), `dataclasses` (stdlib), `enum.StrEnum` (stdlib), `typing.Any`/`typing.Literal` (stdlib).
- True leaf module in the dependency graph -- depended on by 6+ source modules, depends on nothing within the project.
- No circular imports (Tier A: ruff check).
- Calibration: matches schema (10). Both are leaf data models with zero project-internal deps.
