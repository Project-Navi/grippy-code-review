# Superset Analysis — Grippy

**Sweep date range:** 2026-03-13 -- 2026-03-15
**Units audited:** 30 / 30
**Commit range:** `cebbcab`..`3cb362d`

---

## 1. Executive Summary

**Theme 1: Fixture matrix gaps are the dominant finding class.** 14 of 32 findings (44%) are KRC-01 instances — test suites missing one or more fixture categories (adversarial, edge, negative). This is a systemic pattern identified during Phase 1 and formally classified in methodology v1.2. The findings are real (test coverage is genuinely incomplete in these categories) but predictable and batch-addressable.

**Theme 2: Delegation carries the security story.** Trust boundary defense is concentrated in 7 anchor-owning units (agent, retry, github-review, codebase, local-diff, rule-engine, prompts). The remaining 23 units delegate to these anchors correctly. The system's security posture depends on anchor unit completeness, not fleet-wide adversarial testing. This is a strength, not a gap — clear ownership prevents diffuse responsibility.

**Theme 3: Adversarial Resilience (Dim 4) is the only discriminative dimension.** With a range of 5–8 and mean of 6.4, it is the only dimension that materially affected health status decisions. Convention Adherence (mean 8.9), Dead Code (mean 9.0), and Dependency Hygiene (mean 8.6) anchor the rubric but do not differentiate units.

**Theme 4: One open HIGH finding affects assurance, not correctness.** F-RY-001 (file-set validation path in TB-8 has zero test coverage) is the sole gate-firing finding in the entire codebase. The code exists and runs in production. The gap is in test evidence, not code behavior.

**Theme 5: Two confirmed code defects were found and resolved.** F-CRD-001 (unredacted auth tokens in evidence chain) and F-IMP-001 (uncaught ValueError in relative import resolution). Both fixed during the audit. This yield is consistent with a security-focused codebase with pre-existing CI and pre-commit hooks.

**Aggregate statistics:**

| Metric | Value |
|--------|-------|
| Total findings | 32 |
| CRITICAL | 0 |
| HIGH | 2 (1 open, 1 resolved) |
| HIGH (provisional) | 0 |
| MEDIUM | 3 (2 open, 1 resolved) |
| LOW | 27 (23 open, 4 resolved) |
| Units with HIGH+ findings | 2 / 30 |
| Mean scorecard score | 7.6 / 10 |

---

## 2. Finding Index

Flat routing table of all findings from 30 scorecards + 3 pilot FINDINGS.md files. Detail stays in source documents.

| Finding ID | Severity | Unit | Status | Theme |
|---|---|---|---|---|
| F-RY-001 | HIGH | retry | OPEN | Test Gaps |
| F-CRD-001 | HIGH | rule-creds | RESOLVED | Security Hardening |
| F-RS-001 | MEDIUM | rule-secrets | OPEN | Security Hardening |
| F-ENR-001 | MEDIUM | rule-enrichment | OPEN | Security Hardening |
| F-IMP-001 | MEDIUM | imports | RESOLVED | Correctness |
| F-SCH-001 | LOW | schema | OPEN | Design Observation |
| F-SCH-002 | LOW | schema | OPEN | Test Gaps (KRC-01) |
| F-SCH-003 | LOW | schema | OPEN | Design Observation |
| F-RS-002 | LOW | rule-secrets | OPEN | Test Gaps (KRC-01) |
| F-RS-003 | LOW | rule-secrets | OPEN | Hygiene |
| F-RY-002 | LOW | retry | OPEN | Hygiene |
| F-IGN-001 | LOW | ignore | RESOLVED | Correctness |
| F-IGN-002 | LOW | ignore | RESOLVED | Correctness |
| F-IMP-002 | LOW | imports | RESOLVED | Design Observation |
| F-EMB-001 | LOW | embedder | OPEN | Design Observation |
| F-SNK-001 | LOW | rule-sinks | OPEN | Test Gaps (KRC-01) |
| F-RW-001 | LOW | rule-workflows | OPEN | Test Gaps (KRC-01) |
| F-TRV-001 | LOW | rule-traversal | OPEN | Test Gaps (KRC-01) |
| F-LLM-001 | LOW | rule-llm-sinks | OPEN | Test Gaps (KRC-01) |
| F-CIR-001 | LOW | rule-ci-risk | OPEN | Test Gaps (KRC-01) |
| F-SQL-001 | LOW | rule-sql | OPEN | Test Gaps (KRC-01) |
| F-CRY-001 | LOW | rule-crypto | OPEN | Test Gaps (KRC-01) |
| F-DSR-001 | LOW | rule-deser | OPEN | Test Gaps (KRC-01) |
| F-GS-001 | LOW | graph-store | OPEN | Correctness |
| KRC-01 | LOW | graph-store | OPEN | Test Gaps (KRC-01) |
| F-GC-001 | LOW | graph-context | RESOLVED | Correctness |
| KRC-01 | LOW | graph-context | OPEN | Test Gaps (KRC-01) |
| F-PR-001 | LOW | prompts | OPEN | Test Gaps (KRC-01) |
| F-PR-002 | LOW | prompts | OPEN | Prompt & LLM Safety |
| F-CB-001 | LOW | codebase | OPEN | Correctness |
| F-CB-002 | LOW | codebase | OPEN | Test Gaps |
| F-CLI-01 | LOW | cli | OPEN | Correctness |

