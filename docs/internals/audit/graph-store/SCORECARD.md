<!-- SPDX-License-Identifier: MIT -->

# Audit Scorecard: graph-store

**Audit date:** 2026-03-14
**Commit:** e4d24a8
**Auditor:** Claude Opus 4.6 (AI draft) / Nelson Spence (human reviewer)
**Unit type:** infrastructure (primary)
**Subprofile:** state
**Methodology version:** 1.2

---

## Checklist: IN-01, IN-02, IN-S01, IN-S02, IN-S03

| ID | Invariant | Status | Evidence |
|----|-----------|--------|----------|
| IN-01 | Missing config produces clear error | PASS | `db_path` is a required keyword-only parameter (`__init__(*, db_path)`) — omitting it raises `TypeError`. `Path.mkdir(parents=True, exist_ok=True)` handles directory creation. No environment variables or optional config. |
| IN-02 | Unit follows project conventions | PASS | SPDX header (line 1). ruff clean, mypy strict clean, bandit clean (Tier A: CI). Test mirror: `test_grippy_graph_store.py` (Tier A). |
| IN-S01 | File-based state handles concurrent access safely | PASS | WAL mode configured and verified by pragma test (Tier A: `TestPragmas::test_wal_mode`). Concurrent read/write test uses separate `SQLiteGraphStore` instances on the same DB path (Tier A: `TestConcurrentAccess::test_concurrent_reads_during_write` — 50 writes + 20 concurrent reads, zero errors). `busy_timeout = 5000` prevents immediate lock contention failures. |
| IN-S02 | Schema migrations do not lose data or corrupt state | PASS | `CREATE TABLE IF NOT EXISTS` is idempotent — schema init on existing DB is safe. `TestIdempotentInit::test_reopen_preserves_data` verifies data survives store close/reopen cycle (Tier A). No versioned migration system — single schema version, no migration path needed yet. |
| IN-S03 | State operations are idempotent | PASS | `upsert_node`: `ON CONFLICT(id) DO UPDATE` preserves `created_at` (Tier A: `test_update_existing_preserves_created_at`). `upsert_edge`: `ON CONFLICT(source, relationship, target) DO UPDATE` (Tier A: `test_idempotent_upsert`). Observations: `INSERT OR IGNORE` deduplicates by `(node_id, source, content)` (Tier A: `test_dedup_same_source`). All tested with repeated-operation assertions. |

---

## Gate Rules

### Override Gates (force a specific status)

| Override Gate | Condition | Fired? |
|---|---|---|
| Critical finding | Any unresolved CRITICAL finding | No |
| Multi-HIGH block | 2+ unresolved HIGH findings (including provisional) | No (0 HIGH findings) |
| Security collapse | Security Posture < 2 | No (score: 8) |
| Adversarial collapse | Adversarial Resilience < 2 | No (score: 7) |

### Ceiling Gates (cap the best allowed status)

| Ceiling Gate | Condition | Fired? |
|---|---|---|
| Severity cap | Any unresolved HIGH finding | No |
| Security hard floor | Security Posture < 4 | No (score: 8) |
| Adversarial hard floor | Adversarial Resilience < 4 | No (score: 7) |
| Security soft floor | Security Posture < 6 | No (score: 8) |
| Adversarial soft floor | Adversarial Resilience < 6 | No (score: 7) |
| Accepted critical risk | Any ACCEPTED_RISK at CRITICAL | No |
| Accepted high risk | Any ACCEPTED_RISK at HIGH | No |

---

## Summary

