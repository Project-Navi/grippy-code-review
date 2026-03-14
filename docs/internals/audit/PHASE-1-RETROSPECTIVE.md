# Phase 1 Audit Retrospective — Grippy

**Date:** 2026-03-14
**Scope:** 20/30 units audited (Phase 0 leaf + Phase 1 core infra)
**Auditor:** Claude Opus 4.6 / Nelson Spence
**Methodology:** v1.0 (11 dimensions, v4.1 gate model, 6 checklists)

---

## 1. Score Distribution

### Overall Scores

| Score | Units | Count |
|-------|-------|------:|
| 8.4 | local-diff | 1 |
| 7.9 | retry | 1 |
| 7.7 | schema | 1 |
| 7.6 | embedder, ignore, rule-engine, graph-types, rule-creds | 5 |
| 7.5 | rule-crypto, rule-ci-risk, rule-deser | 3 |
| 7.4 | imports, rule-sinks, rule-workflows, rule-sql, rule-traversal, rule-enrichment | 6 |
| 7.2 | rule-secrets | 1 |
| 7.1 | rule-llm-sinks | 1 |

**Mean:** 7.49 | **Median:** 7.45 | **Range:** 7.1–8.4 | **Std dev:** 0.27

19/20 units land between 7.1 and 7.7. Only local-diff (8.4) breaks out. The cluster is tight — almost too tight. This means either the codebase is genuinely uniform in quality, or the scoring rubric compresses real variation.

**Assessment:** Mostly genuine uniformity. Phase 0+1 are leaf nodes and detector rules sharing the same patterns (`ctx.added_lines_for()`, compiled regexes, `RuleResult` output). The tight band reflects real architectural consistency. Phase 2+3 units (prompts, codebase, agent) will have more structural variation.

### Health Status Distribution

| Status | Count | Units |
|--------|------:|-------|
| Healthy (provisional) | 1 | local-diff |
| Needs Attention | 1 | retry |
| Adequate (provisional) | 18 | everything else |

**The `(provisional)` suffix is on 19/20 units.** See Section 4 for whether this is informative or wallpaper.

### Dimension Score Heat Map

| Dim | Name | Min | Max | Mean | Most Common | Signal? |
|-----|------|-----|-----|------|-------------|---------|
| 1 | Contract Fidelity | 7 | 8 | 7.4 | 7 | Low — mypy strict + typed dataclasses make this a pass/fail check |
| 2 | Robustness | 6 | 8 | 6.8 | 6 | Moderate — splits between simple rules (6) and infrastructure (7-8) |
| 3 | Security Posture | 6 | 9 | 7.1 | 7 | Moderate — local-diff's 9 reflects TB-2 anchor hardening |
| 4 | Adversarial Resilience | 5 | 8 | 6.2 | 6 | **High — this is the discriminative dimension** |
| 5 | Auditability | 5 | 8 | 6.3 | 6 | Moderate — rules with generic messages score lower |
| 6 | Test Quality | 6 | 8 | 7.2 | 7 | Moderate — Batch 3A raised the bar with dedicated redaction tests |
| 7 | Convention Adherence | 8 | 9 | 8.9 | 9 | **None — 18/20 score 9.** This is a formatting check, not analysis. |
| 8 | Documentation Accuracy | 7 | 8 | 7.2 | 7 | Low — consistent 7 across most units |
| 9 | Performance | 7 | 8 | 7.8 | 8 | Low — compiled regexes are compiled regexes |
| 10 | Dead Code / Debt | 8 | 10 | 9.1 | 9 | **None — 17/20 score 9.** Clean codebase, not an audit finding. |
| 11 | Dependency Hygiene | 7 | 10 | 9.0 | 9 | Low — leaf nodes trivially score high |

### Discriminative vs Non-Discriminative Dimensions

**Discriminative (carry real signal):**
- **Dim 4 (Adversarial Resilience):** Range 5–8, mean 6.2. This is where the audit found real gaps. The soft floor gate fired on 2 units (rule-secrets, rule-enrichment). Pre-Batch testing raised most units from 5→6.
- **Dim 2 (Robustness):** Range 6–8. Splits infrastructure (7-8) from simple detectors (6).
- **Dim 5 (Auditability):** Range 5–8. Pattern-specific messages score higher than generic ones.

