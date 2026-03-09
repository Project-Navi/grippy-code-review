# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-03-09

### Added

- **AI code review agent** — Agno-based agent with structured output (GrippyReview schema)
- **MCP server** — `grippy serve` or `uvx grippy-mcp serve` exposes two tools for local git diff auditing:
  - `scan_diff` — deterministic security rules only (no LLM, instant results)
  - `audit_diff` — full AI-powered review pipeline with structured findings
  - Scope parameter: `"staged"`, `"commit:<ref>"`, `"range:<base>..<head>"`
- **MCP client installer** — `grippy install-mcp` detects Claude Code, Claude Desktop, and Cursor, then writes server config with chosen transport and API keys
- **Multi-provider support** — 6 LLM transports via Agno's provider ecosystem:
  - `openai` (OpenAIChat, native structured outputs)
  - `anthropic` (Claude), `google` (Gemini), `groq` (Groq), `mistral` (MistralChat)
  - `local` (OpenAILike for Ollama, LM Studio, vLLM)
- **GitHub Actions deployment** — PR review on `pull_request` events with inline findings
- **6 review modes** — pr_review, security_audit, governance_check, surprise_audit, cli, github_app
- **Deterministic rule engine** — 10 security rules (secrets, dangerous sinks, workflow permissions, path traversal, LLM output sinks, CI script risks, SQL injection, weak crypto, hardcoded credentials, insecure deserialization)
- **Suppression directives** — `.grippyignore` for file/path exclusion (gitignore syntax), `# nogrip` inline pragma for line-level rule suppression
- **3 security profiles** — general (rules off), security (ERROR+ gate), strict-security (WARN+ gate)
- **Scoring rubric** — 0-100 score across 5 dimensions (security, logic, governance, reliability, observability)
- **Codebase indexing** — LanceDB hybrid search (vector + full-text + RRF reranking) with vector-only fallback
- **Knowledge graph** — SQLite graph tracking files, reviews, findings, imports across PRs
- **Graph-enhanced rule engine** — rule findings enriched with blast radius, recurrence detection, import-based false positive suppression, and finding velocity
- **Prompt injection defense** — XML escaping, NL pattern neutralization, data-fence boundaries
- **Output sanitization** — 5-stage pipeline (navi-sanitize → nh3 → image strip → link rewrite → scheme filter)
- **Adversarial test suite** — 44 attack scenarios across 9 domains
- **Grumpy personality** — security auditor persona with tone calibration, catchphrases, disguises
- **Surprise audit** — "production ready" trigger activates expanded governance check
- **Console scripts** — `grippy` and `grippy-mcp` CLI entry points
- **Provider extras** — `pip install "grippy-mcp[anthropic]"` etc. for non-OpenAI providers
- **Retrieval quality benchmarks** — `python -m benchmarks search` and `python -m benchmarks graph`
- **SLSA Level 3** build provenance with OIDC trusted publishing
- **OpenSSF Scorecard** integration with automated badge updates
- **Dual SBOM** — CycloneDX and SPDX generated on every release

[0.1.0]: https://github.com/Project-Navi/grippy-code-review/releases/tag/v0.1.0
