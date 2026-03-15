# Final Audit Retrospective — Grippy

**Date:** 2026-03-15
**Scope:** 30/30 units audited across 5 phases
**Auditor:** Claude Opus 4.6 / Nelson Spence
**Methodology:** v1.0 → v1.2 → v1.3 (progressive refinement during sweep)

This retrospective builds on `PHASE-1-RETROSPECTIVE.md` (which covered the first 20 units) and covers the complete 30/30 picture.

---

## 1. Score Distribution

### Overall Scores (30 units)

| Score | Units | Count |
|-------|-------|------:|
| 8.4 | local-diff | 1 |
| 8.2 | github-review | 1 |
| 8.0 | graph-store | 1 |
| 7.9 | codebase, retry, mcp-response | 3 |
| 7.8 | prompts, agent, mcp-config | 3 |
| 7.7 | schema, mcp-server | 2 |
| 7.6 | ignore, embedder, rule-engine, rule-creds, graph-types, cli | 6 |
| 7.5 | rule-ci-risk, rule-crypto, rule-deser | 3 |
| 7.4 | imports, rule-enrichment, rule-workflows, rule-sinks, rule-traversal, rule-sql | 6 |
| 7.2 | rule-secrets, review | 2 |
| 7.1 | rule-llm-sinks | 1 |
| 7.0 | graph-context | 1 |

**Mean:** 7.6 | **Median:** 7.6 | **Range:** 7.0–8.4 | **Std dev:** 0.31

### Comparison with Phase 1 (20 units)

| Metric | Phase 1 (20 units) | Full sweep (30 units) |
|--------|-------------------:|----------------------:|
| Mean | 7.49 | 7.60 |
| Median | 7.45 | 7.60 |
| Range | 7.1–8.4 | 7.0–8.4 |
| Std dev | 0.27 | 0.31 |

The 10 Phase 2–4 units widened the distribution slightly. graph-context (7.0) extended the floor. github-review (8.2) and graph-store (8.0) joined local-diff (8.4) as Healthy-tier units. The Phase 1 prediction that "Phase 2+3 units will have more structural variation" was confirmed — the 10 new units spread from 7.0 to 8.2, compared to the 7.1–8.4 band of Phase 1.

### Health Status Distribution

| Status | Count | Units |
|--------|------:|-------|
| Healthy | 2 | graph-store, github-review |
| Healthy (provisional) | 1 | local-diff |
| Adequate | 8 | graph-context, codebase, agent, mcp-response, mcp-server, mcp-config, review, cli |
| Adequate (provisional) | 18 | schema, ignore, imports, embedder, 12 Phase 1 units, prompts |
| Needs Attention | 1 | retry |
| Critical | 0 | — |

---

## 2. Recorded State vs Normalized Interpretation

### As Recorded

19 of 30 units carry the `(provisional)` suffix in their scorecard health status. This is the recorded artifact state as of 2026-03-15.

### Under v1.2 Normalization

Methodology v1.2 (2026-03-14) scoped `(provisional)` to trigger only when Dim 3 (Security Posture) or Dim 4 (Adversarial Resilience) is supported exclusively by Tier C evidence. This was applied prospectively — units audited before v1.2 were not recomputed.

The 18 pre-v1.2 units (Phase 0 + Phase 1) carry `(provisional)` from the original v1.0 assessment, where the suffix triggered on any dimension with Tier C evidence. Under v1.2 normalization:

- **Units that would lose the suffix:** Most Phase 1 rules had Batch 2 adversarial tests (ReDoS + long-line) added before scoring, providing Tier A evidence for Dim 4. Their Dim 3 scores are informed by code reading (Tier C) but supplemented by static analysis (Tier A). Under v1.2, units with at least some Tier A evidence in both Dim 3 and Dim 4 would lose the suffix.

- **Units that would retain the suffix:** rule-secrets (Dim 4 = 5, adversarial evidence gaps per F-RS-001), rule-enrichment (Dim 4 = 5, adversarial evidence gap per F-ENR-001), and prompts (Dim 4 = 5, no adversarial fixtures per F-PR-001). These three units have Dim 4 scores driven by the absence of Tier A adversarial evidence, which is exactly what the v1.2 scoping is designed to flag.

- **Post-v1.2 units (Phase 2 partial, Phase 3, Phase 4):** 8 units were scored without the provisional suffix because they met v1.2 criteria. 1 unit (prompts) retains it because Dim 4 = 5 with only Tier C evidence.

**Important:** This analysis does not retroactively change any scorecard. The recorded state in each SCORECARD.md file is the artifact of record. The normalization shows what would change if v1.2 were applied uniformly, which is useful for comparing units across phases but does not invalidate the recorded assessments.

---

## 3. Dimension Discrimination Analysis

### Per-Dimension Statistics (30 units)