**Non-discriminative (politely varying between fixed values):**
- **Dim 7 (Convention Adherence):** 18/20 score 9. ruff + mypy + SPDX header = 9. The only variation is import convention observations.
- **Dim 10 (Dead Code / Debt):** 17/20 score 9. Zero TODOs across the codebase.
- **Dim 11 (Dependency Hygiene):** Leaf nodes have 0-2 deps. Always 8-10.
- **Dim 9 (Performance):** Compiled regexes are compiled regexes. Always 7-8.

**Recommendation for Phase 2:** Do not drop non-discriminative dimensions (they anchor the rubric), but expect them to vary more when auditing orchestration units with real dependency graphs, external I/O, and runtime performance concerns (agent, codebase, mcp-server).

---

## 2. Real Code Defects vs Documentation Gaps

### Genuine Code Defects (required code changes)

| Finding | Severity | Unit | What | Impact |
|---------|----------|------|------|--------|
| **F-CRD-001** | HIGH | rule-creds | `_redact()` didn't cover Bearer/Basic/Token auth header values | Unredacted tokens in evidence → enrichment → prompt → GitHub posting. **Real security fix.** |
| F-IMP-001 | MEDIUM | imports | Uncaught `ValueError` in `_resolve_relative_import()` | Edge case crash on malformed relative imports. **Resolved.** |

**2 code defects found in 20 units.** F-CRD-001 is the only security-relevant one. It justified the entire Phase 1 exercise — the compound chain exposure (evidence → enrichment → prompt → GitHub) is exactly the kind of hidden data flow that manual review misses.

### Evidence-Only Findings (test/documentation gaps, no code change needed)

| Category | Count | Examples |
|----------|------:|---------|
| Fixture matrix gaps (missing test categories) | 10 | F-SNK-001, F-RW-001, F-CRY-001, F-SQL-001, F-TRV-001, F-CIR-001, F-LLM-001, F-DSR-001, F-SCH-002, F-RS-002 |
| Missing adversarial/stress tests | 2 | F-RS-001, F-ENR-001 |
| Design observations (accepted) | 3 | F-EMB-001, F-SCH-001, F-IMP-002 |
| Documentation gaps | 0 | — |

**10/17 findings are fixture matrix gaps.** This is the dominant finding class. Every single detector rule had a "positive-heavy fixture matrix" or "missing edge-case category" finding. This is a real pattern worth addressing, but it's also the most predictable kind of finding.

### Finding Severity Distribution

| Severity | Count | Status |
|----------|------:|--------|
| HIGH | 2 | Both RESOLVED (F-CRD-001 code fix, F-RY-001 acknowledged) |
| MEDIUM | 2 | F-RS-001 OPEN, F-ENR-001 OPEN |
| LOW | 13 | 3 RESOLVED, 10 OPEN |

**No CRITICAL findings.** The 2 MEDIUM findings both involve adversarial test gaps — no proven exploitable behavior, but unproven safety in adversarial conditions.

---

## 3. Recurring False-Friction Patterns

### Pattern A: SR-06 Ownership (N/A for all individual rules)

SR-06 (profile activation) is engine-owned, not rule-owned. Every rule scorecard marks it N/A. This is correct behavior — the checklist correctly identifies that rules don't own profile dispatch. But it means 1/9 checklist items is consistently non-applicable for the largest unit family (10 rules).

**Verdict:** Not friction — this is the checklist correctly encoding the ownership boundary. Keep it. Phase 2 units (prompts, codebase) may actually exercise SR-06's engine-level equivalent.

### Pattern B: Fixture Matrix Findings Are Predictable

10/17 findings are "fixture matrix missing X category." After the first 3 rule audits, the pattern is clear: every rule will have this finding unless pre-seeded with adversarial/edge/negative tests.

**Verdict:** This is a framework signal, not a framework failure. The audit correctly identifies a systemic gap. However, the finding texts are becoming template-like. Phase 2 should document this as a **known pattern** rather than treating each instance as a discovery.

