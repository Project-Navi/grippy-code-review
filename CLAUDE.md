# CLAUDE.md

## Project Overview

**Grippy** is a security-focused AI code review agent with personality, published as [`grippy-mcp`](https://pypi.org/project/grippy-mcp/) on PyPI. Built on the [Agno](https://github.com/agno-agi/agno) framework.

Two deployment modes:
- **MCP server** — `uvx grippy-mcp serve` for local git diff auditing via any MCP client
- **GitHub Actions** — CI workflow that reviews PRs, posts inline findings, and gates merges

Two MCP tools: `scan_diff` (fast deterministic security rules, no LLM) and `audit_diff` (full AI-powered review with structured findings).

## Commands

```bash
# ── Dependencies ──────────────────────────────────────────────────────
uv sync                                          # install all deps

# ── Tests ─────────────────────────────────────────────────────────────
uv run pytest tests/ -v                           # full suite
uv run pytest tests/test_grippy_codebase.py -v    # single file
uv run pytest tests/test_grippy_codebase.py::TestCodebaseToolkit::test_read_file_traversal -v
uv run pytest tests/ -v --cov=src/grippy --cov-report=term-missing  # with coverage
uv run pytest -m e2e -v                           # e2e tests (auto-skipped otherwise)

# ── Quality ───────────────────────────────────────────────────────────
uv run ruff check src/grippy/ tests/              # lint
uv run ruff format --check src/grippy/ tests/     # format check
uv run mypy src/grippy/                           # type check

# ── MCP Server ────────────────────────────────────────────────────────
uvx grippy-mcp serve                              # zero-install (PyPI)
grippy serve                                      # after pip install grippy-mcp
python -m grippy serve                            # backwards compat

# ── MCP Installer ─────────────────────────────────────────────────────
grippy install-mcp                                # registers uvx grippy-mcp in client configs
grippy install-mcp --dev                          # dev mode: uses uv run --directory

# ── CI Review (legacy) ────────────────────────────────────────────────
OPENAI_API_KEY=sk-... GITHUB_TOKEN=ghp-... GITHUB_EVENT_PATH=event.json grippy
grippy --profile security                         # with security profile
```

## Architecture

### CI Pipeline (`grippy` / `python -m grippy`)

```
PR event → load metadata → CodebaseIndex.build() [LanceDB, non-fatal]
  → fetch_pr_diff() → filter_diff() [.grippyignore]
  → run_rules() on FULL diff → truncate_diff() to 500K
  → create_reviewer() [Agno agent + prompt chain + tools]
  → format_pr_context() [rule findings + data-fence boundary]
  → run_review() [structured output validation + retry]
  → post_review() [inline comments + summary + resolve stale threads]
  → set GitHub Actions outputs
```

### MCP Server (`grippy serve`)

```
MCP client → scan_diff or audit_diff tool
  → get_local_diff() [git subprocess, scope parsing]
  → filter_diff() [.grippyignore]
  → scan_diff: run_rules() → serialize_scan() → JSON
  → audit_diff: run_rules() + create_reviewer() + run_review()
    → serialize_audit() [dense JSON, no personality] → response
```

### Module Map

| Module | Purpose |
|--------|---------|
| `__main__.py` | CLI dispatch: `serve`, `install-mcp`, legacy CI. `main()` entry point for console scripts. |
| `review.py` | CI orchestration. Loads PR event, coordinates pipeline, sets Actions outputs. |
| `agent.py` | `create_reviewer()` factory. `_PROVIDERS` registry (OpenAI, Anthropic, Google, Groq, Mistral, local). Prompt chain composition, tool hooks, structured output. |
| `codebase.py` | `CodebaseIndex` (LanceDB hybrid search), `CodebaseToolkit` (read_file, grep_code, list_files), `sanitize_tool_hook` (tool_hooks middleware). Security-critical. |
| `github_review.py` | GitHub API. Diff parsing → line mapping, inline comments, stale thread resolution, 5-stage output sanitization. |
| `schema.py` | Pydantic structured output: `GrippyReview`, `Finding`, `Score`, `Verdict`, `Escalation`, `Personality`. |
| `retry.py` | `run_review()` — JSON parsing (raw/dict/markdown-fenced) + Pydantic validation + retry with error feedback. |
| `prompts.py` | Loads 20 markdown prompt files. Chain: identity → mode-specific → shared quality gates → suffix. |
| `mcp_server.py` | FastMCP server. `scan_diff` + `audit_diff` tools with `readOnlyHint` annotations. |
| `mcp_config.py` | Client detection (Claude Code/Desktop/Cursor), server entry generation (uvx or dev mode). |
| `mcp_response.py` | AI-facing serializers. Strips personality, outputs dense structured JSON. |
| `local_diff.py` | Git diff acquisition. Scope parsing, ref validation, subprocess with timeout. |
| `graph_store.py` | `SQLiteGraphStore` — codebase knowledge graph (nodes, typed edges, migrations). |
| `graph_context.py` | `build_context_pack()` — traverses import graph for pre-review context. |
| `graph_types.py` | Graph node/edge type enums for the knowledge graph. |
| `graph.py` | Backward-compat re-export shim for `graph_types.py` enums. |
| `ignore.py` | `.grippyignore` loading, diff filtering, `# nogrip` pragma parsing. |
| `imports.py` | Python AST import extraction for knowledge graph edges. |
| `embedder.py` | Embedder factory for OpenAI-compatible embedding models. |
| `rules/engine.py` | `RuleEngine` — orchestrates rule execution against parsed diffs. |
| `rules/base.py` | `RuleSeverity`, `RuleResult`, `Rule` protocol, `ResultEnrichment` dataclass. |
| `rules/config.py` | `ProfileConfig`, `PROFILES` dict, `load_profile()` — security profile definitions. |
| `rules/context.py` | `DiffLine`, `DiffHunk`, `ChangedFile`, `RuleContext`, `parse_diff()` — diff parser. |
| `rules/__init__.py` | Public API: `run_rules()`, `check_gate()`, re-exports of core types. |
| `rules/registry.py` | `RULE_REGISTRY` — explicit import list of all 10 rule classes. |
| `rules/enrichment.py` | `enrich_results()` — blast radius, recurrence, import-based suppression, velocity. |
| `rules/*.py` (10) | Individual security rules: secrets, sinks, workflows, traversal, llm-sinks, ci-risk, sql, crypto, creds, deser. |

### Rules Engine

10 rules scan diffs before the LLM: secrets, dangerous sinks, workflow permissions, path traversal, LLM output sinks, CI script risks, SQL injection, weak crypto, hardcoded credentials, insecure deserialization. Controlled by `GRIPPY_PROFILE`:
- `security` (default) — gate fails on ERROR+
- `strict-security` — gate fails on WARN+
- `general` — rules off, LLM-only review

Graph enrichment: `enrich_results()` (rules/enrichment.py) post-processes findings with blast radius, recurrence, import-based suppression, and velocity from the graph store. Gate check skips suppressed findings.

### Prompt System

20 markdown files in `src/grippy/prompts_data/`. Composition:
1. **Identity** (Agno `description`): CONSTITUTION.md + PERSONA.md
2. **Instructions** (Agno `instructions`): system-core.md + mode prefix + 8 shared prompts + scoring-rubric.md + output-schema.md

6 review modes: `pr_review`, `security_audit`, `governance_check`, `surprise_audit`, `cli`, `github_app`.

## Code Conventions

- **Python 3.12+**, managed with **uv**, published as **grippy-mcp** on PyPI
- **Ruff** — line length 100, rules: `E, F, I, N, W, UP, B, RUF, C4` (E501 ignored)
- **MyPy** strict — `disallow_untyped_defs`, `check_untyped_defs`
- **SPDX header** — `# SPDX-License-Identifier: MIT` in first 3 lines of every `.py` file
- **Pre-commit** — trailing whitespace, EOF fixer, YAML/TOML/AST checks, large file (1MB), merge conflict, license header, ruff lint+format, bandit, detect-secrets
- **GitHub Actions SHA-pinned** — no tag-pinned actions, supply chain security
- **Commit messages** — imperative, lowercase, prefixed: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`, `style:`. Always `Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>`
- **PR comments** — never leak internal paths or stack traces. Use `nh3.clean()` for any PR-origin text.
- **Test files** — mirror source structure: `src/grippy/foo.py` → `tests/test_grippy_foo.py`. 50 LOC minimum enforced by parity check.
- **detect-secrets** — test diffs with fake credentials need `# pragma: allowlist secret` + regenerate `.secrets.baseline`

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `GRIPPY_TRANSPORT` | Provider: `openai`, `anthropic`, `google`, `groq`, `mistral`, `local` | `local` |
| `GRIPPY_MODEL_ID` | Model identifier | `devstral-small-2-24b-instruct-2512` |
| `GRIPPY_BASE_URL` | API endpoint for local transport | `http://localhost:1234/v1` |
| `GRIPPY_EMBEDDING_MODEL` | Embedding model name | `text-embedding-qwen3-embedding-4b` |
| `GRIPPY_API_KEY` | API key for non-OpenAI endpoints | `lm-studio` |
| `GRIPPY_DATA_DIR` | Persistence directory | `./grippy-data` |
| `GRIPPY_TIMEOUT` | Review timeout in seconds (0 = none) | `300` |
| `GRIPPY_MAX_DIFF_CHARS` | Max diff chars sent to LLM | `500000` |
| `GRIPPY_PROFILE` | Security profile | `security` |
| `GRIPPY_MODE` | Review mode override | `pr_review` |
| `GRIPPY_FORCE_REINDEX` | Force codebase index rebuild | — |
| `OPENAI_API_KEY` | OpenAI API key (sets transport to openai) | — |
| `ANTHROPIC_API_KEY` | Anthropic API key (when transport=anthropic) | — |
| `GOOGLE_API_KEY` | Google API key (when transport=google) | — |
| `GROQ_API_KEY` | Groq API key (when transport=groq) | — |
| `MISTRAL_API_KEY` | Mistral API key (when transport=mistral) | — |
| `GITHUB_TOKEN` | GitHub API access for PR operations | — |
| `GITHUB_EVENT_PATH` | Path to PR event JSON (set by Actions) | — |

## Security Model

### Codebase Tools (`codebase.py`) — LLM-facing, security-critical

- Path traversal: `Path.is_relative_to()` (not `startswith`)
- Symlink: `grep_code` uses `-S` flag (no follow)
- Glob timeout: 5-second `time.monotonic()` deadline
- Result caps: 5,000 files indexed, 500 glob results, 12,000 chars per tool response
- Sanitization: `tool_hooks` middleware applies `navi_sanitize.clean()` + XML-escape + 12K truncation to all tool outputs before LLM sees them

### Prompt Injection Defense (`agent.py`)

- `_escape_xml()`: navi-sanitize → 7 compiled regex patterns neutralize scoring/confidence/system-override injections → XML entity escape
- `format_pr_context()`: data-fence boundary before all PR content
- `_escape_rule_field()`: XML-escapes filenames, messages, evidence in rule findings

### Output Sanitization (`github_review.py`)

5-stage pipeline on all LLM text before posting to GitHub:
1. `navi_sanitize.clean()` — Unicode normalization
2. `nh3.clean()` — HTML stripping
3. Markdown image removal — tracking pixel defense
4. Markdown link rewriting — phishing prevention
5. Dangerous URI scheme filter

### Retry Safety (`retry.py`)

- `_safe_error_summary()`: strips raw field values from ValidationError before retry prompts
- `_validate_rule_coverage()`: cross-references rule findings against expected counts AND file sets — prevents hallucinated findings

### Session History

Disabled (`add_history_to_context = False`). Prior LLM responses may contain attacker-controlled PR content, enabling history poisoning.

### Adversarial Test Suite

`tests/test_hostile_environment.py` — 44 attack scenarios across 9 domains: Unicode input, prompt injection, tool output injection, output sanitization, codebase tool exploitation, information leakage, schema validation, session history poisoning, PR target advice.

## Trust Boundaries

9 named trust boundaries define where untrusted data enters, transforms, or exits the system. Changes to boundary anchor functions require security review and adversarial test verification.

| ID | Boundary | Anchor Functions | Audit Units |
|---|---|---|---|
| TB-1 | PR metadata ingress | `format_pr_context()`, `_escape_xml()`, `_escape_rule_field()` | agent, review |
| TB-2 | Diff/content ingestion | `fetch_pr_diff()`, `filter_diff()`, `get_local_diff()`, `RuleEngine.run()` | local-diff, review, rule-engine |
| TB-3 | Prompt composition | `load_identity()`, `load_instructions()`, `create_reviewer()` chain, `format_pr_context()` | agent, prompts |
| TB-4 | Tool-call boundary | `CodebaseToolkit` methods, `sanitize_tool_hook()` | codebase |
| TB-5 | Model output boundary | `run_review()`, `_parse_response()`, `_strip_markdown_fences()` | retry |
| TB-6 | GitHub posting boundary | `_sanitize_comment_text()`, `post_review()`, `build_review_comment()`, `resolve_threads()` | github-review |
| TB-7 | Config/credentials boundary | `_resolve_transport()`, `_PROVIDERS` dict (module paths + class names) | agent, cli, mcp-server |
| TB-8 | Rule coverage validation | `_validate_rule_coverage()`, `_safe_error_summary()` | retry |
| TB-9 | Session history boundary | `add_history_to_context` setting in `Agent()` constructor | agent |

**Critical data flow:** PR content → `_escape_xml` → agent prompt → LLM → `run_review` JSON parse → `_validate_rule_coverage` → `github_review` sanitization → GitHub API. Any code touching this path gets extra scrutiny.

## Quality Standards

These standards define the bar for this project. Some are fully met today; others are aspirational targets that all new work should meet.

### Test Quality

- **Fixture matrices:** Tests should cover positive, negative, adversarial, and edge case categories — not just happy paths
- **Security paths require tests:** No merge without test for code touching auth, sanitization, validation, or trust boundaries. Non-negotiable.
- **Adversarial coverage:** Any code processing untrusted input (PR content, LLM output, tool results) needs adversarial test fixtures
- **Test parity:** Every `src/grippy/foo.py` has a `tests/test_grippy_foo.py` with ≥50 LOC (enforced by CI)

### Security-First Development

- **Think in invariants:** "All untrusted PR content is sanitized before prompt insertion" — not "call `_escape_xml()` on line 99"
- **Defense in depth:** No single sanitization layer is trusted alone. The pipeline has multiple independent layers.
- **Fail closed:** Error paths must not produce values that look like success. A review that fails to parse is an error, not a clean bill of health.
- **Evidence over assertion:** When claiming a security property holds, cite the test, trace, or CI check that proves it.

### Change Review

- **Boundary changes** (touches trust boundary anchors from TB-1 through TB-9) → require security review + adversarial test verification
- **Rule changes** (modifies detection patterns in `rules/*.py`) → require fixture matrix update covering positive/negative/adversarial
- **Prompt changes** (modifies prompt chain in `prompts_data/` or `agent.py`) → require adversarial test review for injection resistance
- **Infrastructure changes** (everything else) → standard review

## Audit Framework

The project maintains a formal audit framework at `docs/internals/audit/`. The single source of truth for unit metadata is `docs/internals/audit/registry.yaml`.

**Key concepts:**
- **30 audit units** tracked individually (individual security rules tracked separately because they drift independently)
- **11 scorecard dimensions** including Adversarial Resilience and Auditability & Traceability as first-class concerns
- **Gate semantics:** Override gates (force Critical) and ceiling gates (cap best status) — averages do not determine health
- **Trust boundary triggers:** Changes to boundary anchor functions force re-audit regardless of commit count
- **Evidence tiers:** A (machine-verifiable), B (deterministic repro), C (manual trace), D (hypothesis, not scored)

**Framework documents:** methodology, scorecard template, superset template, freshness tracker, 6 invariant-based checklists, and the registry.

## CI / Quality Gates

| Workflow | Purpose |
|----------|---------|
| `tests.yml` | pytest (3.12 + 3.13), coverage (≥80%), lint, format, typecheck, bandit, semgrep, quality gate, test parity |
| `pre-commit.yml` | Pre-commit hook validation |
| `grippy-review.yml` | Grippy self-review on PRs |
| `codeql.yml` | CodeQL SAST |
| `scorecard.yml` | OpenSSF Scorecard + badge |
| `release.yml` | PyPI publish via OIDC trusted publisher (SLSA L3) |
| `_build-reusable.yml` | Reusable build with attestations + SBOM |

Quality gate (`.github/quality-gate.json`): auto-bumped on main push. Enforces test count floor, coverage floor, and parity violation ceiling.

## Dependencies of Note

- **`agno[openai]`** must stay in core deps — `OpenAILike` (local transport) requires the `openai` SDK
- **`sqlalchemy`** must stay in core deps — not imported by grippy directly, but agno's sqlite session storage depends on it
- **`lancedb`** — codebase vector index, in core deps (moved from optional `[persistence]` extra)
- **Provider extras** — `pip install grippy-mcp[anthropic]` etc. pull `agno[anthropic]>=1.1.0`
