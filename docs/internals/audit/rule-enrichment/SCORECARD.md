<!-- SPDX-License-Identifier: MIT -->

# Audit Scorecard: rule-enrichment

**Audit date:** 2026-03-14
**Commit:** 5f75603
**Auditor:** Claude Opus 4.6 (AI draft) / Nelson Spence (human reviewer)
**Unit type:** security-rule (primary)
**Subprofile:** N/A

---

## Unit Character

**This unit is not a detector rule.** Unlike the other 10 `rule-*` units, rule-enrichment does not scan diffs for patterns. It post-processes findings from detector rules by adding graph-derived context: blast radius, recurrence, suppression, and velocity. Several SR checklist items must be reinterpreted or marked N/A accordingly.

**The critical property:** Enrichment suppression directly affects gate behavior. `check_gate()` in engine.py (line 47) skips findings where `enrichment.suppressed is True`. This means `_SUPPRESSION_MAP` and `_PATH_SUPPRESSION_MAP` control whether ERROR-level findings block merges. This is the semantic power that justifies a solo audit.

---

## Gate Rules

### Override Gates (force a specific status)

| Override Gate | Condition | Fired? |
|---|---|---|
| Critical finding | Any unresolved CRITICAL finding | No |
| Multi-HIGH block | 2+ unresolved HIGH findings (including provisional) | No (0 HIGH findings) |
| Security collapse | Security Posture < 2 | No (score: 7) |
| Adversarial collapse | Adversarial Resilience < 2 | No (score: 5) |

### Ceiling Gates (cap the best allowed status)

| Ceiling Gate | Condition | Fired? |
|---|---|---|
| Severity cap | Any unresolved HIGH finding | No |
| Security hard floor | Security Posture < 4 | No (score: 7) |
| Adversarial hard floor | Adversarial Resilience < 4 | No (score: 5) |
| Security soft floor | Security Posture < 6 | No (score: 7) |
| Adversarial soft floor | Adversarial Resilience < 6 | **Yes — score 5 caps at Adequate** |
| Accepted critical risk | Any ACCEPTED_RISK at CRITICAL | No |
| Accepted high risk | Any ACCEPTED_RISK at HIGH | No |

---

## Summary

| Dimension | Score | Evidence Tier | Notes |
|-----------|------:|:---:|-------|
| 1. Contract Fidelity | 8/10 | A | All functions typed, mypy strict clean. `ResultEnrichment` dataclass is the formal contract. |
| 2. Robustness | 8/10 | A + C | Non-fatal try/except wrapper. `dataclasses.replace()` for immutability. Pre-computed caches. |
| 3. Security Posture | 7/10 | A + C | Suppression-gate integration proven by Tier A tests. No I/O beyond graph queries. |
| 4. Adversarial Resilience | 5/10 | A + C | No adversarial fixtures. Suppression maps are hardcoded — no user-controlled input. But no evasion/manipulation tests. |
| 5. Auditability & Traceability | 7/10 | A + C | `suppression_reason` traces why a finding was suppressed. Velocity includes review count. Logging on error. |
| 6. Test Quality | 8/10 | A | 24 tests across 10 classes. Suppression-gate integration (3), evidence preservation (1), error resilience (2), suppression specificity (3). |
| 7. Convention Adherence | 8/10 | A | ruff, mypy strict, bandit clean. SPDX header. Cross-phase import of graph_store (justified). |
| 8. Documentation Accuracy | 7/10 | C | Accurate docstrings. Non-fatal behavior documented. Suppression maps not documented. |
| 9. Performance | 7/10 | C | Pre-computed caches reduce graph queries. O(results) per pass, 4 passes total. |
| 10. Dead Code / Debt | 9/10 | A + C | Zero TODOs, all functions called. `persist_rule_findings` used in review.py. |
| 11. Dependency Hygiene | 7/10 | A | 3 internal deps including cross-phase graph_store (Phase 2). Justified by design. |
| **Overall** | **7.4/10** | | **Average of 11 dimensions** |

**Health status:** Adequate (provisional)