---

## 3. Pattern Clusters

### Cluster A: Fixture Matrix Gaps (KRC-01)

**Description:** Test suites with incomplete fixture category coverage. Missing categories typically include adversarial inputs, edge-case diff formats (renamed, binary, submodule), or negative fixtures. Formally classified as KRC-01 in methodology v1.2 to prevent theatrical rediscovery.

**Instance count:** 14 findings across 14 units

**Representative findings:**

| Finding ID | Unit | Gap |
|---|---|---|
| F-SCH-002 | schema | No test for missing required field rejection |
| F-RS-002 | rule-secrets | Missing adversarial, renamed/binary diff categories |
| F-SNK-001 | rule-sinks | Positive-heavy fixture matrix |
| F-RW-001 | rule-workflows | Positive-heavy fixture matrix |
| F-TRV-001 | rule-traversal | Positive-heavy fixture matrix |
| F-LLM-001 | rule-llm-sinks | Positive-heavy fixture matrix |
| F-CIR-001 | rule-ci-risk | Positive-heavy fixture matrix |
| F-SQL-001 | rule-sql | Positive-heavy fixture matrix |
| F-CRY-001 | rule-crypto | Positive-heavy fixture matrix |
| F-DSR-001 | rule-deser | Positive-heavy fixture matrix |
| KRC-01 | graph-store | Missing edge-case fixture categories |
| KRC-01 | graph-context | Missing edge-case fixture categories |
| F-PR-001 | prompts | No adversarial test fixtures |
| F-CB-002 | codebase | No property-based testing for path traversal |

**Cross-unit compound risk:** None. Each KRC-01 instance is self-contained — fixture gaps in one rule do not amplify gaps in another.

**Systemic vs isolated:** Systemic. Affects 14/30 units. The pattern reflects an organic development style where positive fixtures are written during implementation and negative/adversarial fixtures are deferred. Batch-addressable with ~1-2 tests per instance.

### Cluster B: Adversarial Test Coverage Gaps

**Description:** Security-relevant code paths where adversarial testing is specifically missing, beyond the generic KRC-01 fixture pattern. These target trust-boundary-adjacent code and warrant individual attention rather than batch treatment.

**Representative findings:**

| Finding ID | Unit | Summary |
|---|---|---|
| F-RY-001 | retry | File-set validation in `_validate_rule_coverage()` has zero test coverage (TB-8) |
| F-RS-001 | rule-secrets | No Unicode homoglyph bypass or ReDoS adversarial tests |
| F-ENR-001 | rule-enrichment | No crafted import path adversarial tests for graph-derived enrichment |
| F-CB-002 | codebase | No property-based testing for path traversal defense (TB-4) |

**Cross-unit compound risk:** F-RY-001 affects CH-1 (Prompt Injection → Merge Block). If file-set validation can be bypassed, an attacker could attribute fabricated findings to wrong files without triggering a retry. The count validation (well-tested) still catches finding omission, limiting the attack surface.

