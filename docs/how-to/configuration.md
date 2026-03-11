# Configuration

All configuration is through environment variables, with one CLI flag (`--profile`) that overrides `GRIPPY_PROFILE`.

---

## Environment Variables

| Variable | Description | Default | Notes |
|---|---|---|---|
| `GRIPPY_TRANSPORT` | API transport: `openai`, `anthropic`, `google`, `groq`, `mistral`, or `local` | Inferred from `OPENAI_API_KEY` | See [Transport Resolution](#transport-resolution) below |
| `GRIPPY_MODEL_ID` | Model identifier at the inference endpoint | `devstral-small-2-24b-instruct-2512` | Any model name your endpoint accepts |
| `GRIPPY_BASE_URL` | OpenAI-compatible API base URL | `http://localhost:1234/v1` | Used by `local` transport only |
| `GRIPPY_EMBEDDING_MODEL` | Embedding model name | `text-embedding-qwen3-embedding-4b` | Must serve the `/v1/embeddings` endpoint |
| `GRIPPY_API_KEY` | API key for non-OpenAI endpoints | `lm-studio` | Embedding auth fallback for local endpoints |
| `GRIPPY_DATA_DIR` | Persistence directory for vector index and graph DB | `./grippy-data` | Created automatically if it doesn't exist |
| `GRIPPY_TIMEOUT` | Review timeout in seconds | `300` | Set to `0` to disable the timeout |
| `GRIPPY_MAX_DIFF_CHARS` | Max diff chars sent to LLM | `500000` | Lower this for local models with smaller context windows (e.g. `100000` for 32K context) |
| `GRIPPY_PROFILE` | Security rule engine profile | `security` | See [Security Profiles](#security-profiles) below |
| `GRIPPY_MODE` | Review mode | `pr_review` | One of: `pr_review`, `security_audit`, `governance_check`, `surprise_audit`, `cli`, `github_app` |
| `GRIPPY_FORCE_REINDEX` | Force codebase index rebuild | --- | Set to `1`, `true`, or `yes` to force re-index |
| `OPENAI_API_KEY` | OpenAI API key | --- | Presence auto-sets transport to `openai` |
| `ANTHROPIC_API_KEY` | Anthropic API key (when transport=anthropic) | --- | Requires `pip install "grippy-mcp[anthropic]"` |
| `GOOGLE_API_KEY` | Google API key (when transport=google) | --- | Requires `pip install "grippy-mcp[google]"` |
| `GROQ_API_KEY` | Groq API key (when transport=groq) | --- | Requires `pip install "grippy-mcp[groq]"` |
| `MISTRAL_API_KEY` | Mistral API key (when transport=mistral) | --- | Requires `pip install "grippy-mcp[mistral]"` |
| `GITHUB_TOKEN` | GitHub API token for fetching diffs and posting comments | --- | Set automatically by GitHub Actions |
| `GITHUB_EVENT_PATH` | Path to PR event JSON payload | --- | Set automatically by GitHub Actions |
| `GITHUB_REPOSITORY` | Repository full name (`owner/repo`) | --- | Set automatically by GitHub Actions (fallback) |

---

## Transport Resolution

Grippy uses a three-tier priority to determine how it connects to the LLM:

1. **Explicit parameter** --- `GRIPPY_TRANSPORT` is set to one of: `openai`, `anthropic`, `google`, `groq`, `mistral`, `local`
2. **Inferred from API key** --- If `OPENAI_API_KEY` is present and `GRIPPY_TRANSPORT` is unset, transport is inferred as `openai`
3. **Default** --- Falls back to `local`

### Provider Details

| Transport | Agno Model Class | Structured Output | Install |
|-----------|-----------------|-------------------|---------|
| `openai` | `OpenAIChat` | Native (wire-level schema enforcement) | Included in base install |
| `anthropic` | `Claude` | JSON-mode with retry validation | `pip install "grippy-mcp[anthropic]"` |
| `google` | `Gemini` | JSON-mode with retry validation | `pip install "grippy-mcp[google]"` |
| `groq` | `Groq` | JSON-mode with retry validation | `pip install "grippy-mcp[groq]"` |
| `mistral` | `MistralChat` | JSON-mode with retry validation | `pip install "grippy-mcp[mistral]"` |
| `local` | `OpenAILike` | JSON-mode with retry validation | Included in base install |

When transport is `openai`:
- Uses `OpenAIChat` from the Agno framework
- Reads `OPENAI_API_KEY` from the environment
- `GRIPPY_BASE_URL` is ignored (OpenAI's endpoint is used directly)
- Enables native structured outputs (`structured_outputs=True`) for wire-level JSON schema enforcement

When transport is `local`:
- Uses `OpenAILike` from the Agno framework
- Connects to `GRIPPY_BASE_URL` (default: `http://localhost:1234/v1`)
- Accepts any API key (LM Studio, Ollama, and vLLM don't validate keys)

When transport is any other provider (`anthropic`, `google`, `groq`, `mistral`):
- Uses the provider's native Agno model class
- Reads the provider-specific API key from the environment
- `GRIPPY_BASE_URL` is ignored

If `GRIPPY_TRANSPORT` is set to an unrecognized value, the agent exits with a config error.

---

## Security Profiles

The `GRIPPY_PROFILE` environment variable controls the deterministic security rule engine. The `--profile` CLI flag overrides the env var.

| Profile | Rule engine | Gate threshold | When to use |
|---|---|---|---|
| **`security`** (default) | **On** | Fail on `ERROR`+ | Most teams. Deterministic rules catch real issues without noise. Mode auto-overrides to `security_audit`. |
| `strict-security` | **On** | Fail on `WARN`+ | High-assurance environments, external contributors, compliance. |
| `general` | **Off** | --- | LLM-only review. No deterministic rules run. Use when you only want AI-powered review. |

Priority: CLI `--profile` > `GRIPPY_PROFILE` env var > default (`security`).

```bash
# Use the default (security) — rules ON, gate fails on ERROR+
grippy

# Stricter gating — gate also fails on WARN
grippy --profile strict-security

# LLM-only, no rules
GRIPPY_PROFILE=general grippy
```

When the rule engine activates, it runs 10 deterministic rules on the full diff before the LLM call. Rule findings are injected into the LLM context as confirmed facts. See [Architecture --- Rule Engine](../explanation/architecture.md#rule-engine) for details.

---

## Model Recommendations

> **Opinion: use a different vendor than your coding assistant.** If your codebase is co-developed with an AI coding assistant, run Grippy on a model from a different vendor. Different model families have different training data, different biases, and different blind spots. A reviewer that shares the same priors as the author is more likely to miss the same classes of bugs. Cross-vendor review --- e.g., reviewing GPT-authored code with Claude, or Claude-authored code with GPT --- gives you a genuinely independent audit rather than an echo chamber.

### Chat models

| Use case | Model | Quant | Notes |
|---|---|---|---|
| Recommended | `gpt-4.1` | — | Best balance of cost, speed, and structured output quality |
| Fast / cheap | `gpt-4.1-mini` | — | Good for rapid iteration on smaller PRs |
| Fast / local | `devstral-small-2-24b-instruct-2512` | Q4_K_S+ | **Recommended local model.** Validated with full e2e test suite. Runs on consumer GPUs with 16GB+ VRAM. |
| Reasoning / local | `nvidia/nemotron-3-nano` | Q3_K_L+ | 30B (A3B active) reasoning model. Validated with full e2e test suite. Grippy handles `reasoning_content` output automatically. |
| Thorough | `claude-sonnet-4-20250514` | — | First-class provider via `GRIPPY_TRANSPORT=anthropic`. Requires `pip install "grippy-mcp[anthropic]"`. |

### Embedding models

| Use case | Model | Notes |
|---|---|---|
| OpenAI | `text-embedding-3-large` | Best retrieval quality, 3072 dimensions |
| Local | `text-embedding-qwen3-embedding-4b` | Default local embedding model |

Set the embedding model with `GRIPPY_EMBEDDING_MODEL`. The embedding endpoint must be OpenAI-compatible (`/v1/embeddings`).

---

## Persistence

`GRIPPY_DATA_DIR` stores two things:

1. **LanceDB vector index** (`lance/`) --- Codebase chunks embedded for semantic search during review. The agent uses this to understand code beyond the diff.
2. **SQLite graph database** (`navi-graph.db`) --- Nodes and edges tracking review entities (findings, patterns, files, authors) across review rounds. A separate `grippy-session.db` stores Agno agent session state.

### Caching in CI

Cache `GRIPPY_DATA_DIR` between workflow runs to avoid re-indexing the codebase on every push. The workflow in this repo uses:

```yaml
- name: Cache Grippy data
  uses: actions/cache@cdf6c1fa76f9f475f3d7449005a359c84ca0f306  # v5
  with:
    path: ./grippy-data
    key: grippy-data-${{ github.event.pull_request.number || 'manual' }}-${{ github.sha }}
    restore-keys: |
      grippy-data-${{ github.event.pull_request.number || 'manual' }}-
```

### Important notes

- Data is **repo-specific** --- don't share a `GRIPPY_DATA_DIR` across different repositories.
- The vector index is rebuilt if the `codebase_chunks` table doesn't exist. Deleting the cache forces a full re-index.
- The graph database uses WAL mode and foreign keys for integrity. It is safe to cache and restore across runs.

---

## MCP Server Configuration

When running as an MCP server (`grippy serve` or `uvx grippy-mcp serve`), the same environment variables apply. The server reads `GRIPPY_TRANSPORT`, `GRIPPY_MODEL_ID`, `GRIPPY_BASE_URL`, `GRIPPY_API_KEY`, and `GRIPPY_PROFILE` from its environment.

The `grippy install-mcp` command provides an interactive installer that configures these variables for your MCP client:

```bash
grippy install-mcp              # published mode (uvx grippy-mcp)
grippy install-mcp --dev        # dev mode (uv run --directory)
```

The installer detects Claude Code, Claude Desktop, and Cursor, and writes the appropriate server configuration.