**Determination:**
1. Average-based status: 7.4/10 falls in 6.0-7.9 range = Adequate
2. Override gates: None fired.
3. Ceiling gates: Adversarial soft floor fired (Dim 4 = 5 < 6). Caps at Adequate. Consistent with average-based determination.
4. Suffixes: `(provisional)` — dims 3, 5, 8, 9 include Tier C evidence components.

**Override gates fired:** None
**Ceiling gates fired:** Adversarial soft floor (Dim 4 = 5)

---

## Checklist: SR-01 through SR-09

| ID | Verdict | Evidence | Notes |
|----|---------|----------|-------|
| SR-01 | PASS (reinterpreted) | Tier A: 24 tests cover all 4 enrichment dimensions. Blast radius: 3 tests (dependents, no dependents, not-in-graph). Recurrence: 3 tests (recurring, non-recurring, different rule_id). Suppression: 6 tests (import-based, path-based, no-match, unregistered rule, case-insensitive, dynaconf). Velocity: 2 tests (with history, empty). Plus: persistence round-trip (1), multi-result independence (1), passthrough (2), evidence preservation (1), error resilience (2), gate integration (3). | **Reinterpretation:** For enrichment, SR-01 means "all documented enrichment dimensions are tested" rather than "all detection patterns are tested." |
| SR-02 | N/A | No compiled regex patterns. Enrichment uses graph queries and dict lookups, not regex matching. | Enrichment has zero regex patterns — SR-02 is structurally inapplicable. |
| SR-03 | N/A | Enrichment does not assign severity. It adds `ResultEnrichment` metadata to existing findings without modifying severity. Suppression affects gate behavior via `check_gate()`, which is owned by engine.py. | Enrichment preserves original severity unchanged (Tier A: `test_original_fields_preserved`). |
| SR-04 | N/A | Enrichment does not scan diffs. It receives `list[RuleResult]` from upstream rules that have already filtered to added lines. | No diff scanning at all — structurally inapplicable. |
| SR-05 | PASS (reinterpreted) | Tier A: `test_original_fields_preserved` proves `rule_id`, `severity`, `message`, `file`, `line`, `evidence` all survive enrichment unchanged. `dataclasses.replace()` at line 71 creates a new instance — original is not mutated. | **Reinterpretation:** For enrichment, SR-05 means "original finding evidence is preserved" rather than "evidence is human-readable." |
| SR-06 | N/A | Ownership: engine-owned. | Per SR-06 scope note. |
| SR-07 | PASS | Tier C: Enrichment adds `ResultEnrichment` fields: `blast_radius` (int), `is_recurring` (bool), `prior_count` (int), `suppressed` (bool), `suppression_reason` (str), `velocity` (str). None contain raw secret values. `suppression_reason` contains import path substrings (e.g., "file imports sqlalchemy") and file path substrings (e.g., "file path contains 'cache'") — not credentials. | No secret leakage risk in enrichment metadata. |
| SR-08 | Self-referential | Tier A: This IS the enrichment layer. All tests verify that `ResultEnrichment` dataclass is correctly attached to `RuleResult` via `dataclasses.replace()`. The enrichment output IS the enrichment format. | SR-08 is self-referential for this unit. Reinterpret as: "enrichment output is compatible with downstream consumers (check_gate, mcp_response, github_review)." |
| SR-09 | Partial | Tier A: Positive (12: blast, recurrence, suppression, velocity, persistence, multi-result), negative (5: no dependents, not-in-graph, non-recurring, different-rule, no-suppression), edge (2: passthrough for None store and empty results), error-resilience (2: graph exception, persist error), gate-integration (3: suppressed/unsuppressed/still-in-results). Missing: adversarial (no crafted graph data attacks), renamed files, large graph stress tests. | See F-ENR-001. |

**N/A items:** 4/9 (SR-02, SR-03, SR-04, SR-06). At 44%, just below the >50% reclassification threshold. This is expected — enrichment is categorized as `security-rule` in the registry but functionally is a post-processor, not a detector.

---

## Findings

### F-ENR-001: No adversarial or stress tests for graph-derived enrichment

