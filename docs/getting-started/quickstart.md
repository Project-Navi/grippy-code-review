# Getting Started

Four ways to run Grippy: as an MCP server for local diff auditing, GitHub Actions with OpenAI, GitHub Actions with a self-hosted LLM, or locally for development.

---

## 1. MCP Server (Local Diff Auditing)

Grippy runs as an MCP server for local git diff auditing from Claude Code, Cursor, or Claude Desktop --- no GitHub Actions required.

### Zero-install

```bash
uvx grippy-mcp serve
```

Or install globally:

```bash
pip install grippy-mcp
grippy serve
```

**Two tools:**

| Tool | What it does | LLM required? |
|------|-------------|---------------|
| `scan_diff` | Deterministic security rules | No |
| `audit_diff` | Full AI-powered code review | Yes |

**Scope options** (both tools):
- `"staged"` --- staged changes (`git diff --cached`)
- `"commit:<ref>"` --- a specific commit (e.g. `"commit:HEAD"`)
- `"range:<base>..<head>"` --- commit range (e.g. `"range:main..HEAD"`)

**Install into your MCP client:**

```bash
grippy install-mcp          # registers uvx grippy-mcp in client configs
grippy install-mcp --dev    # dev mode: uses uv run --directory
```

The installer detects Claude Code, Claude Desktop, and Cursor, then writes the server config with your chosen LLM transport and API keys.

---

## 2. GitHub Actions + OpenAI

The fastest path for CI integration. You need:

- A GitHub repository
- Python 3.12+
- An [OpenAI API key](https://platform.openai.com/api-keys)

### Step 1: Add your API key as a repository secret

Go to **Settings > Secrets and variables > Actions** and add `OPENAI_API_KEY` with your OpenAI key. The `GITHUB_TOKEN` is provided automatically by Actions.

### Step 2: Add the workflow

Create `.github/workflows/grippy-review.yml`:

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

      - name: Run review
        id: review
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITHUB_EVENT_PATH: ${{ github.event_path }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          GRIPPY_TRANSPORT: openai
          GRIPPY_MODEL_ID: gpt-4.1
          GRIPPY_EMBEDDING_MODEL: text-embedding-3-large
          GRIPPY_DATA_DIR: ./grippy-data
          GRIPPY_TIMEOUT: 300
          # GRIPPY_PROFILE: security  # Default — deterministic rules ON, gate fails on ERROR+
        run: python -m grippy
```

All actions are SHA-pinned (not tag-pinned) for supply chain security.

### Step 3: Verify

Open a pull request and check the **Actions** tab. Grippy will post inline findings on the diff and a summary comment with the score and verdict.

---

## 3. GitHub Actions + Self-Hosted LLM

Run your own model (Ollama, LM Studio, vLLM) and connect it to GitHub Actions via a Cloudflare Tunnel. No API keys to manage, no per-token costs.

See the **[Self-Hosted LLM Guide](../how-to/self-hosted-llm-guide.md)** for the full tutorial, including tunnel setup, workflow configuration, and model recommendations.

---

## 4. Local Development

### Clone and install

```bash
git clone https://github.com/Project-Navi/grippy-code-review.git
cd grippy-code-review
```

Install with [uv](https://docs.astral.sh/uv/):

```bash
uv sync
```

Or with pip:

```bash
pip install -e .
```

For other providers:

```bash
pip install "grippy-mcp[anthropic]"   # Anthropic (Claude)
pip install "grippy-mcp[google]"      # Google (Gemini)
pip install "grippy-mcp[groq]"        # Groq
pip install "grippy-mcp[mistral]"     # Mistral
```

### Set environment variables

For OpenAI:

```bash
export OPENAI_API_KEY="sk-..."  # pragma: allowlist secret
export GITHUB_TOKEN="ghp_..."  # pragma: allowlist secret
```

For a local model (LM Studio, Ollama, etc.):

```bash
export GRIPPY_TRANSPORT=local  # Valid: openai, anthropic, google, groq, mistral, local
export GRIPPY_BASE_URL="http://localhost:1234/v1"
export GRIPPY_MODEL_ID="devstral-small-2-24b-instruct-2512"
export GITHUB_TOKEN="ghp_..."  # pragma: allowlist secret
# Optional: enable security rule engine
export GRIPPY_PROFILE=security
```

### Create a mock event file

Grippy reads the PR payload from `GITHUB_EVENT_PATH`. For local testing, create an `event.json`:

```json
{
  "pull_request": {
    "number": 1,
    "title": "Test PR",
    "user": { "login": "testuser" },
    "head": { "ref": "feature-branch", "sha": "abc1234" },
    "base": { "ref": "main" },
    "body": "Test description"
  },
  "repository": {
    "full_name": "your-org/your-repo"
  }
}
```

### Run

```bash
export GITHUB_EVENT_PATH=event.json
python -m grippy

# Or use the console script
grippy
```

---

## Caching

Add the `actions/cache` step to persist Grippy's LanceDB vector index and graph database between runs. This avoids re-indexing the codebase on every PR push.

```yaml
      - name: Cache Grippy data
        uses: actions/cache@cdf6c1fa76f9f475f3d7449005a359c84ca0f306  # v5
        with:
          path: ./grippy-data
          key: grippy-data-${{ github.event.pull_request.number || 'manual' }}-${{ github.sha }}
          restore-keys: |
            grippy-data-${{ github.event.pull_request.number || 'manual' }}-
```

Place this step after checkout and before `pip install`. The cache is keyed per PR number and commit SHA, with fallback to the latest cache for that PR.

---

## GitHub Actions Outputs

Grippy sets seven outputs after a successful review:

| Output | Description | Example |
|---|---|---|
| `score` | Overall score (0-100) | `72` |
| `verdict` | PASS, FAIL, or PROVISIONAL | `PASS` |
| `findings-count` | Number of findings | `3` |
| `merge-blocking` | Whether the review blocks merge | `false` |
| `rule-findings-count` | Deterministic rule hit count | `2` |
| `rule-gate-failed` | Whether rule gate caused CI failure | `false` |
| `profile` | Active security profile name | `security` |

Use these in subsequent workflow steps by referencing the step ID:

```yaml
      - name: Run review
        id: review
        run: python -m grippy

      - name: Review summary
        if: always()
        run: |
          echo "### Grippy Review Results" >> "$GITHUB_STEP_SUMMARY"
          echo "- Score: ${{ steps.review.outputs.score }}" >> "$GITHUB_STEP_SUMMARY"
          echo "- Verdict: ${{ steps.review.outputs.verdict }}" >> "$GITHUB_STEP_SUMMARY"
          echo "- Findings: ${{ steps.review.outputs.findings-count }}" >> "$GITHUB_STEP_SUMMARY"
          echo "- Merge blocking: ${{ steps.review.outputs.merge-blocking }}" >> "$GITHUB_STEP_SUMMARY"

      - name: Block merge on failure
        if: steps.review.outputs.merge-blocking == 'true'
        run: exit 1
```
