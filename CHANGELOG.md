# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - Unreleased

### Added

- **MCP server** — `grippy serve` or `uvx grippy-mcp serve` exposes two tools for local git diff auditing:
  - `scan_diff` — deterministic security rules only (no LLM, instant results)
  - `audit_diff` — full AI-powered review pipeline with structured findings
  - Scope parameter: `"staged"`, `"commit:<ref>"`, `"range:<base>..<head>"`
- **MCP client installer** — `grippy install-mcp` detects Claude Code, Claude Desktop, and Cursor, then writes server config with chosen transport and API keys
- **Multi-provider support** — 6 LLM transports via Agno's provider ecosystem:
  - `openai` (OpenAIChat, native structured outputs)
  - `anthropic` (Claude), `google` (Gemini), `groq` (Groq), `mistral` (MistralChat)
  - `local` (OpenAILike for Ollama, LM Studio, vLLM)
- **Console scripts** — `grippy` and `grippy-mcp` CLI entry points
- **Provider extras** — `pip install "grippy-mcp[anthropic]"` etc. for non-OpenAI providers
- **Retrieval quality benchmarks** — `python -m benchmarks search` and `python -m benchmarks graph` for validating search and graph retrieval quality
- **Hybrid search** — migrated CodebaseIndex from pure vector search to LanceDB hybrid search (vector + full-text + RRF reranking) with vector-only fallback
- **LanceDB in core deps** — moved from optional `[persistence]` extra to always-available
- **4 new OWASP security rules** — expands deterministic rule engine from 6 to 10 rules:
  - `sql-injection-risk` — SQL queries built via f-strings, %-formatting, or concatenation (A03)
  - `weak-crypto` — MD5, SHA1, DES, ECB mode, and `random` for security contexts (A02)
  - `hardcoded-credentials` — hardcoded passwords, DB connection strings, auth headers (A07)
  - `insecure-deserialization` — unsafe deserialization sinks: shelve, dill, yaml.load, torch.load (A08)

### Changed

- **Default security profile** changed from `general` to `security` — the deterministic rule engine now runs by default. Set `GRIPPY_PROFILE=general` to disable rules for LLM-only review.
- **Package renamed** from `grippy-code-review` to `grippy-mcp` on PyPI
- **MEDIUM confidence minimum** aligned to 75 (was 70 in scoring-rubric prompt, now matches confidence-filter)
- **Transport hints** in error messages list all 6 providers (was only openai/local)
- **Quality gate** auto-bumps on main push — 845+ tests, 97%+ coverage, 0 parity violations

### Fixed

- Anti-drift audit fixing stale docs, dependencies, and quality gate thresholds

## [0.1.0] - 2026-03-01

### Added

- **AI code review agent** — Agno-based agent with structured output (GrippyReview schema)
- **GitHub Actions deployment** — PR review on `pull_request` events with inline findings
- **6 review modes** — pr_review, security_audit, governance_check, surprise_audit, cli, github_app
- **Deterministic rule engine** — 6 security rules (secrets, dangerous sinks, workflow permissions, path traversal, LLM output sinks, CI script risks)
- **3 security profiles** — general (rules off), security (ERROR+ gate), strict-security (WARN+ gate)
- **Scoring rubric** — 0-100 score across 5 dimensions (security, logic, governance, reliability, observability)
- **Codebase indexing** — LanceDB vector store with read_file, grep_code, list_files tools
- **Knowledge graph** — SQLite graph tracking files, reviews, findings, imports across PRs
- **Prompt injection defense** — XML escaping, NL pattern neutralization, data-fence boundaries
- **Output sanitization** — 5-stage pipeline (navi-sanitize → nh3 → image strip → link rewrite → scheme filter)
- **Adversarial test suite** — 44 attack scenarios across 9 domains
- **Grumpy personality** — security auditor persona with tone calibration, catchphrases, disguises
- **Surprise audit** — "production ready" trigger activates expanded governance check
- **SLSA Level 3** build provenance with OIDC trusted publishing
- **OpenSSF Scorecard** integration with automated badge updates

[0.2.0]: https://github.com/Project-Navi/grippy-code-review/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Project-Navi/grippy-code-review/releases/tag/v0.1.0