| Dim | Name | Min | Max | Range | Mean | Signal |
|-----|------|-----|-----|-------|------|--------|
| 1 | Contract Fidelity | 7 | 8 | 1 | 7.4 | Low |
| 2 | Robustness | 6 | 8 | 2 | 7.1 | Moderate |
| 3 | Security Posture | 6 | 9 | 3 | 7.3 | Moderate |
| 4 | **Adversarial Resilience** | **5** | **8** | **3** | **6.4** | **High** |
| 5 | Auditability | 5 | 8 | 3 | 6.3 | Moderate |
| 6 | Test Quality | 6 | 9 | 3 | 7.6 | Moderate |
| 7 | Convention Adherence | 8 | 9 | 1 | 8.9 | None |
| 8 | Documentation Accuracy | 6 | 8 | 2 | 7.2 | Low |
| 9 | Performance | 7 | 9 | 2 | 7.9 | Low |
| 10 | Dead Code / Debt | 8 | 10 | 2 | 9.0 | None |
| 11 | Dependency Hygiene | 6 | 10 | 4 | 8.6 | Low |

### Analysis

**Dim 4 (Adversarial Resilience) is the only dimension that materially affected health status.** Three units scored 5 on this dimension (rule-secrets, rule-enrichment, prompts), triggering the adversarial resilience soft floor gate. This gate is the rubric's primary mechanism for separating units with proven security properties from those without. The mean of 6.4 is the lowest of all 11 dimensions, confirming that adversarial testing is the codebase's most variable quality axis.

**Dims 7, 10, and 11 are non-discriminative.** Convention Adherence (8.9 mean, range 8–9), Dead Code (9.0 mean, range 8–10), and Dependency Hygiene (8.6 mean, range 6–10) anchor the rubric but do not differentiate units. Dim 11 has the widest range (4 points) but this is driven by a single outlier — review (6) has the largest import surface and most external dependencies.

**Phase 1 prediction confirmed:** The retrospective predicted that non-discriminative dimensions would "vary more when auditing orchestration units with real dependency graphs." This was partially confirmed: Dim 2 (Robustness) gained more variation in Phase 2–4 (graph-store=8, review=8 vs. graph-context=6), and Dim 3 (Security Posture) showed its full range (6–9) only when Phase 3–4 units (agent=9, github-review=9) were scored.

---

## 4. Delegation vs Local Control

The strongest architectural insight from the audit: trust boundary defense is concentrated in anchor-owning units, and the remaining units delegate correctly. This is a strength.

### Anchor-Owning Units

| Unit | Trust Boundaries | Role |
|------|------------------|------|
| agent | TB-1, TB-3, TB-7, TB-9 | PR metadata ingress, prompt composition, config/credentials, session history. 4 boundaries — most of any unit. |
| retry | TB-5, TB-8 | Model output parsing, rule coverage validation. Defense-in-depth against LLM fabrication. |
| github-review | TB-6 | GitHub posting. 5-stage sanitization pipeline — sole terminus for CH-3. |
| codebase | TB-4 | Tool-call boundary. Path traversal, symlink, glob timeout, tool_hooks sanitization. |
| local-diff | TB-2 | Diff acquisition. Ref validation, subprocess timeout, scope parsing. |
| rule-engine | TB-2 | Diff processing. Rule dispatch, profile gating. |
| prompts | TB-3 | Prompt file loading. Structural integrity of prompt chain composition. |
| review | TB-1, TB-2 | PR event loading, diff fetching. Delegates sanitization to agent (TB-1) and github-review (TB-6). |

### Delegating Units (23 units)

All 10 individual rule units delegate diff ingestion to rule-engine (TB-2). schema, imports, ignore, embedder, graph-types, graph-store, graph-context, mcp-response are leaf/infrastructure units with no boundary ownership. mcp-server and mcp-config delegate to agent (TB-1/3/7) and retry (TB-5/8). cli delegates transport resolution to agent (TB-7).

### What This Means

The security posture of the entire fleet is determined by 8 anchor-owning units. If those 8 units are correct and well-tested, the 22 delegating units inherit their security properties. The audit confirmed this pattern: anchor units score higher on Dim 3 (Security) and Dim 4 (Adversarial) than delegating units.

| Group | Count | Mean Dim 3 | Mean Dim 4 |
|-------|------:|:----------:|:----------:|
| Anchor-owning | 8 | 8.0 | 6.9 |
| Delegating | 22 | 6.9 | 6.2 |

The gap is most pronounced in Dim 3 (Security Posture): anchor units average 8.0 vs. 6.9 for delegating units. This confirms that the audit correctly prioritized boundary-owning code for deeper scrutiny.

---

## 5. What the Audit Found

### Yield Summary

