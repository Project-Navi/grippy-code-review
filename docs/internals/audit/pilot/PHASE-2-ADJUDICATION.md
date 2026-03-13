<!-- SPDX-License-Identifier: MIT -->

# Phase 2 Adjudication — rule-secrets + retry

**Date:** 2026-03-13
**Adjudicator:** Nelson Spence (PM/Architect)
**Executor:** Claude Opus 4.6

---

## Cross-Unit Calibration

### Calibration Anchors (from Phase 1 schema audit)

| Dimension | schema Score | rule-secrets Score | retry Score | Calibration Notes |
|-----------|:-----------:|:------------------:|:-----------:|-------------------|
| Contract Fidelity | 8 | 7 | 8 | rule-secrets lower: no Protocol class, duck-typed Rule interface. retry matches schema: typed exceptions + explicit returns. |
| Robustness | 7 | 6 | 8 | schema/rule-secrets: pure data structures, limited error paths. retry higher: typed exceptions, configurable retry, graceful degradation. |
| Security Posture | 7 | 7 | 8 | schema/rule-secrets: no trust boundaries owned. retry higher: owns TB-5 + TB-8 with proven controls. |
| Adversarial Resilience | 6 | 5 | 7 | schema: limited exposure as data model. rule-secrets: no adversarial tests (F-RS-001). retry: 3 adversarial sanitization tests. |
| Auditability | 6 | 6 | 7 | Consistent: no logging (appropriate for leaf/rule). retry higher: ReviewParseError carries context + callback mechanism. |
| Test Quality | 8 | 6 | 7 | schema: 44 tests, 1.69:1 ratio, boundary values. rule-secrets: 14 tests, thinner fixture matrix. retry: 35 tests, 2.61:1 ratio, TB-8 gap. |
| Convention Adherence | 9 | 9 | 9 | All three: ruff, mypy strict, bandit clean. SPDX headers. Consistent. |
| Documentation | 7 | 7 | 7 | All three: accurate docstrings, no usage examples. Consistent. |
| Performance | 8 | 8 | 8 | All three: efficient for workload, no profiling data. Consistent. |
| Dead Code / Debt | 9 | 9 | 9 | All three: zero TODOs, all functions called. Consistent. |
| Dependency Hygiene | 10 | 9 | 9 | schema: zero internal deps. Others: 1-2 clean internal deps. Appropriate delta. |

**Calibration verdict:** Scores are consistently calibrated across units. No adjustments needed for cross-unit consistency.

---

## Score Adjustments

### F-RS-001: Downgraded from HIGH to MEDIUM

**Original severity:** HIGH
**Adjusted severity:** MEDIUM
**Rationale:** The draft finding itself documents that all 10 regex patterns are structurally safe from catastrophic backtracking based on manual analysis. The gap is absence of adversarial Tier A proof, not a demonstrated correctness or security failure under normal operation. Under the severity taxonomy, HIGH is for code paths that produce incorrect or unsafe behavior in normal usage. This is better described as an edge-case coverage gap with insufficient proof, which fits MEDIUM.

**Impact on scoring:**
- Severity cap ceiling gate: **no longer fires** (no unresolved HIGH findings)
- Adversarial soft floor ceiling gate: **still fires** (Adversarial Resilience = 5 < 6, ceiling: Adequate)
- Final status moves from Needs Attention to **Adequate (provisional)**

### F-RY-001: Evidence tier corrected from A to B

**Original tier:** A
**Adjusted tier:** B
**Rationale:** The proof cited is "zero matches for `expected_rule_files` in test file" (grep result) plus a code-path/production trace showing the branch is live via review.py:529,628. This is deterministic repro (Tier B), not machine-verifiable proof (Tier A). Tier A would require a test that fails when the code path is broken.

**Impact on scoring:** No change to severity or scores. F-RY-001 remains HIGH. The severity cap ceiling gate still fires.

---

## Final Health Statuses

### schema

**Final status: Adequate**

