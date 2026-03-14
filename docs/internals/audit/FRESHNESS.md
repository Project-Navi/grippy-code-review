# Audit Unit Freshness Tracker — Grippy

**Last updated:** 2026-03-14 (Phase 2 Batch 2 complete — 22/30 CURRENT)

## Status Legend

| Status | Meaning |
|--------|---------|
| CURRENT | Audited, no boundary anchor changes, <50 commits touching mapped files since audit |
| STALE | >50 commits touching mapped files since audit |
| BOUNDARY_CHANGED | Named anchor function modified since last audit -- re-audit required |
| NEVER | No audit performed |
| IN_PROGRESS | Audit currently underway |

## Trust Boundary Register

Changes to these anchor functions trigger BOUNDARY_CHANGED status for affected units.

| ID | Boundary | Anchor Functions | Units |
|---|---|---|---|
| TB-1 | PR metadata ingress | `format_pr_context()`, `_escape_xml()`, `_escape_rule_field()` | agent, review |
| TB-2 | Diff/content ingestion | `fetch_pr_diff()`, `filter_diff()`, `get_local_diff()`, `RuleEngine.run()` | local-diff, review, rule-engine |
| TB-3 | Prompt composition | `load_identity()`, `load_instructions()`, `create_reviewer()` chain, `format_pr_context()` | agent, prompts |
| TB-4 | Tool-call boundary | `CodebaseToolkit.read_file/grep_code/list_files/search_code`, `sanitize_tool_hook()` | codebase |
| TB-5 | Model output boundary | `run_review()`, `_parse_response()`, `_strip_markdown_fences()` | retry |
| TB-6 | GitHub posting boundary | `_sanitize_comment_text()`, `post_review()`, `build_review_comment()`, `resolve_threads()` | github-review |
| TB-7 | Config/credentials boundary | `_resolve_transport()`, `_PROVIDERS` dict (module paths + class names) | agent |
| TB-8 | Rule coverage validation | `_validate_rule_coverage()`, `_safe_error_summary()` | retry |
| TB-9 | Session history boundary | `add_history_to_context` setting | agent |

## Unit Status

### Phase 0 -- Leaf (4 units)

| Unit ID | Last Audit | Commit | Score | Commits Since | Status |
|---|---|---|---|---|---|
| schema | 2026-03-13 | cebbcab | 7.7/10 | 0 | CURRENT |
| ignore | 2026-03-13 | 6a85523 | 7.6/10 | 0 | CURRENT |
| imports | 2026-03-13 | c606d0a | 7.4/10 | 0 | CURRENT |
| embedder | 2026-03-13 | 44a6621 | 7.6/10 | 0 | CURRENT |

### Phase 1 -- Core Infra (14 units)

| Unit ID | Last Audit | Commit | Score | Commits Since | Status |
|---|---|---|---|---|---|
| rule-engine | 2026-03-13 | aa19594 | 7.6/10 | 0 | CURRENT |
| rule-enrichment | — | — | — | — | NEVER |
| rule-secrets | 2026-03-13 | 259d0b8 | 7.2/10 | 0 | CURRENT |
| rule-workflows | 2026-03-13 | b40d4ec | 7.4/10 | 0 | CURRENT |
| rule-sinks | 2026-03-13 | b40d4ec | 7.4/10 | 0 | CURRENT |
| rule-traversal | 2026-03-13 | ab7cc93 | 7.4/10 | 0 | CURRENT |
| rule-llm-sinks | 2026-03-14 | 8957771 | 7.1/10 | 0 | CURRENT |
| rule-ci-risk | 2026-03-14 | 8957771 | 7.5/10 | 0 | CURRENT |
| rule-sql | 2026-03-13 | ab7cc93 | 7.4/10 | 0 | CURRENT |
| rule-crypto | 2026-03-13 | ab7cc93 | 7.5/10 | 0 | CURRENT |
| rule-creds | 2026-03-14 | 8957771 | 7.6/10 | 0 | CURRENT |
| rule-deser | 2026-03-14 | 8957771 | 7.5/10 | 0 | CURRENT |
| local-diff | 2026-03-13 | b3732e4 | 8.4/10 | 0 | CURRENT |
| graph-types | 2026-03-13 | b40d4ec | 7.6/10 | 0 | CURRENT |