### Pattern C: Dim 4 Scoring Requires Adversarial Tests Before Audit

The ReDoS + long-line tests added in Batch 2 raised every rule's Dim 4 from 5→6. Without those tests, the adversarial soft floor would have fired on every rule, making all of them cap at Adequate with a gate note.

**Verdict:** The Commit 1 pattern (add evidence before scoring) is the right workflow. Phase 2 should continue this: adversarial tests in Commit 1, scorecard in Commit 2.

### Pattern D: Per-Rule vs Engine/Enrichment Responsibility

Observed in multiple units:
- `_in_tests_dir()` appears in rule-crypto but not other rules — per-rule noise suppression vs engine-level filtering
- `ctx.added_lines_for()` vs direct iteration — rule-traversal uses direct iteration, others use the helper
- Suppression logic lives in enrichment, gate consumption in engine, detection in rules

**Verdict:** The ownership split is currently defensible — each boundary is clear and consistent within its scope. But Phase 2 (graph-store, graph-context) will test whether the enrichment↔engine boundary holds under more complex data flows.

---

## 4. What Does "Provisional" Mean in Practice?

**19/20 units carry the `(provisional)` suffix.** The suffix means "at least one dimension includes Tier C (manual trace) evidence."

### Is it informative or wallpaper?

Looking at which dimensions trigger `(provisional)`:
- Dims 5, 8, 9 are **always Tier C** for every unit (auditability, documentation, performance all require human judgment)
- Dim 3 (Security Posture) is Tier C for most rules (security properties verified by trace, not machine)
- Only Dim 1 (Contract Fidelity), Dim 6 (Test Quality), Dim 7 (Convention), Dim 10 (Dead Code), Dim 11 (Deps) are consistently Tier A

**Assessment: The suffix is becoming wallpaper.** If every unit is provisional because dims 5/8/9 are inherently Tier C, the suffix no longer carries information. It's a property of the rubric, not the codebase.

### Options

1. **Remove the suffix** — accept that some dimensions are inherently Tier C. "Adequate" without qualifier.
2. **Redefine `(provisional)`** — only trigger it when *security-critical* dimensions (3, 4) are Tier C. This would make the suffix meaningful: "we haven't machine-proven the security properties."
3. **Keep as-is** — it's technically correct even if uninformative.

**Recommendation:** Option 2. Redefine `(provisional)` to trigger only when Dim 3 or Dim 4 evidence is Tier C. This makes the suffix meaningful: it flags units where security claims rest on manual traces rather than machine-verifiable evidence. Under this rule, local-diff would lose its `(provisional)` (Dim 3 = A+C, Dim 4 = A) and units with only Tier A adversarial tests (post-Batch-2 rules) would also lose it. Units like rule-secrets (Dim 4 = 5, mixed evidence) would keep it.

---

## 5. Phase 2 Risk Posture

### What changes in Phase 2

Phase 2 units (graph-store, graph-context, prompts, codebase) are structurally different from Phase 1:

| Property | Phase 1 Units | Phase 2 Units |
|----------|---------------|---------------|
| I/O | None (pure compute) | SQLite (graph-store), file system (codebase), prompt files (prompts) |
| Trust boundaries | TB-2 partial (rules consume diffs) | TB-3 (prompts), TB-4 (codebase) — LLM-facing |
| External deps | 0-2 internal | graph-store depends on SQLAlchemy, codebase on LanceDB |
| Attack surface | Regex patterns | File traversal (codebase), prompt injection resistance (prompts) |
| Checklist | SR (security-rule) for 10 units | Infrastructure (IF), data-model (DM) — different invariants |
| Test complexity | Fake diffs in, RuleResult out | Requires mock filesystems, databases, embeddings |

### Is the framework trustworthy enough?

**Yes, with adjustments.** The framework proved it can:
- Find real code defects (F-CRD-001)
- Distinguish security properties from hygiene checks (Dim 4 vs Dim 7)
- Encode gate semantics that prevent score-washing (adversarial soft floor fired twice)
- Track ownership boundaries (enrichment solo audit proved the suppression-gate chain)

