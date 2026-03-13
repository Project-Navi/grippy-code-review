# Superset Analysis — Grippy

**Sweep date range:** {start} -- {end}
**Units audited:** {count} / 30
**Commit range:** `{first_audit_commit}`..`{last_audit_commit}`

---

## 1. Executive Summary

Top 5 systemic themes, 2-3 sentences each.

**Aggregate statistics:**

| Metric | Value |
|--------|-------|
| Total findings | {n} |
| CRITICAL | {n} |
| HIGH | {n} |
| HIGH (provisional) | {n} |
| MEDIUM | {n} |
| LOW | {n} |
| Units with HIGH+ findings | {n} / 30 |
| Mean scorecard score | {x.x} / 10 |

---

## 2. Finding Index

Flat routing table extracted from 30 x FINDINGS.md. Detail stays in source documents.

| finding_id | severity | unit | theme |
|---|---|---|---|
| `{unit_id}-{id}` | CRITICAL / HIGH / MEDIUM / LOW | `{unit_id}` | {lane name} |

---

## 3. Pattern Clusters

### Cluster: {Name}

**Description:** {What ties these findings together}

**Representative findings:**

| finding_id | unit | summary |
|---|---|---|
| | | |

**Cross-unit compound risk:** {Do these findings interact across unit boundaries? If so, reference chain ID.}

**Systemic vs isolated:** {Codebase-wide pattern or localized to a few units?}

*(Repeat for each cluster)*

---

## 4. Trust Boundary Impact

For each trust boundary (TB-1 through TB-9), summarize findings that touch its anchor functions:

| Boundary | Units | Finding Count | Highest Severity |
|---|---|---|---|
| TB-1: PR metadata ingress | | | |
| TB-2: Diff/content ingestion | | | |
| TB-3: Prompt composition | | | |
| TB-4: Tool-call boundary | | | |
| TB-5: Model output boundary | | | |
| TB-6: GitHub posting boundary | | | |
| TB-7: Config/credentials boundary | | | |
| TB-8: Rule coverage validation | | | |
| TB-9: Session history boundary | | | |

---

## 5. Dead Code Triage

| finding_id | unit | classification | rationale | action |
|---|---|---|---|---|
| | | D1 (Deprecate) / D2 (Wire or Park) | | |

---

## 6. Batch PR Plan

### Lane 1: Hygiene

Constants, typing nits, style, dead code removal.

**Candidate findings:** {finding_ids}
**Estimated scope:** {files touched, LOC delta}
**Dependencies:** {any ordering constraints}

### Lane 2: Security Hardening

Sanitization gaps, injection vectors, path traversal, tool safety.

**Candidate findings:** {finding_ids}
**Estimated scope:** {files touched, LOC delta}
**Dependencies:** {any ordering constraints}

### Lane 3: Prompt & LLM Safety

Data fencing, escape handling, history poisoning, rule coverage validation.

**Candidate findings:** {finding_ids}
**Estimated scope:** {files touched, LOC delta}
**Dependencies:** {any ordering constraints}

### Lane 4: Test Gaps

Missing coverage, adversarial scenarios, rule edge cases, fixture matrices.

**Candidate findings:** {finding_ids}
**Estimated scope:** {files touched, LOC delta}
**Dependencies:** {any ordering constraints}

### Lane 5: Correctness & Invariants

Logic bugs, schema validation, retry safety, gate semantics.

**Candidate findings:** {finding_ids}
**Estimated scope:** {files touched, LOC delta}
**Dependencies:** {any ordering constraints}

### Lane 6: CI & Release

Workflow hardening, quality gate, dependency freshness, SHA pinning.

**Candidate findings:** {finding_ids}
**Estimated scope:** {files touched, LOC delta}
**Dependencies:** {any ordering constraints}

---

## 7. Dimension Heatmap

| Unit | CF | Rob | Sec | Adv | Aud | Tst | Con | Doc | Perf | Dead | Dep | Avg | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| schema | | | | | | | | | | | | | |
| ignore | | | | | | | | | | | | | |
| ... | | | | | | | | | | | | | |

**Legend:** CF=Contract Fidelity, Rob=Robustness, Sec=Security Posture, Adv=Adversarial Resilience, Aud=Auditability, Tst=Test Quality, Con=Convention Adherence, Doc=Documentation Accuracy, Perf=Performance, Dead=Dead Code/Debt, Dep=Dependency Hygiene

---

## 8. Phase-Level Health

| Phase | Units | Mean Score | Healthy | Adequate | Needs Attention | Critical |
|---|---|---|---|---|---|---|
| 0 (Leaf) | 4 | | | | | |
| 1 (Core Infra) | 14 | | | | | |
| 2 (Mid-Tier) | 4 | | | | | |
| 3 (Orchestration) | 3 | | | | | |
| 4 (Integration) | 5 | | | | | |
| **Total** | **30** | | | | | |

---

## 9. Compound Chain Status

| Chain ID | Chain Name | Status | Notes |
|---|---|---|---|
| CH-1 | Prompt Injection -> Merge Block | | |
| CH-2 | Path Traversal -> Prompt Leakage | | |
| CH-3 | Output Injection -> XSS/Phishing | | |
| CH-4 | Rule Bypass -> Silent Pass | | |
| CH-5 | History Poisoning -> Override | | |