**Severity:** MEDIUM
**Status:** OPEN
**Checklist:** SR-09, Dim 4
**Evidence tier:** C (manual review of test file and source)

**Description:** The test suite has strong functional coverage (24 tests, all 4 enrichment dimensions) but zero adversarial fixtures. Specific gaps:

1. **Suppression map manipulation:** No test verifying that a crafted graph with misleading import edges cannot cause inappropriate suppression of critical findings. The `_SUPPRESSION_MAP` is hardcoded (not user-controlled), which limits the attack surface, but the graph data that feeds into suppression decisions IS derived from the codebase (which is attacker-influenced in a PR review context).

2. **Large graph stress:** No test with hundreds of nodes/edges to verify enrichment doesn't degrade with large codebases.

3. **Malformed graph data:** No test verifying behavior when graph nodes have missing or unexpected `data` fields (e.g., `node.data.get("rule_id")` returns None).

**Impact:** MEDIUM — The suppression-gate integration is security-critical: enrichment suppression controls whether ERROR findings block merges. While suppression maps are hardcoded (limiting direct manipulation), the graph data feeding recurrence and blast radius queries comes from codebase indexing, which processes PR content. A malicious PR could influence graph state in ways that affect future enrichment decisions.

**Mitigating factors:** (1) Suppression maps are hardcoded constants, not graph-derived. (2) The entire enrichment is wrapped in try/except with fallback to originals. (3) Graph queries are read-only during enrichment (persist is separate).

**Recommendation:** Add 2-3 adversarial tests: (a) malformed graph node data, (b) large-graph stress, (c) verify suppression maps cannot be influenced by graph content. This would raise Dim 4 from 5 to 6-7.

### Compound Chain Exposure

**Identified:** Suppression → gate bypass chain. `_SUPPRESSION_MAP` entries → `enrichment.suppressed=True` → `check_gate()` skips finding → ERROR-level finding does not block merge. This is **by design** (import-based false-positive suppression), but the chain means incorrect suppression has direct security impact.

**Scope:** The chain is bounded by:
1. Suppression maps are hardcoded in enrichment.py (not configurable, not graph-derived).
2. Only 2 rule_ids have import suppression (`sql-injection-risk`, `hardcoded-credentials`). Only 1 has path suppression (`weak-crypto`).
3. `check_gate()` is the only consumer of the `suppressed` field in the gate path.

**Risk assessment:** LOW — the chain exists and is security-relevant, but all three inputs are static. No user-controlled data enters the suppression decision. The risk is in the suppression map being wrong (false-negative suppression), not in it being manipulated.

---

## Dimension Details

### 1. Contract Fidelity

**Key question:** Do types, exports, and validation faithfully represent the unit's contract?

**Score:** 8/10
**Evidence:**
- mypy strict passes with zero issues (Tier A: static analysis).
- All functions fully typed, including complex return types: `dict[str, int]`, `dict[tuple[str, str], tuple[bool, int]]`, `dict[tuple[str, str], tuple[bool, str]]` (Tier A: mypy proves this).
- `ResultEnrichment` dataclass (in rules/base.py) defines the formal enrichment contract: 6 typed fields, frozen=True (Tier A).
- `enrich_results()` public function has complete signature: `(results: list[RuleResult], graph_store: SQLiteGraphStore | None) -> list[RuleResult]` (Tier A).
- `persist_rule_findings()` public function: `(store: SQLiteGraphStore, findings: list[RuleResult], review_id: str) -> None` (Tier A).
- `dataclasses.replace()` at line 71 preserves the frozen dataclass contract — does not mutate original (Tier A: `test_original_fields_preserved`).
- **Above 7** because `ResultEnrichment` is a formal typed contract, and all internal functions have rich type annotations for complex dict structures.
- Calibration: above rule-sql (7), rule-traversal (7). Richer type signatures, formal enrichment contract.

---

### 2. Robustness

**Key question:** Does the unit handle errors, retries, and edge cases correctly?