| Dimension | Score | Evidence Tier | Notes |
|-----------|------:|:---:|-------|
| 1. Contract Fidelity | 8/10 | A | Frozen dataclasses, deterministic IDs, typed throughout, mypy strict clean |
| 2. Robustness | 8/10 | A | WAL + FK cascade, MissingNodeError fail-safe, pragma fallbacks, busy_timeout |
| 3. Security Posture | 8/10 | A | All SQL parameterized, `nosec` comments on safe patterns, no dynamic table names |
| 4. Adversarial Resilience | 7/10 | A | No external attack surface. Concurrent access proven. Graph data originates from codebase indexing of PR content — indirect exposure. |
| 5. Auditability & Traceability | 7/10 | A + C | Deterministic IDs enable trace. Pragma mismatch logged. No structured audit logging. |
| 6. Test Quality | 9/10 | A | 81 tests across 17 classes. CRUD, traversal, subgraph, observations, edge cases, pragmas, concurrent access. |
| 7. Convention Adherence | 9/10 | A | ruff, mypy strict, bandit clean. SPDX header. `nosec` annotations on all parameterized IN clauses. |
| 8. Documentation Accuracy | 7/10 | C | Docstrings with transaction semantics on every write method. Observation max length (500) undocumented in graph_store.py (defined in graph_types.py). |
| 9. Performance | 8/10 | B | Compiled pragmas at init, WAL mode, chunked IN clauses at 500, `_batch_touch` for traversal access stats. No profiling data. |
| 10. Dead Code / Debt | 9/10 | A | All methods called by 5+ consumers. Zero TODOs. Clean imports. |
| 11. Dependency Hygiene | 8/10 | A | Imports graph_types (Phase 1, audited). stdlib sqlite3 + json + collections + pathlib. No external dependencies. |
| **Overall** | **8.0/10** | | **Average of 11 dimensions** |

**Health status:** Healthy

**Determination:**
1. Average-based status: 8.0/10 -> Healthy (8.0+ range, exact boundary)
2. Override gates: None fired.
3. Ceiling gates: None fired. All gate dimensions >= 6.
4. Suffixes: No `(provisional)` — Dim 3 (8/10) has Tier A evidence (parameterized query tests). Dim 4 (7/10) has Tier A evidence (concurrent access test + MissingNodeError tests). Under v1.2 rules, non-security dimensions with Tier C (dims 8, 9) do not trigger the suffix.

**Override gates fired:** None
**Ceiling gates fired:** None

---

## Findings

### F-GS-001: Pragma mismatch handling is silent-but-logged (LOW)

**Severity:** LOW
**Status:** OPEN
**Evidence tier:** B (deterministic trace: `_init_schema` lines 113-121)

**Location:** `graph_store.py:113-121`

**Description:** When a SQLite pragma returns an unexpected value (e.g., WAL mode not available on the platform), the code logs a warning but continues initialization. This is the correct behavior for non-critical pragmas (cache_size, synchronous) but the same fallback applies to `journal_mode = WAL` and `foreign_keys = ON`, which are correctness-critical.

**Current behavior:** Warning logged, init continues. Tests verify both the mismatch path (`test_pragma_mismatch_warning`) and the operational error path (`test_pragma_operational_error`).

**Risk:** If WAL mode fails to set on an unusual platform, the store operates in rollback journal mode, which reduces concurrent read safety. If FK fails to set, cascade deletes may not fire, leaving orphaned edges/observations.

**Suggested improvement:** Log at ERROR level for WAL and FK pragma mismatches. Consider raising an exception for FK failure specifically, since data integrity depends on it.

**Compound chain exposure:** Indirect. If FK cascade fails silently, orphaned edges could produce stale graph traversal results, biasing enrichment suppression decisions (CH-4 adjacent).

### KRC-01 instance: Fixture matrix gap (LOW)

**Severity:** LOW (known recurring class — see METHODOLOGY.md Section E.1)
**Status:** OPEN
**Evidence tier:** C

**Description:** The 81-test suite is strong across positive, negative, and edge case categories. No adversarial test fixtures specifically targeting graph data that might originate from malicious PR content (e.g., node IDs with unusual characters, data JSON with oversized payloads). This is LOW severity because graph-store is an internal data layer — untrusted input enters through codebase indexing and review.py, not directly.

### Compound Chain Exposure

graph-store is a **state substrate** whose corruption could bias downstream systems. It does not cleanly fit a single compound chain — instead it has **diffuse dependency** across multiple chains:

- **CH-4 adjacent (Rule Bypass):** enrichment.py queries the graph for suppression decisions. Stale or missing graph data could cause false suppressions (rule findings incorrectly marked as recurring/suppressed). Role: **relay** (passes through graph state to enrichment logic).
- **CH-2 adjacent (Data Exfiltration):** graph_context.py queries the graph to build LLM context packs. Corrupted graph data flows through `format_context_for_llm()` into the LLM prompt. Role: **relay** (provides data to context builder).

