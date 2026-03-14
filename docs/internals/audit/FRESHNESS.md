# Audit Unit Freshness Tracker — Grippy

**Last updated:** 2026-03-13 (Wave 1.5 shared substrate complete)

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
| rule-workflows | — | — | — | — | NEVER |
| rule-sinks | — | — | — | — | NEVER |
| rule-traversal | — | — | — | — | NEVER |
| rule-llm-sinks | — | — | — | — | NEVER |
| rule-ci-risk | — | — | — | — | NEVER |
| rule-sql | — | — | — | — | NEVER |
| rule-crypto | — | — | — | — | NEVER |
| rule-creds | — | — | — | — | NEVER |
| rule-deser | — | — | — | — | NEVER |
| local-diff | 2026-03-13 | ea9be04 | 8.4/10 | 0 | CURRENT |
| graph-types | — | — | — | — | NEVER |

### Phase 2 -- Mid-Tier (4 units)

| Unit ID | Last Audit | Commit | Score | Commits Since | Status |
|---|---|---|---|---|---|
| graph-store | — | — | — | — | NEVER |
| graph-context | — | — | — | — | NEVER |
| prompts | — | — | — | — | NEVER |
| codebase | — | — | — | — | NEVER |

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

## Cross-Unit Audits

| Date | Units | Auditor | Reference |
|---|---|---|---|
| 2026-03-13 | schema, rule-secrets, retry | Claude Opus 4.6 / Nelson Spence | `pilot/PHASE-2-ADJUDICATION.md` |
| 2026-03-13 | ignore, imports, embedder | Claude Opus 4.6 / Nelson Spence | `ignore/SCORECARD.md`, `imports/SCORECARD.md`, `embedder/SCORECARD.md` |
| 2026-03-13 | rule-engine, local-diff | Claude Opus 4.6 / Nelson Spence | `rule-engine/SCORECARD.md`, `local-diff/SCORECARD.md` |

## Superset Analysis

| Date | Commit Range | Finding Count | Reference |
|---|---|---|---|
| — | — | — | — |