**Score:** 8/10
**Evidence:**
- **Non-fatal wrapper (Tier A):** `enrich_results()` wraps `_do_enrich()` in try/except at line 41-45. Any exception logs a warning and returns original results unchanged. Proven by `test_graph_exception_returns_originals`.
- **`persist_rule_findings` non-fatal (Tier A):** Per-finding try/except at line 221. Inner try/except at line 219 handles missing file nodes. Proven by `test_persist_nonfatal_on_error`.
- **Immutability (Tier A):** `dataclasses.replace()` creates new RuleResult instances — originals never mutated. Proven by `test_original_fields_preserved`.
- **None store handling (Tier A):** `if graph_store is None` at line 38 returns immediately. Proven by `test_none_graph_returns_unchanged`.
- **Empty results handling (Tier A):** `if not results` at line 38 returns immediately. Proven by `test_empty_results_returns_empty`.
- **Pre-computed caches:** `unique_files`, `unique_pairs`, `imports_cache` prevent redundant graph queries across results.
- **Duplicate suppression key handling:** `if key in out: continue` at line 130 prevents redundant suppression checks.
- **Above 7** because non-fatal design, immutability, and pre-computation are deliberate robustness features.
- Calibration: above rule-creds (7), rule-deser (7). Non-fatal wrapper and immutability are stronger robustness properties than false-positive suppression layers.

---

### 3. Security Posture

**Key question:** Does the unit protect against injection, leakage, and unauthorized access?

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 7/10
**Evidence:**
- **Suppression-gate integration (Tier A):** 3 tests prove the core semantic contract: suppressed findings stay in results but don't trigger `check_gate()`, unsuppressed findings do trigger the gate.
- No network, no subprocess, no file I/O beyond SQLite graph queries (Tier C).
- Enrichment metadata contains no secret values (Tier C: SR-07 analysis).
- Suppression maps are hardcoded constants — not configurable, not user-controlled (Tier C).
- Graph queries are read-only during enrichment — `persist_rule_findings` is a separate function called at a different stage (Tier C).
- Logging uses `log.warning()` with `exc_info=True` — exception details only go to server logs, not to PR comments (Tier C).
- Not 8: Compound chain exposure exists (suppression → gate bypass). While bounded and by-design, it's a security-relevant data flow.
- Calibration: matches rule-sql (7), rule-traversal (7). The suppression-gate chain is unique to this unit.

---

### 4. Adversarial Resilience

**Key question:** Can the unit resist adversarial input from untrusted PR content and prompt injection?

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 5/10
**Evidence:**
- **No adversarial test fixtures (Tier C).** This is the primary gap. No tests for malformed graph data, large graph stress, or suppression boundary manipulation.
- **Suppression maps are static (Tier C):** `_SUPPRESSION_MAP` and `_PATH_SUPPRESSION_MAP` are hardcoded dict constants. No user input can modify them at runtime. This limits the direct attack surface.
- **Graph data is indirectly attacker-influenced (Tier C):** The graph store is populated during codebase indexing, which processes the repository. A malicious PR could introduce import edges that affect future suppression decisions — but only for the 2 rule_ids in `_SUPPRESSION_MAP` and only if the graph store persists across reviews.
- **Non-fatal wrapper provides defense-in-depth (Tier A):** Any graph corruption that causes exceptions returns original (unsuppressed) results — fail-safe.
- **Below 6** because zero adversarial fixtures is a genuine gap for a security-relevant unit. The static suppression maps mitigate but don't eliminate the concern. F-ENR-001 documents the gap.
- Calibration: below rule-sql (6), rule-traversal (6) which have ReDoS tests. At parity with rule-secrets (5) which also lacked adversarial fixtures at initial audit.

---

### 5. Auditability & Traceability

**Key question:** Can operators investigate failures, reproduce review results, and trace the decision path from input to output?