**Circuit breaker:** `MissingNodeError` prevents edge creation between nonexistent nodes, maintaining referential integrity at the application level (in addition to FK constraints at the DB level). Deterministic IDs prevent node ID collisions. `_canonical_json()` prevents cache-busting via JSON key reordering.

### Hypotheses

None.

---

## Dimension Details

### 1. Contract Fidelity

**Score:** 8/10
**Evidence:**
- mypy strict passes with zero issues (Tier A).
- All public methods typed with explicit return types (Tier A).
- `GraphNode`, `GraphEdge` are frozen dataclasses from graph_types — immutable contracts (Tier A).
- `_record_id()` and `_edge_id()` produce deterministic SHA256-based IDs — same inputs always produce same ID (Tier A: `test_deterministic_edge_id`).
- `_canonical_json()` ensures deterministic JSON serialization — key ordering is stable (Tier A: `test_canonical_json_in_db`).
- `MissingNodeError` provides typed exception discrimination with `node_id` and `role` attributes (Tier A).
- `NeighborResult`, `TraversalResult`, `SubgraphResult` are frozen dataclasses with explicit field types.
- Not 9: No Protocol classes or runtime type checks at boundaries. `data` field is `dict[str, Any]` — no schema validation on node data payloads.
- Calibration: matches local-diff (8). Both have frozen/typed return values and custom exceptions.

---

### 2. Robustness

**Score:** 8/10
**Evidence:**
- **WAL mode:** Configured at init, verified by pragma read-back (Tier A: `test_wal_mode`). Enables concurrent readers during writes.
- **FK constraints:** `ON DELETE CASCADE` on edges and observations — node deletion cleans up all dependent records (Tier A: `test_fk_cascade_works`, `test_cascade_delete`).
- **MissingNodeError:** Raised BEFORE edge write if source or target node absent — no partial state (Tier A: `test_missing_source_raises`, `test_missing_target_raises`).
- **Pragma fallback:** `OperationalError` caught during pragma setting, logged as warning, init continues (Tier A: `test_pragma_operational_error`). Mismatch also logged (Tier A: `test_pragma_mismatch_warning`). See F-GS-001 for risk assessment.
- **busy_timeout = 5000:** Prevents immediate `SQLITE_BUSY` under light contention.
- **Empty input guards:** `get_nodes([])` returns `[]`, `subgraph([])` returns empty result, `walk([])` returns empty traversal, `delete_observations(_, [])` is no-op (all Tier A tested).
- Not 9: No retry logic on transient SQLite errors. Pragma mismatch for correctness-critical settings (WAL, FK) gets the same soft warning as non-critical settings.
- Calibration: matches local-diff (8). Both have typed exceptions, explicit bounds, and defensive edge case handling.

---

### 3. Security Posture

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 8/10
**Evidence:**
- **All SQL parameterized:** Every query uses `?` placeholders. No string interpolation in SQL (Tier A: all CRUD tests exercise parameterized paths).
- **`nosec B608` annotations:** 12 instances, each on a dynamically-constructed IN clause using repeated `?` placeholders. The `nosec` comments explain why the pattern is safe — column names are hardcoded string literals, not user input (Tier B: code trace).
- **No dynamic table names:** Schema is hardcoded DDL strings. Table names never come from parameters.
- **Chunked IN clauses:** `subgraph()` chunks at 500 to stay under SQLite's 999 variable limit — prevents runtime errors on large inputs (Tier B: code trace at `graph_store.py:521`).
- **Observation max length:** 500 chars enforced by `ValueError` in `add_observations()` (Tier A: `test_max_length_enforced`). Prevents oversized payloads.
- **No trust boundary anchors:** graph-store is an internal data layer. Untrusted data reaches it indirectly through review.py and codebase indexing.
- Not 9: No audit logging of write operations. `data` field accepts arbitrary `dict[str, Any]` — no payload validation beyond JSON serialization.
- Calibration: below local-diff (9, which owns TB-2 and has defense-in-depth subprocess safety), above embedder (6, which has no trust boundaries but minimal defense surface).