**But Phase 2 needs:**
1. **New checklist types.** IF (infrastructure) and DM (data-model) checklists exist but haven't been battle-tested on complex units. graph-store has migrations, codebase has tool_hooks — these need checklist coverage.
2. **Richer adversarial scenarios.** Phase 1 adversarial tests were ReDoS + long-line. Phase 2 needs path traversal attacks (codebase), prompt injection probes (prompts), and SQL injection against graph_store.
3. **Cross-unit integration tests.** The enrichment→gate chain was the first cross-unit property tested. Phase 2 has more: graph-store→graph-context→prompts is a data pipeline that feeds the LLM.

---

## 6. Remediation Queue (Risk-Ranked)

### Priority 1 — Security-relevant, should fix before Phase 2

| Finding | Severity | Unit | Risk | Effort |
|---------|----------|------|------|--------|
| F-ENR-001 | MEDIUM | rule-enrichment | Graph-derived enrichment (blast radius, recurrence) processes data from codebase indexing. No adversarial proof that malicious graph state can't bias enrichment. | 2-3 tests |
| F-RS-001 | MEDIUM | rule-secrets | No ReDoS tests on rule-secrets patterns. All other rules have them. | 2-3 tests (follow Batch 2 pattern) |

### Priority 2 — Systematic fixture gap, batch-addressable

| Finding Class | Count | Affected Units | Approach |
|---------------|------:|----------------|----------|
| Fixture matrix gaps | 10 | All detector rules except rule-creds | Single batch PR adding 1-2 edge/negative tests per rule. ~20 tests total. |

### Priority 3 — Low-risk, defer to organic development

| Finding | Unit | Why Defer |
|---------|------|-----------|
| F-RY-001 | retry | File-set validation path is defense-in-depth, not primary security. Test when retry is next modified. |
| F-RY-002 | retry | Lazy import is a style choice, not a defect. |
| F-SCH-001 | schema | Frozen model asymmetry is documented design choice. |
| F-EMB-001 | embedder | Passthrough params are consumed by OpenAI SDK, not user-facing. |

---

## 7. Phase 2 Entry Plan

### Recommended Unit Order

1. **graph-store** — SQLite persistence, migrations, node/edge CRUD. Infrastructure checklist. Lower trust-boundary weight than codebase/prompts. Tests require SQLite fixtures.
2. **graph-context** — Traverses graph-store output to build context packs. Depends on graph-store. Test after graph-store audit confirms store behavior.
3. **prompts** — TB-3 anchor. Loads 20 markdown files into prompt chain. Prompt injection resistance is the key property. Adversarial tests need crafted prompt files.
4. **codebase** — TB-4 anchor. LLM-facing tools (read_file, grep_code, list_files). Path traversal, symlink following, glob timeout, tool_hooks sanitization. **Highest risk unit in Phase 2.**

### Cadence

Phase 1 averaged 3-4 units per batch across 7 batches (pilot + 6 waves). Phase 2 units are more complex — recommend **2 units per batch** with richer Commit 1 test additions.

### Framework Adjustments for Phase 2

1. **Provisional suffix:** Redefine to trigger only on Dim 3/4 Tier C evidence (see Section 4).
2. **Known pattern: fixture matrix gaps.** Document as a systemic observation in the methodology rather than rediscovering per-unit.
3. **Cross-unit properties.** Each Phase 2 scorecard should include a "Cross-Unit Dependencies" section documenting data flows to/from other audited units.
4. **Checklist validation.** IF and DM checklists need the same battle-testing that SR got in Phase 1. First Phase 2 batch should explicitly validate checklist coverage.

---

## Summary

Phase 1 found what it was supposed to find. One real security fix, one structural insight (suppression-gate chain), and a clear picture of the codebase's quality floor. The framework works. The tight score distribution reflects genuine consistency in Phase 0+1, not rubric compression.

The question entering Phase 2 is not "does the framework work?" but "does it work on units that talk to LLMs, file systems, and databases?" That's a different kind of stone.
