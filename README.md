# Grippy Code Review

> Open-source AI code review agent. Your model, your infrastructure, your rules.

[![Tests](https://github.com/Project-Navi/grippy-code-review/actions/workflows/tests.yml/badge.svg)](https://github.com/Project-Navi/grippy-code-review/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/Project-Navi/grippy-code-review/graph/badge.svg)](https://codecov.io/gh/Project-Navi/grippy-code-review)
[![CodeQL](https://github.com/Project-Navi/grippy-code-review/actions/workflows/codeql.yml/badge.svg)](https://github.com/Project-Navi/grippy-code-review/actions/workflows/codeql.yml)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/Project-Navi/grippy-code-review/badge)](https://scorecard.dev/viewer/?uri=github.com/Project-Navi/grippy-code-review)
[![SLSA 3](https://slsa.dev/images/gh-badge-level3.svg)](https://slsa.dev)
[![PyPI](https://img.shields.io/badge/PyPI-coming%20soon-lightgrey)](https://pypi.org/project/grippy-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

Grippy reviews pull requests using any OpenAI-compatible model — GPT, Claude, or a local LLM running on your own hardware. It indexes your codebase into a vector store for context-aware analysis, then posts structured findings with scores, verdicts, and escalation paths. It also happens to be a grumpy security auditor who secretly respects good code.

## Why Grippy?

- **Your model, your infrastructure.** Bring your own model. No SaaS dependency, no per-seat fees. Run GPT-5 through OpenAI, Claude through a compatible proxy, or a local model via Ollama or LM Studio.

- **Codebase-aware, not diff-blind.** Grippy embeds your repository into a LanceDB hybrid search index (vector + full-text) and searches it during review. It understands the code around the diff, not just the diff itself. Most OSS alternatives paywall this behind a hosted tier.

- **Cross-PR memory, not amnesia.** Grippy builds a knowledge graph of your codebase — tracking files, reviews, findings, and import dependencies across every PR. It knows which modules are blast-radius risks, which files have recurring findings, and which authors have patterns worth watching. Tools like CodeRabbit, Greptile, and Qodo charge $20–38/seat/month for comparable cross-PR context. Here, it's free and open-source.

- **Structured output, not just comments.** Every review produces typed findings with severity, confidence, and category. A score out of 100. A verdict (PASS / FAIL / PROVISIONAL). Escalation targets for findings that need human attention.

- **Security-first, not security-added.** Grippy is a security auditor that also reviews code, not the other way around. Dedicated audit modes go deeper than a general-purpose linter.

- **Deterministic rules, not just LLM guesses.** A built-in rule engine runs 10 security rules against every diff before the LLM sees it. Findings are guaranteed — not hallucinated — and the profile gate can fail CI on critical severity hits, independent of model output.

- **MCP server** — use Grippy as a local diff auditor from Claude Code, Cursor, or Claude Desktop via the Model Context Protocol.

- **It has opinions.** Grippy is a grumpy security auditor persona, not a faceless bot. Good code gets grudging respect. Bad code gets disappointment. The personality keeps reviews readable and honest.

## What it looks like

An inline finding on a PR diff:

> **CRITICAL** | `security` | confidence: 95
>
> **SQL injection via string interpolation**
>
> `query = f"SELECT * FROM users WHERE id = {user_id}"` constructs a SQL query from unsanitized input. Use parameterized queries.
>
> *grippy_note: I've seen production databases get wiped by less. Parameterize it or I'm telling the security team.*

A review summary posted as a PR comment:

> **Score: 45/100** | Verdict: **FAIL** | Complexity: STANDARD
>
> 3 findings (1 critical, 1 high, 1 medium) | 1 escalation to security-team
>
> *"I've reviewed thousands of PRs. This one made me mass in-progress a packet of antacids."*

## Quick start

### GitHub Actions (OpenAI)

Add `.github/workflows/grippy-review.yml` to your repo:

```yaml
name: Grippy Review

on:
  pull_request:
    types: [opened, synchronize, reopened]

permissions:
  contents: read
  pull-requests: write

jobs:
  review:
    name: Grippy Code Review
    runs-on: ubuntu-latest
    steps:
      - uses: step-security/harden-runner@a90bcbc6539c36a85cdfeb73f7e2f433735f215b  # v2.15.0
        with:
          egress-policy: audit

      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd  # v6

      - uses: actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405  # v6
        with:
          python-version: '3.12'

      - name: Install Grippy
        run: pip install "grippy-mcp"

      # Cache the vector index to avoid re-indexing on every push
      - name: Cache Grippy data
        uses: actions/cache@cdf6c1fa76f9f475f3d7449005a359c84ca0f306  # v5
        with:
          path: ./grippy-data
          key: grippy-${{ github.event.pull_request.number }}-${{ github.sha }}
          restore-keys: grippy-${{ github.event.pull_request.number }}-

      - name: Run review
        id: review
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITHUB_EVENT_PATH: ${{ github.event_path }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          GRIPPY_MODEL_ID: gpt-4.1
        run: grippy
```

> **Want LLM-only review without the rule engine?** Set `GRIPPY_PROFILE: general`. For stricter gating (fail on WARN+), use `strict-security`. See [`examples/`](examples/) for more workflow variants.

### GitHub Actions (self-hosted LLM)

Grippy works with any OpenAI-compatible API endpoint, including Ollama, LM Studio, and vLLM. We recommend **Devstral-Small 24B at Q4 quantization or higher** — tested during development for structured output compliance and review quality. See the [Self-Hosted LLM Guide](https://project-navi.github.io/grippy-code-review/how-to/self-hosted-llm-guide/) for full setup instructions.

### Local development

```bash
# OpenAI (default, included in base install)
pip install "grippy-mcp"

# Anthropic
pip install "grippy-mcp[anthropic]"

# Google (Gemini)
pip install "grippy-mcp[google]"

# Groq
pip install "grippy-mcp[groq]"

# Mistral
pip install "grippy-mcp[mistral]"

# Or with uv
uv add "grippy-mcp[anthropic]"
```

### MCP Server

### Quick start (zero install)

```bash
uvx grippy-mcp serve
```

Or install globally:

```bash
pip install grippy-mcp
grippy serve
```

Grippy runs as an MCP server for local git diff auditing — no GitHub Actions required.

**Two tools:**

| Tool | What it does | LLM required? |
|------|-------------|---------------|
| `scan_diff` | Deterministic security rules | No |
| `audit_diff` | Full AI-powered code review | Yes |

**Scope options** (both tools):
- `"staged"` — staged changes (`git diff --cached`)
- `"commit:<ref>"` — a specific commit (e.g. `"commit:HEAD"`)
- `"range:<base>..<head>"` — commit range (e.g. `"range:main..HEAD"`)

**Install into your MCP client:**

```bash
python -m grippy install-mcp          # registers uvx grippy-mcp in client configs
python -m grippy install-mcp --dev    # dev mode: uses uv run --directory
```

The installer detects Claude Code, Claude Desktop, and Cursor, then writes the server config with your chosen LLM transport and API keys.

**Run the server directly:**

```bash
python -m grippy serve
```

MCP tools return dense, structured JSON designed for AI agent consumption — no personality or ASCII art.

## Configuration

Grippy is configured entirely through environment variables.

| Variable | Purpose | Default |
|---|---|---|
| `GRIPPY_TRANSPORT` | API transport: `openai`, `anthropic`, `google`, `groq`, `mistral`, or `local` | `local` |
| `GRIPPY_MODEL_ID` | Model identifier | `devstral-small-2-24b-instruct-2512` |
| `GRIPPY_BASE_URL` | API endpoint for local transport | `http://localhost:1234/v1` |
| `GRIPPY_EMBEDDING_MODEL` | Embedding model name | `text-embedding-qwen3-embedding-4b` |
| `GRIPPY_API_KEY` | API key for non-OpenAI endpoints | `lm-studio` |
| `GRIPPY_DATA_DIR` | Persistence directory | `./grippy-data` |
| `GRIPPY_TIMEOUT` | Review timeout in seconds (0 = none) | `300` |
| `GRIPPY_PROFILE` | Security profile: `security`, `strict-security`, `general` | `security` |
| `GRIPPY_MODE` | Review mode override | `pr_review` |
| `OPENAI_API_KEY` | OpenAI API key (sets transport to `openai`) | — |
| `GITHUB_TOKEN` | GitHub API token (set automatically by Actions) | — |

### Cross-vendor model selection

If your codebase is co-developed with an AI coding assistant, **we strongly recommend running Grippy on a model from a different vendor** than the one that wrote the code. Different model families have different training data, different biases, and different blind spots. A reviewer that shares the same priors as the author is more likely to miss the same classes of bugs. Using a cross-vendor model — for example, reviewing GPT-authored code with Claude, or Claude-authored code with GPT — gives you a genuinely independent audit rather than an echo chamber.

## Security profiles

Grippy ships with the deterministic rule engine **on by default** (`security` profile). Ten rules scan every diff for secrets, dangerous sinks, workflow permission escalation, path traversal, unsanitized LLM output, risky CI scripts, SQL injection, weak cryptography, hardcoded credentials, and insecure deserialization — before the LLM sees anything. These findings are guaranteed, not hallucinated.

Switch profiles via `GRIPPY_PROFILE` env var or `--profile` CLI flag (CLI takes priority).

| Profile | What happens | Gate behavior | When to use |
|---|---|---|---|
| **`security`** (default) | Rules + LLM review | CI fails on ERROR or CRITICAL rule findings | Most teams — catches real issues without noise |
| `strict-security` | Rules + LLM review | CI fails on WARN or higher | High-assurance, compliance, external contributors |
| `general` | LLM review only | No rule gate | When you only want AI-powered review, no deterministic scanning |

```bash
# Use the default (security)
grippy

# Explicit profile
grippy --profile strict-security

# Via environment variable
GRIPPY_PROFILE=general grippy
```

The 10 deterministic rules:

| Rule ID | Detects | Severity |
|---|---|---|
| `workflow-permissions-expanded` | write/admin permissions, unpinned actions | ERROR / WARN |
| `secrets-in-diff` | API keys, private keys, `.env` additions | CRITICAL / WARN |
| `dangerous-execution-sinks` | unsafe code execution patterns | ERROR |
| `path-traversal-risk` | tainted path variables, `../` patterns | WARN |
| `llm-output-unsanitized` | model output piped to sinks without sanitizer | ERROR |
| `ci-script-execution-risk` | risky CI script patterns, sudo in CI | CRITICAL / WARN |
| `sql-injection-risk` | SQL queries built from interpolated input | ERROR |
| `weak-crypto` | MD5, SHA1, DES, ECB mode, insecure RNG | WARN |
| `hardcoded-credentials` | passwords, connection strings, auth headers | ERROR |
| `insecure-deserialization` | unsafe deserialization sinks (shelve, dill, etc.) | ERROR |

Rule findings are injected into the LLM context as confirmed facts for explanation.

When the knowledge graph is available (CI with caching, or MCP with persistent `GRIPPY_DATA_DIR`), rule findings are enriched with:
- **Blast radius** — how many modules depend on the flagged file
- **Recurrence** — whether this rule has fired on this file in prior reviews
- **False positive suppression** — import-aware suppression (e.g., SQL injection suppressed when file imports SQLAlchemy)
- **Finding velocity** — how often this rule fires across recent reviews

## Suppression

### `.grippyignore` — file-level suppression

Create a `.grippyignore` file in your repo root to exclude files from review. Uses gitignore syntax (comments, negation, wildcards):

```
# Exclude generated code
vendor/
*.generated.py

# Exclude test fixtures that contain intentional anti-patterns
tests/test_rule_*.py

# But keep the hostile environment tests
!tests/test_hostile_environment.py
```

Excluded files are stripped from the diff before either the rule engine or the LLM sees them.

### `# nogrip` — line-level pragma

Suppress deterministic rule findings on specific lines:

```python
password = os.environ["DB_PASS"]  # nogrip
conn = f"postgres://{user}:{password}@host/db"  # nogrip: hardcoded-credentials
h = hashlib.md5(data)  # nogrip: weak-crypto, hardcoded-credentials
```

- Bare `# nogrip` suppresses all rules on that line
- `# nogrip: rule-id` suppresses only the named rule
- `# nogrip: id1, id2` suppresses multiple rules
- **Rules only** — the LLM reviewer still sees the line and may comment on it

## Review modes

| Mode | Trigger | Focus |
|---|---|---|
| `pr_review` | Default on PR events | Full code review: correctness, security, style, maintainability |
| `security_audit` | Manual, scheduled, or auto when `profile != general` | Deep security analysis: injection, auth, cryptography, data exposure |
| `governance_check` | Manual or scheduled | Compliance and policy: licensing, access control, audit trails |
| `surprise_audit` | PR title/body contains "production ready" | Full-scope audit with expanded governance checks |
| `cli` | Local invocation | Interactive review for local development and testing |
| `github_app` | GitHub App webhook | Event-driven review via installed GitHub App |

## GitHub Actions outputs

When running as a GitHub Action, Grippy sets these step outputs for downstream workflow logic:

| Output | Type | Description |
|---|---|---|
| `score` | int | Review score 0–100 |
| `verdict` | string | `PASS` / `FAIL` / `PROVISIONAL` |
| `findings-count` | int | Total LLM finding count |
| `merge-blocking` | bool | Whether verdict blocks merge |
| `rule-findings-count` | int | Deterministic rule hit count |
| `rule-gate-failed` | bool | Whether rule gate caused CI failure |
| `profile` | string | Active security profile name |

## Security

Grippy operates in an adversarial environment — PR diffs are untrusted input controlled by any contributor. Defense-in-depth sanitization is applied at every stage of the pipeline, validated by a 44-test adversarial test suite covering 9 attack domains.

**Input sanitization.** All untrusted text (PR metadata, diffs, tool outputs) passes through [navi-sanitize](https://pypi.org/project/navi-sanitize/) for Unicode normalization — stripping invisible characters (ZWSP, bidi overrides, variation selectors), normalizing homoglyphs (Cyrillic/Greek → ASCII), and removing null bytes. This runs before any other processing.

**Prompt injection defense.** Three layers protect the LLM context:
1. **XML escaping** — All context sections (`<diff>`, `<pr_metadata>`, `<rule_findings>`, etc.) are XML-escaped, preventing `</diff><system>...` breakout attacks.
2. **NL injection pattern neutralization** — Seven compiled regex patterns detect and replace natural-language injection attempts (scoring directives, confidence manipulation, system override phrases) with `[BLOCKED]` markers.
3. **Data-fence boundary** — A preamble in the LLM prompt explicitly marks all subsequent content as "USER-PROVIDED DATA only" with instructions to ignore embedded directives.

**Output sanitization.** LLM-generated text passes through a five-stage pipeline before posting to GitHub:

1. **[navi-sanitize](https://pypi.org/project/navi-sanitize/)** — Unicode normalization (same as input stage).
2. **nh3** — Rust-based HTML sanitizer strips all HTML tags from free-text fields.
3. **Markdown image stripping** — Removes `![](url)` syntax to prevent tracking pixels in review comments.
4. **Markdown link rewriting** — Converts `[text](https://url)` to plain text to prevent phishing links.
5. **URL scheme filter** — Removes `javascript:`, `data:`, and `vbscript:` schemes from remaining link syntax.

**Tool output sanitization.** Codebase tool responses (`read_file`, `grep_code`, `list_files`) are sanitized with navi-sanitize and XML-escaped before reaching the LLM, preventing indirect prompt injection through crafted file contents.

**Adversarial test suite.** `tests/test_hostile_environment.py` exercises 44 attack scenarios across Unicode attacks, prompt injection, tool exploitation, output sanitization gaps, information leakage, schema validation attacks, session history poisoning, and more. All 44 pass.

See the [Security Model](https://project-navi.github.io/grippy-code-review/explanation/security-model/) for codebase tool protections, CI hardening, and the full threat model.

### Retrieval Quality Benchmarks

Grippy includes a benchmark suite for validating search and graph retrieval quality.

```bash
# Run search benchmarks (requires embedding model)
python -m benchmarks search --k 5

# Run graph retrieval benchmarks (requires populated graph DB)
python -m benchmarks graph

# Run all benchmarks
python -m benchmarks all
```

Results are written as JSON to `benchmarks/output/`.

## Documentation

- [Getting Started](https://project-navi.github.io/grippy-code-review/getting-started/quickstart/) — Setup for OpenAI, local LLMs, and development
- [Configuration](https://project-navi.github.io/grippy-code-review/how-to/configuration/) — Environment variables and model options
- [Architecture](https://project-navi.github.io/grippy-code-review/explanation/architecture/) — Module map, prompt system, data flow
- [Review Modes](https://project-navi.github.io/grippy-code-review/how-to/review-modes/) — The 6 review modes and how they work
- [Scoring Rubric](https://project-navi.github.io/grippy-code-review/reference/scoring-rubric/) — How Grippy scores PRs
- [Security Model](https://project-navi.github.io/grippy-code-review/explanation/security-model/) — Codebase tool protections, hardened CI
- [Self-Hosted LLM Guide](https://project-navi.github.io/grippy-code-review/how-to/self-hosted-llm-guide/) — Ollama/LM Studio + Cloudflare Tunnel
- [Contributing](https://project-navi.github.io/grippy-code-review/how-to/contributing/) — Dev setup, testing, conventions
- [Examples](examples/) — Copy-paste workflow YAMLs and sample review output
- [Changelog](https://project-navi.github.io/grippy-code-review/reference/changelog/) — Release history

## License

[MIT](LICENSE)