**Systemic vs isolated:** Semi-systemic. Each finding targets a different trust boundary anchor, but all share the pattern of defense-in-depth code that exists and runs but lacks dedicated adversarial test evidence.

### Cluster C: Resolved Code Defects

**Description:** Findings where code was genuinely incorrect and required a fix. Both were resolved during the audit.

**Representative findings:**

| Finding ID | Unit | Summary |
|---|---|---|
| F-CRD-001 | rule-creds | `_redact()` didn't cover Bearer/Basic/Token auth header values. Unredacted tokens flowed through evidence → enrichment → prompt → GitHub posting. **Security fix.** |
| F-IMP-001 | imports | Uncaught `ValueError` in `_resolve_relative_import()` on malformed relative imports. Crash on edge-case input. |

**Cross-unit compound risk:** F-CRD-001 had a compound chain exposure: unredacted credential evidence → enrichment context → LLM prompt → GitHub comment. The fix broke the chain at the source (redaction).

**Systemic vs isolated:** Isolated. Two defects in 30 units, each in distinct code paths with no shared root cause.

### Cluster D: Resolved Documentation / Artifact Corrections

**Description:** Findings where the gap was in documentation, metadata, or test coverage rather than runtime behavior. Resolved during the audit.

**Representative findings:**

| Finding ID | Unit | Summary |
|---|---|---|
| F-IGN-001 | ignore | Documentation/behavior alignment correction |
| F-IGN-002 | ignore | Documentation/behavior alignment correction |
| F-GC-001 | graph-context | Resolved during audit |
| F-IMP-002 | imports | Design observation, accepted |

**Systemic vs isolated:** Isolated. Minor documentation and alignment issues resolved opportunistically.

### Cluster E: Design Observations Accepted

**Description:** Findings where current behavior is intentional and documented. No code change planned. Recorded for audit completeness.

**Representative findings:**

| Finding ID | Unit | Summary |
|---|---|---|
| F-SCH-001 | schema | Only Finding model is frozen; other 10 models mutable. Intentional for incremental construction. |
| F-SCH-003 | schema | Finding.id and Escalation.id use bare `str`. Intentional for LLM output tolerance. |
| F-EMB-001 | embedder | Passthrough params consumed by OpenAI SDK, not user-facing. |
| F-RS-003 | rule-secrets | `_is_comment_line` misses HTML/CSS/Lua comments. Acceptable — comment-line secrets still worth flagging. |
| F-RY-002 | retry | `import warnings` lazy inside function body. Style choice, not defect. |

**Systemic vs isolated:** Isolated. Each is a specific design decision with clear rationale. No pattern of avoidance.

---

## 4. Trust Boundary Impact

| ID | Boundary | Anchor Units | Delegating Units | Open Findings | Highest Severity | Coverage Status |
|---|---|---|---|---|---|---|
| TB-1 | PR metadata ingress | agent, review | mcp-server | 0 | — | Directly verified |
| TB-2 | Diff/content ingestion | local-diff, rule-engine, review | 10 rule-\* units, ignore | 0 | — | Directly verified |
| TB-3 | Prompt composition | prompts, agent | mcp-server | 1 (F-PR-002) | LOW | Directly verified |
| TB-4 | Tool-call boundary | codebase | — | 2 (F-CB-001, F-CB-002) | LOW | Directly verified |
| TB-5 | Model output boundary | retry | — | 0 | — | Directly verified |
| TB-6 | GitHub posting boundary | github-review | review | 0 | — | Directly verified |
| TB-7 | Config/credentials boundary | agent | mcp-server, cli | 0 | — | Directly verified |
| TB-8 | Rule coverage validation | retry | — | 1 (F-RY-001) | HIGH | Partially verified |
| TB-9 | Session history boundary | agent | — | 0 | — | Directly verified |

**Coverage status definitions:**

- **Directly verified** — anchor functions tested with adversarial fixtures in `test_hostile_environment.py` or unit-specific adversarial test classes
- **Verified by delegation** — unit delegates to a directly-verified anchor and performs no independent boundary logic
- **Partially verified** — some anchor code paths tested, others lack test coverage (F-RY-001: count validation tested, file-set validation untested)