---

### 4. Adversarial Resilience

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 7/10
**Evidence:**
- **No direct external attack surface:** graph-store is not exposed to untrusted input directly. Data enters through review.py (which sanitizes PR content) and codebase indexing.
- **Concurrent access proven:** Separate store instances on same DB path, 50 writes + 20 concurrent reads, zero errors (Tier A: `TestConcurrentAccess`).
- **MissingNodeError prevents orphan edges:** Application-level referential integrity check before edge creation (Tier A: `test_missing_source_raises`, `test_missing_target_raises`).
- **Deterministic IDs:** SHA256-based IDs prevent collision-based attacks. `_canonical_json()` prevents cache-busting via JSON key reordering (Tier A: `test_canonical_json_in_db`, `test_deterministic_edge_id`).
- **Idempotent upserts:** Repeated operations produce same result (Tier A: `test_idempotent` for nodes, `test_idempotent_upsert` for edges, `test_dedup_same_source` for observations).
- Not 8: No adversarial fixtures specifically targeting graph data from malicious PR content (KRC-01 instance). Graph data originates from codebase indexing which processes PR content — indirect exposure channel exists.
- Calibration: below local-diff (8, which has 10 dedicated injection tests). Appropriate — local-diff has direct user input exposure; graph-store's exposure is indirect.

---

### 5. Auditability & Traceability

**Score:** 7/10
**Evidence:**
- **Deterministic IDs:** `_record_id()` and `_edge_id()` produce repeatable SHA256-based IDs from input parameters. Given a node type + parts, the ID is reconstructable (Tier A).
- **Pragma mismatch logging:** `log.warning()` on pragma value mismatch, `log.debug()` on successful pragma set (Tier A: `test_pragma_mismatch_warning`).
- **Timestamps on all records:** `created_at`, `updated_at`, `accessed_at` on nodes; `created_at`, `updated_at` on edges; `created_at` on observations (Tier B: schema DDL trace).
- **Access stats:** `access_count` and `accessed_at` on nodes, updated by read operations and batch-touched after traversals (Tier A: `test_touches_access_stats`, `test_batch_touch_after_walk`).
- Not 8: No structured audit logging of write operations (upsert/delete). No log module usage beyond pragma init. Trace requires direct DB inspection.
- Calibration: matches local-diff (7). Both have deterministic operations and traceable state, but no structured audit logging.

---

### 6. Test Quality

**Score:** 9/10
**Evidence:**
- **Test count:** 81 tests across 17 test classes (after Commit 2 adds `TestConcurrentAccess`).
- **Source:test ratio:** 633 LOC source / 910 LOC tests = 1.44:1 test-to-source ratio.
- **Fixture matrix categories:**
  - Positive: Node CRUD, edge CRUD, observation CRUD, traversal, subgraph, neighbor queries (40+ tests).
  - Negative: Missing node returns None, delete nonexistent returns False, MissingNodeError on orphan edges (6+ tests).
  - Edge cases: Empty inputs, max length enforcement, pragma mismatch/error, inner truncation, depth limits, cycle prevention (10+ tests).
  - Concurrent: WAL concurrent read/write with separate store instances (1 test).
  - Idempotency: Repeated upsert, dedup observations, normalization dedup (4+ tests).
- **Coverage classes:** TestInit, TestSchema, TestPragmas, TestIndexes, TestIdempotentInit, TestUpsertNode, TestUpsertEdge, TestDeleteNode, TestDeleteEdge, TestGetNode, TestGetNodes, TestGetRecentNodes, TestNeighbors, TestWalk, TestSubgraph, TestObservations, TestEdgeCases, TestConcurrentAccess.
- Not 10: No property-based testing. No mutation testing. KRC-01 fixture matrix gap in adversarial category.
- Calibration: above local-diff (8, 30 tests) and embedder (8, 10 tests). Significantly more comprehensive test suite.

---

### 7. Convention Adherence

