# Grippy Audit Framework

Central hub for all audit documentation.

**Provenance:** Adapted from navi-os audit methodology v2.0 (20-module sweep, 178 findings, 11 remediation PRs).
**Established:** 2026-03-13

## Framework Documents

| Document | Purpose |
|----------|---------|
| [registry.yaml](registry.yaml) | Single source of truth for unit metadata (30 units, 5 phases, type mappings, boundary anchors) |
| [METHODOLOGY.md](METHODOLOGY.md) | Audit process, principles, severity taxonomy, evidence tiers, compound chain registry, CI checks |
| [SCORECARD-TEMPLATE.md](SCORECARD-TEMPLATE.md) | 11-dimension rubric with override-vs-ceiling gate semantics |
| [SUPERSET-TEMPLATE.md](SUPERSET-TEMPLATE.md) | Cross-unit synthesis: finding index, pattern clusters, trust boundary impact, 6 batch PR lanes |
| [FRESHNESS.md](FRESHNESS.md) | Audit unit freshness tracker (30 units, 5 phases, trust boundary triggers) |

## Audit Unit Type Checklists

| Checklist | Applies To |
|-----------|-----------|
| [security-rule.md](CHECKLISTS/security-rule.md) | rule-engine, rule-enrichment, 10 individual rule-* units |
| [llm-agent.md](CHECKLISTS/llm-agent.md) | agent, prompts, mcp-server (secondary) |
| [llm-facing-tool.md](CHECKLISTS/llm-facing-tool.md) | codebase |
| [review-pipeline.md](CHECKLISTS/review-pipeline.md) | retry, github-review, review |
| [data-model.md](CHECKLISTS/data-model.md) | schema, graph-types |
| [infrastructure.md](CHECKLISTS/infrastructure.md) | ignore, imports, embedder, local-diff, graph-store, graph-context, mcp-config, mcp-response, mcp-server (primary), cli |

## Audit Phases (Dependency Order)

| Phase | Units | Count |
|-------|-------|------:|
| **0** | schema, ignore, imports, embedder | 4 |
| **1** | rule-engine, rule-enrichment, 10x rule-*, local-diff, graph-types | 14 |
| **2** | graph-store, graph-context, prompts, codebase | 4 |
| **3** | agent, retry, mcp-response | 3 |
| **4** | mcp-server, mcp-config, github-review, review, cli | 5 |
| | **Total** | **30** |

## Execution Stages

| Stage | Scope | Status |
|-------|-------|--------|
| 1. Framework bootstrap | 12 framework files | In Progress |
| 2. Pilot audit | schema, rule-secrets, retry | Pending |
| 3. Framework revision | Revise based on pilot | Pending |
| 4. Full sweep | Remaining 27 units | Pending |

## Per-Unit Audit Reports

Created during audits. Each unit directory contains:
- `README.md` -- census, dependencies, test mapping, audit history
- `FINDINGS.md` -- severity-ordered findings with evidence + Compound Chain Exposure + Hypotheses
- `SCORECARD.md` -- 11-dimension scores with gate status
- `COVERAGE.md` -- test coverage assessment (gap-first)