**Key insight:** 8 of 9 trust boundaries are directly verified with adversarial fixtures. The sole partial verification (TB-8) is an assurance gap — the code exists and runs in production, but the file-set validation branch has zero test coverage. The delegation pattern (23 units delegating to 7 anchor units) means that verifying the 7 anchor units provides coverage for the entire fleet.

---

## 5. Dead Code Triage

No dead code findings. Dim 10 (Dead Code / Debt) scores range 8–10 across all 30 units, with a mean of 9.0. Zero TODO/FIXME items in the source. The codebase is clean of dead code.

| finding_id | unit | classification | rationale | action |
|---|---|---|---|---|
| *(empty)* | — | — | — | — |

---

## 6. Batch PR Plan

### Lane 1: Hygiene

Constants, typing nits, style, dead code removal.

**Candidate findings:** F-RY-002, F-RS-003
**Estimated scope:** 2 files, ~10 LOC delta
**Dependencies:** None

### Lane 2: Security Hardening

Adversarial test gaps on trust-boundary-adjacent code.

**Candidate findings:** F-RS-001, F-ENR-001
**Estimated scope:** 2 test files, ~30 LOC added (adversarial fixtures)
**Dependencies:** None

### Lane 3: Prompt & LLM Safety

Data fencing and trust marking in prompt composition.

**Candidate findings:** F-PR-002
**Estimated scope:** 1 prompt file, ~5 LOC annotation
**Dependencies:** None

### Lane 4: Test Gaps

Missing coverage, adversarial scenarios, fixture matrices.

**Candidate findings:** F-RY-001, KRC-01 batch (13 instances), F-CB-002
**Estimated scope:** ~15 test files, ~200 LOC added (1-2 tests per KRC-01 instance + ~10 LOC for F-RY-001 + ~20 LOC for F-CB-002)
**Dependencies:** Lane 2 should land first (adversarial fixtures for rule-secrets and rule-enrichment overlap with KRC-01 batch)

### Lane 5: Correctness & Invariants

Logic bugs, behavioral correctness, error handling.

**Candidate findings:** F-CLI-01, F-CB-001, F-GS-001
**Estimated scope:** 3 source files, ~20 LOC delta
**Dependencies:** None

### Lane 6: CI & Release

Workflow hardening, quality gate, dependency freshness, SHA pinning.

**Candidate findings:** None
**Estimated scope:** 0 files
**Dependencies:** N/A

---

## 7. Dimension Heatmap

Scores extracted from each unit's SCORECARD.md Summary table.

