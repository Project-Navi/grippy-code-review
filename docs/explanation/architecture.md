# Architecture

Grippy is built on the [Agno](https://github.com/agno-agi/agno) agent framework. It has two deployment modes: an MCP server (`grippy serve` / `uvx grippy-mcp serve`) for local diff auditing, and a GitHub Actions CI pipeline (`grippy` / `python -m grippy`) for PR review.

---

## CI Pipeline Flow

```
PR event (GITHUB_EVENT_PATH)
  |
  v
Load PR metadata ......................... review.py
  |
  v
Index codebase into LanceDB .............. codebase.py, embedder.py [non-fatal]
  |
  v
Build dependency graph ................... imports.py, graph_store.py [non-fatal]
  |  (walk Python files, extract imports, upsert FILE nodes + IMPORTS edges)
  v
Fetch full PR diff ....................... github_review.py
  |
  v
Run deterministic rule engine ............ rules/ [when profile != general]
  |  (10 rules, gate check, mode override to security_audit)
  v
Record review + author in graph .......... graph_store.py [non-fatal]
  |  (AUTHOR, REVIEW nodes; AUTHORED, TOUCHED edges)
  v
Query graph for pre-review context ....... graph_context.py [non-fatal]
  |  (blast radius, recurring findings, author risk summary)
  v
Truncate diff ............................ review.py (500K char cap, after rules)
  |
  v
Create agent with prompt chain + tools ... agent.py, prompts.py
  |
  v
Format PR context with rule findings ..... agent.py
  |  (includes <graph-context> from knowledge graph)
  v
Run review with structured output ........ retry.py, schema.py
  |  (up to 3 retries on validation failure + rule coverage check)
  v
Post inline findings + summary to PR ..... github_review.py
  |
  v
Resolve stale threads .................... github_review.py (GraphQL)
  |
  v
Persist findings to graph ................ graph_store.py [non-fatal]
  |  (FINDING nodes, FOUND_IN/PRODUCED/VIOLATES edges, observations)
  v
Set GitHub Actions outputs ............... review.py
  (score, verdict, findings-count, merge-blocking,
   rule-findings-count, rule-gate-failed, profile)
```

### MCP Server Flow

```
MCP client (Claude Code / Cursor / Claude Desktop)
  |
  v
scan_diff or audit_diff tool ............. mcp_server.py
  |
  v
Parse scope + get local diff ............. local_diff.py
  |  (git subprocess, ref validation, timeout)
  v
scan_diff path:                            audit_diff path:
  Run deterministic rules ............      Run rules + create agent
  Serialize scan results .............      Run review with structured output
  Return JSON ........................      Serialize audit results
                                           Return dense JSON (no personality)
```

---

## Module Map

All modules live in `src/grippy/`.

| Module | Purpose |
|---|---|
| `__main__.py` | CLI dispatch: `serve`, `install-mcp`, legacy CI. `main()` entry point for console scripts. |
| `review.py` | Orchestration entry point. Loads PR event, coordinates the full CI pipeline, handles errors and timeouts, sets Actions outputs. |
| `agent.py` | Agent factory. `_PROVIDERS` registry with deferred imports for 6 providers (openai, anthropic, google, groq, mistral, local). Composes prompt chain, attaches tools, configures structured output. |
| `codebase.py` | Codebase indexing (LanceDB hybrid search: vector + keyword + RRF reranking) and `CodebaseToolkit` providing `search_code`, `read_file`, `grep_code`, `list_files` tools for the agent. |
| `github_review.py` | GitHub API integration. Parses unified diffs to map findings to addressable lines, posts inline review comments (batched), manages thread lifecycle (new/persists/resolved), builds summary dashboard. |
| `schema.py` | Pydantic models for the complete structured output: `GrippyReview`, `Finding`, `Score`, `Verdict`, `Escalation`, `Personality`. Enums for severity, category, verdict status, tone register. |
| `prompts.py` | Prompt chain loader. Reads 20 markdown prompt files from `prompts_data/` and composes them into identity + instruction layers. |
| `mcp_server.py` | FastMCP server. `scan_diff` + `audit_diff` tools with `readOnlyHint` annotations. |
| `mcp_config.py` | MCP client detection (Claude Code/Desktop/Cursor), server entry generation (uvx or dev mode). |
| `mcp_response.py` | AI-facing serializers. Strips personality, outputs dense structured JSON for MCP tool responses. |
| `local_diff.py` | Git diff acquisition. Scope parsing (`staged`, `commit:<ref>`, `range:<base>..<head>`), ref validation, subprocess with timeout. |
| `graph_types.py` | Node/edge type enums (`NodeType`, `EdgeType`), dataclasses, deterministic ID helpers. Defines the navi-graph shape. |
| `graph_store.py` | `SQLiteGraphStore` --- schema init, node/edge writes, neighbor queries, BFS traversal, append-only observations, migrations. |
| `graph_context.py` | Pre-review context builder. Queries the graph for blast radius, recurring findings, and author risk summary. |
| `imports.py` | Python import extraction via `ast.parse`. Produces `IMPORTS` edges for the dependency graph. |
| `graph.py` | Re-exports `NodeType` and `EdgeType` for backward compatibility. |
| `retry.py` | Structured output validation with retry. Handles JSON strings, dicts, markdown-fenced JSON, and `GrippyReview` instances. Retries with validation error feedback. Post-parse rule coverage validation ensures all deterministic findings appear in LLM output. |
| `embedder.py` | Embedding model factory. Creates Agno `OpenAIEmbedder` instances configured for OpenAI or local endpoints. |
| `rules/` | Deterministic security rule engine (subpackage). See [Rule Engine](#rule-engine) below. |

---

## Prompt Composition System

Grippy's prompts are 20 markdown prompt files in `src/grippy/prompts_data/`, composed into two Agno layers by `prompts.py`.

### Layer 1: Identity (Agno `description`)

Loaded as a single concatenated string. Defines who Grippy is.

| File | Purpose |
|---|---|
| `CONSTITUTION.md` | Core rules, constraints, and behavioral boundaries |
| `PERSONA.md` | The grumpy security auditor personality |

### Layer 2: Instructions (Agno `instructions`)

Loaded as a list of strings (one per file). Tells Grippy what to do for a given review mode.

The instruction chain is composed in three parts:

**Mode prefix** --- `system-core.md` + one mode-specific file:

| Mode | Files |
|---|---|
| `pr_review` | `system-core.md`, `pr-review.md` |
| `security_audit` | `system-core.md`, `security-audit.md` |
| `governance_check` | `system-core.md`, `governance-check.md` |
| `surprise_audit` | `system-core.md`, `surprise-audit.md` |
| `cli` | `system-core.md`, `cli-mode.md` |
| `github_app` | `system-core.md`, `github-app.md` |

**Shared prompts** --- personality and quality gate prompts included in every mode:

1. `tone-calibration.md`
2. `confidence-filter.md`
3. `escalation.md`
4. `context-builder.md`
5. `catchphrases.md`
6. `disguises.md`
7. `ascii-art.md`
8. `all-clear.md`

**Conditional:** When rule engine findings exist, `rule-findings-context.md` is inserted into the instruction chain before the suffix.

**Suffix** --- always anchored at the end:

1. `scoring-rubric.md` --- The scoring formula and deduction rules
2. `output-schema.md` --- The exact JSON schema the model must produce

The full instruction chain for any mode is: `MODE_PREFIX + SHARED_PROMPTS + [rule-findings-context.md if rules fired] + SUFFIX`.

---

## Codebase Indexing Pipeline

When `GITHUB_WORKSPACE` is set (i.e., running in CI), Grippy indexes the checked-out repository before running the review. This lets the agent search and read the full codebase, not just the diff.

### 1. Walk source files

`walk_source_files()` uses `git ls-files` to enumerate tracked files, respecting `.gitignore`. Falls back to manual directory walk if git is unavailable. Only files with indexable extensions are included (`.py`, `.md`, `.yaml`, `.yml`, `.toml` by default). Capped at 5,000 files.

### 2. Chunk files

`chunk_file()` splits each file into 4KB character windows with 200-character overlap. Small files become a single chunk. Each chunk records its file path, chunk index, and line range for attribution.

### 3. Embed and store

`CodebaseIndex.build()` computes embeddings for all chunks (batch when supported, sequential otherwise) and stores them in a LanceDB table (`codebase_chunks`). The table is overwritten on each build.

### 4. Agent tools

During review, the agent has access to four codebase tools via `CodebaseToolkit`:

| Tool | Purpose |
|---|---|
| `search_code` | Hybrid search (vector + keyword + RRF reranking) over indexed chunks. "Find code that handles authentication." |
| `grep_code` | Regex search across the codebase with context lines. Exact pattern matching. |
| `read_file` | Read a file or line range with line numbers. Path traversal protection via `is_relative_to()`. |
| `list_files` | List directory contents with glob filtering. Capped at 500 results. |

Tool output is capped at 12,000 characters per response. All tool responses pass through `sanitize_tool_hook` middleware (`navi_sanitize.clean()` + XML-escape + 12K truncation) before reaching the LLM, preventing indirect prompt injection through crafted file contents.

---

## Knowledge Graph

Grippy maintains a SQLite-backed knowledge graph that tracks relationships between files, reviews, findings, rules, and authors across PRs. The graph is structural only --- vectors stay in the LanceDB codebase index.

**What it tracks:**

| Node Type | Represents |
|---|---|
| `FILE` | Source code file |
| `REVIEW` | A single PR review run |
| `FINDING` | A code issue or recommendation |
| `RULE` | A deterministic security rule |
| `AUTHOR` | A PR submitter |

These are connected by 6 edge types: `IMPORTS` (file dependencies), `FOUND_IN` (finding location), `VIOLATES` (rule match), `PRODUCED` (review → finding), `TOUCHED` (review → file), and `AUTHORED` (author → review).

Before each review, the context builder queries the graph for blast radius (which modules depend on changed files), recurring findings (prior issues in the same files), and author risk (historical finding patterns). This context is injected into the LLM prompt as `<graph-context>`.

All graph operations are non-fatal --- if the graph store is unavailable, the review proceeds without it.

See the [Knowledge Graph](knowledge-graph.md) page for the full data model and technical details.

---

## Rule Engine

The `src/grippy/rules/` subpackage implements a deterministic security rule engine that runs before the LLM. Core contract: **rules detect, LLM explains.**

### Submodule Map

| Module | Purpose |
|---|---|
| `__init__.py` | Public API: `run_rules()`, `check_gate()` convenience functions |
| `base.py` | `Rule` protocol, `RuleResult` dataclass, `RuleSeverity` enum (`CRITICAL`, `ERROR`, `WARN`, `INFO`) |
| `context.py` | Diff parser: `parse_diff()` produces `ChangedFile` / `DiffHunk` / `DiffLine`. `RuleContext` holds parsed diff + profile config |
| `config.py` | `ProfileConfig`, `load_profile()` (CLI > `GRIPPY_PROFILE` env > default), `PROFILES` dict |
| `engine.py` | `RuleEngine`: instantiates rules from registry, runs all, aggregates results. `check_gate()` compares max severity against profile threshold |
| `registry.py` | `RULE_REGISTRY`: explicit list of all `Rule` classes |

### Rules (v1)

| Rule ID | Module | Default Severity | Detects |
|---|---|---|---|
| `workflow-permissions-expanded` | `workflow_permissions.py` | ERROR | write/admin permissions, `pull_request_target`, unpinned actions in GitHub workflows |
| `secrets-in-diff` | `secrets_in_diff.py` | CRITICAL | API keys (AWS, GitHub, OpenAI), private key headers, `.env` additions |
| `dangerous-execution-sinks` | `dangerous_sinks.py` | ERROR | Unsafe code execution patterns in Python and JS/TS |
| `path-traversal-risk` | `path_traversal.py` | WARN | Tainted path variables, `../` traversal patterns |
| `llm-output-unsanitized` | `llm_output_sinks.py` | ERROR | Model output piped to output sinks without sanitizer |
| `ci-script-execution-risk` | `ci_script_risk.py` | WARN | Risky CI script patterns, `sudo` in CI, `chmod +x` (individual patterns like `curl\|bash` are elevated to CRITICAL dynamically) |
| `sql-injection-risk` | `sql_injection.py` | ERROR | SQL queries built with f-strings, %-formatting, or concatenation |
| `weak-crypto` | `weak_crypto.py` | WARN | MD5, SHA1, DES, ECB mode, and `random` module for security contexts |
| `hardcoded-credentials` | `hardcoded_credentials.py` | ERROR | Hardcoded passwords, DB connection strings, and auth headers |
| `insecure-deserialization` | `insecure_deserialization.py` | ERROR | Unsafe deserialization via shelve, jsonpickle, dill, cloudpickle, and torch.load |

### Pipeline Integration

1. Rule engine runs on the **full, un-truncated diff** (before `truncate_diff()`)
2. Rules only run when `profile != general`
3. If any rule finding has severity >= profile's `fail_on` threshold, the gate fails (CI exits non-zero after posting)
4. When rules fire, the review mode is automatically overridden to `security_audit`
5. Rule findings are XML-escaped and injected into the LLM user message as `<rule_findings>` context
6. After the LLM produces output, `_validate_rule_coverage()` in `retry.py` checks that every rule finding appears in the structured output with its `rule_id` set --- missing findings trigger retry