**Score:** 9/10
**Evidence:**
- SPDX header on source and test file (Tier A).
- ruff check passes with zero issues (Tier A).
- mypy strict passes with zero issues (Tier A).
- bandit passes — `nosec B608` annotations are deliberate and documented (Tier A).
- Test file follows mirror structure: `src/grippy/graph_store.py` -> `tests/test_grippy_graph_store.py` (Tier A).
- Test file exceeds 50 LOC minimum (910 LOC) (Tier A).
- `nosec` annotations include explanatory comments per project convention.
- Calibration: matches local-diff (9) and schema (9).

---

### 8. Documentation Accuracy

**Score:** 7/10
**Evidence:**
- File-level docstring: "SQLiteGraphStore — navi-graph-shaped graph persistence" — accurate (Tier C).
- Class docstring: "Navi-graph-shaped SQLite graph store" — brief but accurate (Tier C).
- Write method docstrings include transaction semantics: "Transaction: atomic — single INSERT OR UPDATE", "Transaction: atomic — check + upsert in same transaction" (Tier C: `upsert_node`, `upsert_edge`).
- Read method docstrings distinguish transaction strategy: "Transaction: read is outside transaction, touch is atomic" (Tier C: `get_node`).
- `walk()` docstring documents direction semantics, batch touch strategy, and performance rationale (Tier C).
- Not 8: Observation max length (500 chars) is defined in graph_types.py as `MAX_OBSERVATION_LENGTH` but not mentioned in graph_store.py's `add_observations` docstring (Tier C: documentation gap). `_PRAGMAS` list structure undocumented.
- Calibration: below local-diff (8, which has full Args/Returns/Raises sections). graph-store's docstrings are correct but briefer.

---

### 9. Performance

**Score:** 8/10
**Evidence:**
- **Compiled pragmas at init:** WAL, FK, busy_timeout, synchronous, temp_store, cache_size all set once (Tier B: `_init_schema` trace).
- **WAL mode:** Enables concurrent readers — readers don't block writers (Tier A: concurrent access test).
- **Chunked IN clauses:** `subgraph()` chunks at 500 to stay under SQLite's 999 variable limit (Tier B: code trace).
- **`_batch_touch`:** Traversal updates access stats in a single UPDATE statement instead of per-node (Tier B: code trace at `_batch_touch`).
- **Deterministic ordering:** `ORDER BY` clauses on all queries prevent result-set instability without runtime sorting overhead.
- **`_get_node_readonly`:** Traversal internals skip access stat updates to reduce write amplification (Tier B: code trace).
- Not 9: No profiling data. No benchmark results. Connection pool not used (single connection per store instance).
- Calibration: matches local-diff (8). Both are efficient for their workload with explicit bounds.

---

### 10. Dead Code / Debt

**Score:** 9/10
**Evidence:**
- Zero `TODO` or `FIXME` comments (Tier A: grep search).
- All public methods called: `upsert_node`/`upsert_edge` by review.py + mcp_server.py, `get_node`/`get_nodes` by graph_context.py + enrichment.py, `walk` by graph_context.py + enrichment.py, `neighbors` by graph_context.py + enrichment.py, `subgraph` by tests + benchmarks, `add_observations`/`get_observations`/`delete_observations` by review.py + tests (Tier B: caller trace).
- ruff detects no unused imports (Tier A).
- 5 internal consumers: review.py, graph_context.py, enrichment.py, mcp_server.py, __init__.py.
- Not 10: `_get_node_readonly` and `_batch_touch` are private but well-justified as traversal optimizations.

---

### 11. Dependency Hygiene

**Score:** 8/10
**Evidence:**
- **Internal deps:** Imports `graph_types` (Phase 1, audited at 7.6/10). Single internal dependency.
- **External deps:** Zero. Uses only stdlib: `sqlite3`, `json`, `logging`, `collections.deque`, `pathlib.Path`.
- **No circular imports** (Tier A: ruff check).
- **Clean boundary:** graph_store depends only on graph_types (lower phase). All 5 consumers depend on graph_store, not the reverse.
- Not 9: `graph_types` imports are broad (12 names). Could use a more selective import, though all are used.
- Calibration: matches embedder (8). Both have minimal deps. local-diff (10) has zero internal deps.