| Unit | CF | Rob | Sec | Adv | Aud | Tst | Con | Doc | Perf | Dead | Dep | Avg |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| schema | 8 | 7 | 7 | 6 | 6 | 8 | 9 | 7 | 8 | 9 | 10 | 7.7 |
| ignore | 8 | 7 | 7 | 6 | 6 | 8 | 9 | 7 | 8 | 9 | 9 | 7.6 |
| imports | 7 | 8 | 6 | 6 | 5 | 7 | 9 | 7 | 8 | 8 | 10 | 7.4 |
| embedder | 7 | 7 | 6 | 7 | 5 | 8 | 9 | 8 | 9 | 10 | 8 | 7.6 |
| rule-engine | 8 | 7 | 7 | 7 | 7 | 7 | 9 | 7 | 8 | 9 | 8 | 7.6 |
| rule-enrichment | 8 | 8 | 7 | 5 | 7 | 8 | 8 | 7 | 7 | 9 | 7 | 7.4 |
| rule-secrets | 7 | 6 | 7 | 5 | 6 | 6 | 9 | 7 | 8 | 9 | 9 | 7.2 |
| rule-workflows | 7 | 6 | 7 | 6 | 6 | 7 | 9 | 7 | 8 | 9 | 9 | 7.4 |
| rule-sinks | 7 | 6 | 7 | 6 | 6 | 7 | 9 | 7 | 8 | 9 | 9 | 7.4 |
| rule-traversal | 7 | 6 | 7 | 6 | 6 | 7 | 9 | 7 | 8 | 9 | 9 | 7.4 |
| rule-llm-sinks | 7 | 6 | 7 | 6 | 6 | 7 | 8 | 7 | 7 | 9 | 8 | 7.1 |
| rule-ci-risk | 7 | 6 | 7 | 6 | 7 | 7 | 9 | 7 | 8 | 9 | 9 | 7.5 |
| rule-sql | 7 | 6 | 7 | 6 | 6 | 7 | 9 | 7 | 8 | 9 | 9 | 7.4 |
| rule-crypto | 7 | 6 | 7 | 6 | 7 | 8 | 9 | 7 | 8 | 9 | 9 | 7.5 |
| rule-creds | 7 | 7 | 8 | 6 | 6 | 8 | 9 | 7 | 8 | 9 | 9 | 7.6 |
| rule-deser | 7 | 7 | 7 | 6 | 8 | 7 | 9 | 8 | 8 | 9 | 9 | 7.5 |
| local-diff | 8 | 8 | 9 | 8 | 7 | 8 | 9 | 8 | 8 | 9 | 10 | 8.4 |
| graph-types | 7 | 7 | 7 | 6 | 6 | 8 | 9 | 7 | 8 | 9 | 10 | 7.6 |
| graph-store | 8 | 8 | 8 | 7 | 7 | 9 | 9 | 7 | 8 | 9 | 8 | 8.0 |
| graph-context | 7 | 6 | 7 | 6 | 5 | 7 | 9 | 6 | 7 | 9 | 8 | 7.0 |
| prompts | 7 | 8 | 7 | 5 | 6 | 8 | 9 | 8 | 9 | 9 | 10 | 7.8 |
| codebase | 8 | 8 | 8 | 8 | 6 | 9 | 9 | 7 | 8 | 9 | 7 | 7.9 |
| agent | 8 | 7 | 9 | 7 | 7 | 7 | 9 | 8 | 8 | 9 | 7 | 7.8 |
| retry | 8 | 8 | 8 | 7 | 7 | 7 | 9 | 7 | 8 | 9 | 9 | 7.9 |
| mcp-response | 8 | 8 | 7 | 7 | 6 | 8 | 9 | 7 | 9 | 9 | 9 | 7.9 |
| mcp-server | 8 | 8 | 7 | 7 | 6 | 8 | 9 | 8 | 8 | 9 | 7 | 7.7 |
| mcp-config | 8 | 8 | 7 | 7 | 6 | 7 | 9 | 8 | 8 | 9 | 9 | 7.8 |
| github-review | 8 | 8 | 9 | 8 | 7 | 9 | 9 | 7 | 7 | 9 | 9 | 8.2 |
| review | 7 | 8 | 7 | 6 | 6 | 8 | 9 | 7 | 7 | 8 | 6 | 7.2 |
| cli | 7 | 7 | 7 | 7 | 6 | 8 | 9 | 8 | 8 | 9 | 8 | 7.6 |
| **Min** | **7** | **6** | **6** | **5** | **5** | **6** | **8** | **6** | **7** | **8** | **6** | **7.0** |
| **Max** | **8** | **8** | **9** | **8** | **8** | **9** | **9** | **8** | **9** | **10** | **10** | **8.4** |
| **Mean** | **7.4** | **7.1** | **7.3** | **6.4** | **6.3** | **7.6** | **8.9** | **7.2** | **7.9** | **9.0** | **8.6** | **7.6** |

**Legend:** CF=Contract Fidelity, Rob=Robustness, Sec=Security Posture, Adv=Adversarial Resilience, Aud=Auditability, Tst=Test Quality, Con=Convention Adherence, Doc=Documentation Accuracy, Perf=Performance, Dead=Dead Code/Debt, Dep=Dependency Hygiene

**Discriminative dimensions (carry real signal):**
- **Dim 4 (Adversarial Resilience):** Range 5–8, mean 6.4. The only dimension that materially affected health status. Soft floor gate fired on 3 units (rule-secrets=5, rule-enrichment=5, prompts=5).
- **Dim 5 (Auditability):** Range 5–8, mean 6.3. Separates units with dedicated audit trail metadata from those with generic messages.
- **Dim 2 (Robustness):** Range 6–8, mean 7.1. Splits simple detectors (6) from infrastructure with error handling (8).

