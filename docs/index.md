---
hide:
  - navigation
  - toc
---

# grippy-code-review

**AI-powered PR review agent with security rule engine.**

Runs with any OpenAI-compatible model as an MCP server or GitHub Actions workflow. Indexes your codebase for context-aware analysis, runs a deterministic security rule engine before the LLM, scores PRs against a structured rubric, and posts inline findings --- all as a grumpy security auditor who is reluctantly thorough.

[Get Started](getting-started/quickstart.md){ .md-button .md-button--primary }
[Configuration](how-to/configuration.md){ .md-button }

---

## Pages

- **[Getting Started](getting-started/quickstart.md)** --- Setup for MCP server, OpenAI, local LLMs, and development
- **[Configuration](how-to/configuration.md)** --- Environment variables, transports, and model options
- **[Architecture](explanation/architecture.md)** --- Modules, prompt composition, data flow
- **[Knowledge Graph](explanation/knowledge-graph.md)** --- Cross-PR memory, blast radius, and codebase graph
- **[Review Modes](how-to/review-modes.md)** --- The 6 review modes and how they work
- **[Scoring Rubric](reference/scoring-rubric.md)** --- How Grippy scores PRs
- **[Security Model](explanation/security-model.md)** --- Rule engine, codebase tool protections, and CI hardening
- **[Self-Hosted LLM Guide](how-to/self-hosted-llm-guide.md)** --- Run your own model with Cloudflare Tunnel
- **[Contributing](how-to/contributing.md)** --- Development setup, testing, and conventions

## Quick links

- [GitHub repository](https://github.com/Project-Navi/grippy-code-review)
- [PyPI package](https://pypi.org/project/grippy-mcp/) (`pip install grippy-mcp`)
- [MIT License](https://github.com/Project-Navi/grippy-code-review/blob/main/LICENSE)
- [Issue tracker](https://github.com/Project-Navi/grippy-code-review/issues)