**Score:** 7/10
**Evidence:**
- **Suppression reason (Tier A):** `suppression_reason` field records why a finding was suppressed: `"file imports sqlalchemy"` or `"file path contains 'cache'"`. Operators can trace suppression decisions.
- **Velocity string (Tier A):** `"3 sql-injection-risk finding(s) across last 3 reviews"` — includes count and review window.
- **Logging on error (Tier C):** `log.warning("Rule enrichment failed (non-fatal)", exc_info=True)` and `log.warning("Failed to persist rule finding %s (non-fatal)", r.rule_id, exc_info=True)`. Exceptions are logged with traceback.
- **Deterministic:** Same results + same graph state → same enrichment output. Fully reproducible.
- **Graph-derived values are traceable (Tier C):** blast_radius = count of incoming IMPORTS edges. is_recurring = count of FOUND_IN edges with matching rule_id. All derive from explicit graph queries.
- Not 8: No trace correlation IDs. Logging doesn't include which file or rule triggered the enrichment attempt.
- Calibration: above rule-sql (6), rule-llm-sinks (6). `suppression_reason` adds explicit traceability that detector rules lack.

---

### 6. Test Quality

**Key question:** Do tests verify meaningful behavior with good coverage?

**Score:** 8/10
**Evidence:**
- **Test count:** 24 tests across 10 test classes (Tier A).
- **Source:test ratio:** 1.71:1 (381 LOC tests / 223 LOC source).
- **Fixture matrix categories covered:**
  - Positive: 12 tests (blast 3, recurrence 3, suppression 3, velocity 2, persistence 1).
  - Negative: 5 tests (no dependents, not-in-graph, non-recurring, different-rule, no-suppression).
  - Edge: 2 tests (None graph store, empty results list).
  - Error resilience: 2 tests (graph exception, persist error).
  - Gate integration: 3 tests (suppressed skips gate, unsuppressed triggers gate, suppressed stays in list).
  - Evidence preservation: 1 test (original fields unchanged).
  - Suppression specificity: 3 tests (unregistered rule, case-insensitive path, dynaconf import).
- **The gate integration tests are unique to this unit** — they prove the security-critical property that suppression affects merge-blocking behavior.
- Missing: adversarial (F-ENR-001). No large-graph stress tests.
- **Above 7** because 24 tests with gate integration and error resilience coverage is thorough. The gap is adversarial, not functional.
- Calibration: above rule-creds (8: 24 tests but different profile). Matches on test count, stronger on semantic coverage (gate integration).

---

### 7. Convention Adherence

**Key question:** Does the unit follow Grippy project patterns?

**Score:** 8/10
**Evidence:**
- SPDX header present on source and test file (Tier A).
- ruff check passes with zero issues (Tier A).
- mypy strict passes with zero issues (Tier A).
- bandit passes with zero issues (Tier A).
- Test file follows mirror structure: `src/grippy/rules/enrichment.py` → `tests/test_grippy_rules_enrichment.py` (Tier A).
- Test file exceeds 50 LOC minimum (381 LOC) (Tier A).
- Uses `dataclasses.replace()` for immutable updates — Python best practice (Tier C).
- Uses `logging.getLogger(__name__)` — standard logging convention (Tier C).
- **Cross-phase import:** Imports `SQLiteGraphStore` from `graph_store` (Phase 2) and `graph_types` (Phase 1). This is a cross-phase dependency — enrichment.py is Phase 1 but depends on Phase 2. Justified by design: enrichment IS the bridge between rule findings and graph context.
- Not 9: Cross-phase dependency is a convention divergence. `# nosec B110` comment for bare except on file node edge.
- Calibration: below rule-sql (9), rule-ci-risk (9) due to cross-phase import. Same level as rule-llm-sinks (8) which has DiffHunk import divergence.

---

### 8. Documentation Accuracy

**Key question:** Do docstrings, comments, and docs match actual behavior?

