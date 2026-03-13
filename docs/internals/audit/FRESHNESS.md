# Audit Unit Freshness Tracker — Grippy

**Last updated:** 2026-03-13

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
| TB-7 | Config/credentials boundary | `_resolve_transport()`, `_PROVIDERS`, `importlib.import_module()` | agent, cli, mcp-server |
| TB-8 | Rule coverage validation | `_validate_rule_coverage()`, `_safe_error_summary()` | retry |
| TB-9 | Session history boundary | `add_history_to_context` setting | agent |

## Unit Status

### Phase 0 -- Leaf (4 units)

| Unit ID | Last Audit | Commit | Score | Commits Since | Status |
|---|---|---|---|---|---|
| schema | — | — | — | — | NEVER |
| ignore | — | — | — | — | NEVER |
| imports | — | — | — | — | NEVER |
| embedder | — | — | — | — | NEVER |

### Phase 1 -- Core Infra (14 units)

| Unit ID | Last Audit | Commit | Score | Commits Since | Status |
|---|---|---|---|---|---|
| rule-engine | — | — | — | — | NEVER |
| rule-enrichment | — | — | — | — | NEVER |
| rule-secrets | — | — | — | — | NEVER |
| rule-workflows | — | — | — | — | NEVER |
| rule-sinks | — | — | — | — | NEVER |
| rule-traversal | — | — | — | — | NEVER |
| rule-llm-sinks | — | — | — | — | NEVER |
| rule-ci-risk | — | — | — | — | NEVER |
| rule-sql | — | — | — | — | NEVER |
| rule-crypto | — | — | — | — | NEVER |
| rule-creds | — | — | — | — | NEVER |
| rule-deser | — | — | — | — | NEVER |
| local-diff | — | — | — | — | NEVER |
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
| retry | — | — | — | — | NEVER |
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
| — | — | — | — |

## Superset Analysis

| Date | Commit Range | Finding Count | Reference |
|---|---|---|---|
| — | — | — | — |