No changes from Phase 1. The Phase 2 friction items (SR-06 engine scope, RP-07/08/09 N/A) do not touch the data-model checklist or schema's score logic. Schema completed cleanly with no friction and no ambiguity.

### rule-secrets

**Final status: Adequate (provisional)**

| Step | Result |
|------|--------|
| Average | 7.2/10 → Adequate |
| Override gates | None fired |
| Ceiling gates | Adversarial soft floor (dim 4 = 5 < 6) → ceiling: Adequate |
| Base vs ceiling | Adequate = Adequate → no change |
| Suffixes | `(provisional)`: Adversarial Resilience (dim 4) supported only by Tier C evidence |

**Unresolved findings:** F-RS-001 (MEDIUM), F-RS-002 (MEDIUM), F-RS-003 (LOW)

### retry

**Final status: Needs Attention**

| Step | Result |
|------|--------|
| Average | 7.9/10 → Adequate |
| Override gates | None fired |
| Ceiling gates | Severity cap (F-RY-001 HIGH) → ceiling: Needs Attention |
| Base vs ceiling | Adequate > Needs Attention → **downgrade to Needs Attention** |
| Suffixes | None (Tier C evidence is supplementary on gate dimensions) |

**Unresolved findings:** F-RY-001 (HIGH), F-RY-002 (INFO)

---

## Friction Log Summary

| # | Unit | Issue | Fix Class | Impact on Phase 2 | Framework v1.1 Action |
|---|------|-------|-----------|--------------------|-----------------------|
| 1 | rule-secrets | SR-06 profile activation is engine-level | Clarification | Marked N/A with justification. No scoring impact. | Clarify in security-rule checklist that SR-06 tests belong to rule-engine, or split. |
| 2 | retry | RP-07/08/09 N/A for retry scope (3/9 items) | Structural | Evaluated 6 applicable items. B6.5 still satisfied (67%). | Split/sub-scope review-pipeline checklist by unit responsibility. |

**Would Phase 2 friction have changed schema's Phase 1 result?** No. The friction items concern security-rule and review-pipeline checklists. Neither touches the data-model checklist or schema's scoring logic. Schema's Adequate status stands.

---

## Framework v1.1 Revision Backlog

| # | Source | Revision Item | Priority |
|---|--------|---------------|----------|
| 1 | Friction #1 | Clarify SR-06 as engine-scope or split out of individual rule audits | Medium |
| 2 | Friction #2 | Split/sub-scope review-pipeline checklist so retry doesn't carry 3 predictable N/As | Medium |

---

## Pilot Success Evaluation

### Exit Criteria

| # | Criterion | Result | Evidence |
|---|-----------|:------:|----------|
| 1 | All three units completed the full audit flow end-to-end | **PASS** | schema (Phase 1), rule-secrets + retry (Phase 2). All phases A' through D completed for each unit. |
| 2 | Every Tier A claim is backed by reproducible evidence | **PASS** | Tier A claims cite specific test names and static analysis outputs. F-RY-001 tier corrected from A to B during adjudication — evidence discipline working as intended. |
| 3 | At least one Tier C/Tier A boundary dispute resolved cleanly | **PASS** | F-RY-001 evidence tier corrected from A to B. F-RS-001 severity downgraded based on gap-vs-failure distinction. Both resolved without framework ambiguity. |
| 4 | At least one framework adjustment or code finding emerged | **PASS** | Code findings: F-RY-001 (real TB-8 test gap in production code). Framework: 2 friction log entries producing 2 v1.1 revision items. |
| 5 | Team trusts the framework more after using it than before | **PASS** | Framework survived first contact and exposed one honest structural cleanup (review-pipeline checklist scope) without collapsing comparability. No trust erosion signals. |

**Pilot outcome: SUCCESSFUL**

The 3-unit pilot validated that the audit framework produces defensible, evidence-backed, repeatable outputs. The friction log contains exactly the kind of meaningful tension the pilot was designed to surface: one clarification issue (SR-06 scope) and one structural issue (checklist granularity), both of which are clean framework revision items rather than framework failures.