**Non-discriminative dimensions (anchor the rubric, do not differentiate):**
- **Dim 7 (Convention):** 28/30 score 9, 2 score 8. Mean 8.9. ruff + mypy strict + SPDX header = 9.
- **Dim 10 (Dead Code):** 27/30 score 9, 2 score 8, 1 scores 10. Mean 9.0. Zero TODOs across the codebase.
- **Dim 11 (Dependency Hygiene):** Mean 8.6. Leaf nodes trivially score high. Only review (6) breaks the pattern due to its large import surface.

---

## 8. Phase-Level Health

| Phase | Units | Mean Score | Healthy | Adequate | Needs Attention | Critical |
|---|---|---|---|---|---|---|
| 0 (Leaf) | 4 | 7.6 | 0 | 4 | 0 | 0 |
| 1 (Core Infra) | 14 | 7.5 | 1 | 13 | 0 | 0 |
| 2 (Mid-Tier) | 4 | 7.7 | 1 | 3 | 0 | 0 |
| 3 (Orchestration) | 3 | 7.9 | 0 | 2 | 1 | 0 |
| 4 (Integration) | 5 | 7.7 | 1 | 4 | 0 | 0 |
| **Total** | **30** | **7.6** | **3** | **26** | **1** | **0** |

**Phase 3 has the highest mean (7.9) but the only Needs Attention unit (retry).** This is the gate model working as designed: retry's HIGH finding (F-RY-001) fires the ceiling gate, capping its status at Needs Attention despite an overall score of 7.9 that would otherwise qualify as Healthy. The gate prevents score-washing — a unit with a HIGH assurance gap cannot be called Healthy regardless of its aggregate score.

**Phase 1 has the lowest mean (7.5) due to 10 detector rules clustering at 7.1–7.5.** These rules share architectural patterns (compiled regexes, `ctx.added_lines_for()`, `RuleResult` output) and the same fixture gap pattern (KRC-01). The tight band reflects genuine uniformity, not rubric compression.

---

## 9. Compound Chain Status

| Chain ID | Chain Name | Verification Level | Notes |
|---|---|---|---|
| CH-1 | Prompt Injection → Merge Block | Supported by unit evidence | agent (origin, TB-1/3), retry (relay, TB-5/8), review (relay), github-review (terminus, TB-6) — each unit's scorecard documents its chain role and controls |
| CH-2 | Path Traversal → Prompt Leakage | Supported by unit evidence | codebase (origin, TB-4), graph-context (relay), agent (consumer) — individual unit scorecards verify segment controls |
| CH-3 | Output Injection → XSS/Phishing | **Directly traced end-to-end** | Phase 3B paired audit traced: `run_review()` [retry, TB-5] → `post_review()` [review, relay] → `_sanitize_comment_text()` [github-review, TB-6, 5-stage pipeline]. Documented in FRESHNESS.md § Compound Chain Traces |
| CH-4 | Rule Bypass → Silent Pass | Supported by unit evidence | local-diff/rule-engine (origin, TB-2), review (relay), mcp-server (consumer) — each scorecard documents participation |
| CH-5 | History Poisoning → Override | Supported by unit evidence | agent (circuit breaker via AF-07, `add_history_to_context=False`), retry (non-participant, confirmed) — circuit breaker verified in agent scorecard |

**Verification level definitions:**

- **Directly traced end-to-end** — paired audit traced the full chain across unit boundaries, citing both scorecards with specific code paths and controls at each hop
- **Supported by unit evidence but not end-to-end traced** — individual unit scorecards verify their chain segment, but no paired cross-unit trace exists in the audit record
- **Not yet directly demonstrated** — chain identified in methodology but not independently verified by any unit audit

**Key observation:** CH-3 is the strongest proof in the audit because the Phase 3B paired audit (review + github-review) explicitly traced the full data flow from LLM output through the 5-stage sanitization pipeline to the GitHub API. The other chains are supported by individual unit evidence documenting their roles and controls, but lack the paired cross-boundary trace that CH-3 received. This is an honest asymmetry — CH-3 was specifically prioritized because the critical data flow (PR content → prompt → LLM → GitHub) makes it the highest-risk chain.