| Category | Count | Examples |
|----------|------:|---------|
| Confirmed code defects (fixed) | 2 | F-CRD-001 (security), F-IMP-001 (edge-case crash) |
| Assurance / test gaps | 5 | F-RY-001 (HIGH), F-RS-001, F-ENR-001, F-CB-002, F-PR-002 |
| Fixture matrix gaps (KRC-01) | 13 | Batch-addressable, ~1-2 tests each |
| Code behavior defects (unfixed) | 3 | F-CLI-01, F-CB-001, F-GS-001 — all LOW |
| Design observations (accepted) | 5 | F-SCH-001, F-SCH-003, F-EMB-001, F-RS-003, F-RY-002 |
| Documentation corrections (fixed) | 4 | F-IGN-001, F-IGN-002, F-GC-001, F-IMP-002 |

**Total:** 32 findings (6 resolved, 26 open).

### Interpretation

The audit surfaced **2 confirmed code defects** across 30 units (both resolved). F-CRD-001 was the sole security-relevant defect — unredacted auth tokens flowing through the evidence → enrichment → prompt → GitHub posting chain. This justified the audit exercise: the compound chain exposure is exactly the kind of hidden data flow that manual review and CI checks miss.

The remaining findings are predominantly assurance gaps (missing tests) and fixture matrix gaps (incomplete test categories). This yield is consistent with a security-focused codebase that already has CI enforcement (ruff, mypy strict, bandit, detect-secrets, semgrep, CodeQL), pre-commit hooks, and a 50-LOC test parity check. The audit's value was in verifying the *completeness* of the existing defenses, not in discovering fundamental design flaws.

---

## 6. Framework Assessment

### What Proved Itself

1. **Gate semantics prevented score-washing.** retry (7.9 overall) was capped at Needs Attention because F-RY-001 (HIGH) fired the ceiling gate. Without gates, the high average would have masked the assurance gap. This is the gate model's primary value: preventing a high aggregate score from hiding a load-bearing gap.

2. **Compound chain analysis found the CH-3 delegation pattern.** The Phase 3B paired audit of review + github-review revealed that review.py performs zero output sanitization — it delegates entirely to github-review's 5-stage pipeline. This is correct by design but was only confirmed through cross-unit analysis. No single-unit review would have surfaced this pattern.

3. **Trust boundary tracking correctly identified mcp-server as relay-only.** The initial registry listed mcp-server with a potential secondary llm-agent type. Trust boundary analysis showed it delegates to agent (TB-1/3) and retry (TB-5/8) rather than performing boundary logic itself. The `>50% N/A` reclassification threshold (B6.5) correctly triggered, preventing mcp-server from being audited against an inapplicable checklist.

4. **KRC-01 classification eliminated theatrical rediscovery.** After the first 3 rule audits identified the fixture matrix gap pattern, methodology v1.2 formalized it as KRC-01. This prevented the remaining 7 rule audits from treating the same pattern as a novel discovery. The audit correctly logged each instance while acknowledging the systemic nature.

5. **Dependency-ordered phases (A3) validated the delegation architecture.** By auditing leaf units first, the audit built confidence in lower-level components before examining the orchestration layer that depends on them. When the agent audit confirmed that `format_pr_context()` delegates sanitization to `_escape_xml()` (already verified in agent's TB-1 analysis), the delegation could be validated rather than re-audited.

### What Would Change

1. **Provisional suffix should use v1.2 scoping uniformly.** 18 of 19 provisional units carry the suffix from pre-v1.2 assessment. Since v1.2 was a prospective change, these were never recomputed. A future sweep should apply v1.2 scoping consistently. The current state is honest (recorded as-is) but analytically noisy.

2. **Paired cross-unit traces should cover more chains.** Only CH-3 received a full end-to-end paired trace. CH-1, CH-2, CH-4, and CH-5 are supported by individual unit evidence but lack the paired cross-boundary trace that makes CH-3's verification compelling. A targeted follow-up could pair-audit CH-1 (agent → retry → github-review) and CH-2 (codebase → agent) to bring them to the same verification level.

---

## 7. Re-Audit Triggers

The following events would justify re-auditing major surfaces:

| Trigger | Scope | Rationale |
|---------|-------|-----------|
| Trust boundary anchor modification | Affected unit(s) per FRESHNESS.md register | Boundary behavior changed; existing evidence invalidated |
| New compound chain identified | All units on the chain path | Cross-unit risk not previously assessed |
| Methodology version bump | All units (prospective) | Scoring criteria changed; prior scores may not be comparable |
| >50 commits touching mapped files | Affected unit(s) per FRESHNESS.md | Significant code evolution since last audit |
| New external dependency added | Affected unit(s) | Dependency hygiene and supply chain risk changed |
| F-RY-001 remediated | retry | Re-score Dim 4, remove ceiling gate, update health status |