### Phase 2 -- Mid-Tier (4 units)

| Unit ID | Last Audit | Commit | Score | Commits Since | Status |
|---|---|---|---|---|---|
| graph-store | 2026-03-14 | 617a0f9 | 8.0/10 | 0 | CURRENT |
| graph-context | 2026-03-14 | 617a0f9 | 7.0/10 | 0 | CURRENT |
| prompts | 2026-03-14 | aba44c3 | 7.8/10 | 0 | CURRENT |
| codebase | 2026-03-14 | aba44c3 | 7.9/10 | 0 | CURRENT |

### Phase 3 -- Orchestration (3 units)

| Unit ID | Last Audit | Commit | Score | Commits Since | Status |
|---|---|---|---|---|---|
| agent | — | — | — | — | NEVER |
| retry | 2026-03-13 | 259d0b8 | 7.9/10 | 0 | CURRENT |
| mcp-response | — | — | — | — | NEVER |

### Phase 4 -- Integration (5 units)

| Unit ID | Last Audit | Commit | Score | Commits Since | Status |
|---|---|---|---|---|---|
| mcp-server | — | — | — | — | NEVER |
| mcp-config | — | — | — | — | NEVER |
| github-review | — | — | — | — | NEVER |
| review | — | — | — | — | NEVER |
| cli | — | — | — | — | NEVER |

## Methodology Version

| Version | Date | Key Changes |
|---|---|---|
| 1.0 | 2026-03-13 | Initial Grippy adaptation. 30 units, 11 dimensions, v4.1 gate model. |
| 1.2 | 2026-03-14 | Provisional suffix scoped to Dim 3/4 only. KRC-01 known pattern class. graph-context reclassified to config. |
| 1.3 | 2026-03-14 | prompts reclassified from llm-agent to infrastructure/config (5/8 LA items N/A). Prospective only. |

## Cross-Unit Audits

| Date | Units | Auditor | Reference |
|---|---|---|---|
| 2026-03-13 | schema, rule-secrets, retry | Claude Opus 4.6 / Nelson Spence | `pilot/PHASE-2-ADJUDICATION.md` |
| 2026-03-13 | ignore, imports, embedder | Claude Opus 4.6 / Nelson Spence | `ignore/SCORECARD.md`, `imports/SCORECARD.md`, `embedder/SCORECARD.md` |
| 2026-03-13 | rule-engine, local-diff | Claude Opus 4.6 / Nelson Spence | `rule-engine/SCORECARD.md`, `local-diff/SCORECARD.md` |
| 2026-03-13 | graph-types, rule-workflows, rule-sinks | Claude Opus 4.6 / Nelson Spence | `graph-types/SCORECARD.md`, `rule-workflows/SCORECARD.md`, `rule-sinks/SCORECARD.md` |
| 2026-03-13 | rule-traversal, rule-sql, rule-crypto | Claude Opus 4.6 / Nelson Spence | `rule-traversal/SCORECARD.md`, `rule-sql/SCORECARD.md`, `rule-crypto/SCORECARD.md` |
| 2026-03-14 | rule-llm-sinks, rule-ci-risk, rule-creds, rule-deser | Claude Opus 4.6 / Nelson Spence | `rule-llm-sinks/SCORECARD.md`, `rule-ci-risk/SCORECARD.md`, `rule-creds/SCORECARD.md`, `rule-deser/SCORECARD.md` |
| 2026-03-14 | graph-store, graph-context | Claude Opus 4.6 / Nelson Spence | `graph-store/SCORECARD.md`, `graph-context/SCORECARD.md` |
| 2026-03-14 | prompts, codebase | Claude Opus 4.6 / Nelson Spence | `prompts/SCORECARD.md`, `codebase/SCORECARD.md` |

## Superset Analysis

| Date | Commit Range | Finding Count | Reference |
|---|---|---|---|
| — | — | — | — |