**Score:** 7/10
**Evidence:**
- File-level docstring: "Post-processor that enriches rule results with graph-derived context." (line 2) — accurate (Tier C).
- `enrich_results()` docstring: documents None graph_store behavior and non-fatal nature (lines 33-37) — accurate (Tier C).
- `_do_enrich()` docstring: "Internal enrichment — all four passes." — accurate (Tier C).
- Each compute function has a one-line docstring (lines 90, 103, 118, 164) — accurate (Tier C).
- `persist_rule_findings()` docstring: documents node creation and non-fatal behavior (lines 196-200) — accurate (Tier C).
- `_SUPPRESSION_MAP` comment: "rule_id -> list of import path substrings that suppress it" (line 17) — accurate (Tier C).
- `_PATH_SUPPRESSION_MAP` comment: "rule_id -> list of file path substrings that suppress it" (line 23) — accurate (Tier C).
- Not 8: No documentation of WHY specific suppression entries exist (e.g., why sqlalchemy suppresses sql-injection-risk). No documentation of the suppression → gate bypass chain.
- Calibration: matches rule-sql (7), rule-ci-risk (7). Below rule-deser (8) which has excellent cross-rule coordination comments.

---

### 9. Performance

**Key question:** Is the unit efficient for its workload?

**Score:** 7/10
**Evidence:**
- **Pre-computed caches (Tier C):** `unique_files`, `unique_pairs`, `imports_cache` computed once and reused across all results. Prevents redundant graph queries.
- **4-pass architecture (Tier C):** `_compute_blast_radius`, `_compute_recurrence`, `_compute_suppression`, `_compute_velocity`. Each pass iterates results once. Total: O(4 * results + graph_queries).
- **Duplicate key skipping (Tier C):** `unique_files = list(dict.fromkeys(...))` and `unique_pairs` deduplicate to minimize graph queries.
- **imports_cache per file (Tier C):** `imports_cache[path]` computed once per unique file, reused for all results on that file.
- **Velocity query (Tier C):** `store.get_recent_nodes(limit=20, types=[NodeType.REVIEW])` — bounded at 20 reviews. Then iterates PRODUCED edges for each review.
- Not 8: Velocity computation makes N+1 graph queries (1 for reviews, N for each review's findings). For 20 reviews with many findings, this could be slow. No profiling data.
- Calibration: below rule-sql (8), rule-ci-risk (8) which are O(lines × patterns) with compiled regexes. Graph queries are inherently slower than regex matching.

---

### 10. Dead Code / Debt

**Key question:** Is the unit free of unused code and tracked debt?

**Score:** 9/10
**Evidence:**
- Zero `TODO` or `FIXME` comments (Tier A: grep search).
- All functions called: `enrich_results` from review.py and rules/__init__.py, `persist_rule_findings` from review.py (Tier C: grep callers).
- All 4 compute functions called in `_do_enrich()` (lines 57-60) (Tier C).
- `_SUPPRESSION_MAP` used at line 144, `_PATH_SUPPRESSION_MAP` used at line 134 (Tier C).
- ruff detects no unused imports (Tier A).
- `# nosec B110` on bare except at line 219 — acknowledged and justified (file node may not exist in graph).
- Not 10: F-ENR-001 identifies adversarial test gaps.
- Calibration: matches rule-sql (9), rule-ci-risk (9).

---

### 11. Dependency Hygiene

**Key question:** Are unit boundaries clean with no circular or unnecessary deps?

**Score:** 7/10
**Evidence:**
- **3 internal dependencies:**
  1. `grippy.graph_store` (SQLiteGraphStore) — Phase 2, cross-phase dependency.
  2. `grippy.graph_types` (EdgeType, NodeType, _record_id) — Phase 1, same phase.
  3. `grippy.rules.base` (ResultEnrichment, RuleResult) — Phase 1, same phase.
- **2 external dependencies:** `logging` and `collections.Counter` (both stdlib) (Tier A).
- **1 stdlib utility:** `dataclasses.replace` (Tier A).
- No circular imports (Tier A: ruff check).
- **Cross-phase dependency analysis:** `graph_store` is Phase 2, but rule-enrichment is Phase 1. This is a dependency inversion — enrichment.py depends on a higher-phase module. Justified: enrichment IS the bridge between the rules subsystem (Phase 1) and the graph subsystem (Phase 2). The alternative (putting enrichment in Phase 2) would make it unavailable during Phase 1 testing.
- **Below 8** because the cross-phase dependency is real and notable, even if justified.
- Calibration: below rule-sql (9), rule-ci-risk (9). Cross-phase dependency is a meaningful hygiene cost.
