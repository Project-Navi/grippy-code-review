# Self-Hosted LLM Guide

Run your own model on your own hardware and connect it securely to GitHub Actions via Cloudflare Tunnel. Your code never leaves your network.

This guide walks through the full setup: model server, secure tunnel, zero-trust access policy, and GitHub Actions workflow. By the end, your Grippy reviews will run against a model you control, with no code or prompts sent to any third-party API.

---

> **Note:** The security rule engine (`GRIPPY_PROFILE=security` or `strict-security`) runs deterministically on the raw diff using regex and static analysis --- it does not require any LLM inference. Even if your self-hosted model is slow or temporarily unavailable, rule findings are detected and the quality gate is evaluated independently. This is especially relevant for `strict-security` profile, where WARN-level findings block CI before the LLM ever runs.

## Prerequisites

- A machine with a GPU (or CPU for smaller models like Devstral-Small-24B)
- A [Cloudflare account](https://dash.cloudflare.com/sign-up) (free tier works)
- A domain managed by Cloudflare (for the tunnel hostname)
- A GitHub repository with Actions enabled

---

## 1. Set Up the Model Server

Grippy needs two models: a **chat model** for the review and an **embedding model** for codebase indexing. Both must serve OpenAI-compatible endpoints (`/v1/chat/completions` and `/v1/embeddings`).

### Option A: Ollama

Install Ollama and pull the models:

```bash
curl -fsSL https://ollama.ai/install.sh | sh

# Chat model (must match GRIPPY_MODEL_ID)
ollama pull devstral-small-2-24b-instruct-2512

# Embedding model (must match GRIPPY_EMBEDDING_MODEL)
ollama pull text-embedding-qwen3-embedding-4b
```

Verify the server is running:

```bash
curl http://localhost:11434/v1/models
```

Ollama serves both chat and embedding models on the same port (11434).

### Option B: LM Studio

1. Download from [lmstudio.ai](https://lmstudio.ai)
2. Load a chat model (e.g., Devstral-Small-2512 24B at Q4+ quantization)
3. Load an embedding model alongside it (e.g., Qwen3-Embedding-4B)
4. Start the local server on port 1234 (**Settings > Local Server**)

Verify:

```bash
curl http://localhost:1234/v1/models
```

You should see both models listed in the response.

### Which model?

We recommend **Devstral-Small 24B at Q4 quantization or higher** --- that's what Grippy was validated with for local inference. It runs on consumer GPUs with 16GB+ VRAM and handles Grippy's structured output requirements well. For other options, see the [Model Recommendations](configuration.md#model-recommendations) section in the Configuration page.

---

## 2. Create a Cloudflare Tunnel

The tunnel connects your local model server to a public hostname without opening any ports on your network. Traffic flows through Cloudflare's edge network, encrypted end-to-end.

### Install cloudflared

**macOS:**

```bash
brew install cloudflare/cloudflare/cloudflared
```

**Linux (Debian/Ubuntu):**

```bash
curl -L https://pkg.cloudflare.com/cloudflare-main.gpg \
  | sudo tee /usr/share/keyrings/cloudflare-main.gpg > /dev/null
echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] \
  https://pkg.cloudflare.com/ $(lsb_release -cs) main" \
  | sudo tee /etc/apt/sources.list.d/cloudflare.list
sudo apt update && sudo apt install cloudflared
```

**Other platforms:** See [Cloudflare's download page](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/).

### Create the tunnel

```bash
cloudflared tunnel login
cloudflared tunnel create grippy-llm
```

The `login` command opens a browser for Cloudflare authentication. The `create` command generates a tunnel ID and credentials file.

### Configure the tunnel

Create or edit `~/.cloudflared/config.yml`:

```yaml
tunnel: <TUNNEL_ID>
credentials-file: /home/your-user/.cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: grippy-llm.yourdomain.com
    service: http://localhost:1234    # LM Studio (port 1234)
    # service: http://localhost:11434  # Ollama (port 11434)
  - service: http_status:404
```

Replace `<TUNNEL_ID>` with the ID printed by `cloudflared tunnel create`, and `yourdomain.com` with your Cloudflare-managed domain.

The catch-all `http_status:404` rule at the end is required by cloudflared. It rejects any request that doesn't match a hostname rule.

### Create the DNS route and start the tunnel

```bash
cloudflared tunnel route dns grippy-llm grippy-llm.yourdomain.com
cloudflared tunnel run grippy-llm
```

Verify the tunnel is working:

```bash
curl https://grippy-llm.yourdomain.com/v1/models
```

You should see the same model list as your local server. If this works, the tunnel is live. Stop here and set up access control before exposing it long-term.

---

## 3. Set Up Cloudflare Access (Zero Trust)

Without an access policy, anyone who discovers your tunnel URL can query your model. Cloudflare Access adds an authentication layer in front of the tunnel.

### Create a service token

1. Go to the [Cloudflare Zero Trust dashboard](https://one.dash.cloudflare.com)
2. Navigate to **Access > Service Auth > Service Tokens**
3. Click **Create Service Token**
4. Name it `grippy-github-action`
5. Save the **Client ID** and **Client Secret** --- the secret is only shown once

### Create an access application

1. In the Zero Trust dashboard, go to **Access > Applications**
2. Click **Add an application** and select **Self-hosted**
3. Set the application domain to `grippy-llm.yourdomain.com`
4. Under **Policies**, create a policy:
   - **Policy name:** `grippy-github-action`
   - **Action:** Service Auth
   - **Include rule:** Service Token --- select the token you created
5. Save the application

### Test the access policy

Without credentials, the request should be blocked:

```bash
curl https://grippy-llm.yourdomain.com/v1/models
# Should return a Cloudflare Access login page or 403
```

With credentials, it should work:

```bash
curl -H "CF-Access-Client-Id: <CLIENT_ID>" \
     -H "CF-Access-Client-Secret: <CLIENT_SECRET>" \
     https://grippy-llm.yourdomain.com/v1/models
```

If you see your model list, the access policy is working.

---

## 4. Configure GitHub Actions

### The auth challenge

Grippy uses the OpenAI Python SDK (via the Agno framework), which sends API keys as `Authorization: Bearer <key>`. Cloudflare Access expects `CF-Access-Client-Id` and `CF-Access-Client-Secret` as separate headers.

There are a few ways to bridge this gap:

- **Service token as Bearer:** Configure your Cloudflare Access policy to accept a service token passed as a Bearer token in the Authorization header
- **Access bypass with API key:** Create a bypass rule that accepts a specific API key, and set `GRIPPY_API_KEY` to that key
- **Cloudflare Worker proxy:** Place a Worker in front of the tunnel that maps the Bearer token to the two CF-Access headers

The simplest approach is configuring Access to accept the service token. Set `GRIPPY_API_KEY` to your service token secret and configure the policy accordingly.

### Add repository secrets

Go to **Settings > Secrets and variables > Actions** in your GitHub repository and add:

| Secret | Value |
|---|---|
| `CF_ACCESS_CLIENT_ID` | Your Cloudflare service token Client ID |
| `CF_ACCESS_CLIENT_SECRET` | Your Cloudflare service token Client Secret |

### Workflow configuration

Add the review step to your workflow (`.github/workflows/grippy-review.yml`):

```yaml
      - name: Install Grippy
        run: pip install "grippy-mcp"

      - name: Run Grippy review
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITHUB_EVENT_PATH: ${{ github.event_path }}
          GRIPPY_TRANSPORT: local
          GRIPPY_BASE_URL: https://grippy-llm.yourdomain.com/v1
          GRIPPY_API_KEY: ${{ secrets.CF_ACCESS_CLIENT_SECRET }}
          GRIPPY_MODEL_ID: devstral-small-2-24b-instruct-2512
          GRIPPY_EMBEDDING_MODEL: text-embedding-qwen3-embedding-4b
          GRIPPY_DATA_DIR: ./grippy-data
          GRIPPY_TIMEOUT: '300'
        run: python -m grippy
```

Key settings:

- `GRIPPY_TRANSPORT: local` tells Grippy to use the `OpenAILike` transport, which connects to `GRIPPY_BASE_URL` instead of the OpenAI API. Grippy also supports 5 other transports (`openai`, `anthropic`, `google`, `groq`, `mistral`) --- for cloud-hosted models, no tunnel is needed.
- `GRIPPY_BASE_URL` points to your tunnel hostname with the `/v1` path
- `GRIPPY_API_KEY` is your service token secret, passed as the Bearer token
- `GRIPPY_MODEL_ID` and `GRIPPY_EMBEDDING_MODEL` must match the model names served by your endpoint (check `/v1/models` output)
- `GRIPPY_TIMEOUT` is in seconds --- local models can be slower than cloud APIs, so adjust this based on your hardware

> **Tip:** For local-only use without CI, run Grippy as an MCP server instead: `grippy serve` or `uvx grippy-mcp serve`. The MCP server connects to the same local endpoint using the same environment variables.

For the full workflow file including checkout, Python setup, caching, and outputs, see the [Getting Started](../getting-started/quickstart.md) page.

---

## 5. Running as a Service

For always-on operation, run both the tunnel and the model server as system services.

### cloudflared

```bash
sudo cloudflared service install
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
```

This installs cloudflared as a systemd service using your existing `~/.cloudflared/config.yml`. The tunnel will start automatically on boot.

### Ollama

Ollama installs its own systemd service by default. Verify it's running:

```bash
sudo systemctl status ollama
```

If you need to enable it:

```bash
sudo systemctl enable ollama
sudo systemctl start ollama
```

### LM Studio

LM Studio doesn't ship a systemd service. You can create one at `/etc/systemd/system/lmstudio-server.service`:

```ini
[Unit]
Description=LM Studio Server
After=network.target

[Service]
Type=simple
User=your-user
ExecStart=/path/to/lms server start --port 1234
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then enable and start it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable lmstudio-server
sudo systemctl start lmstudio-server
```

Adjust the `ExecStart` path and `User` for your system. Check `which lms` to find the LM Studio CLI path.

---

## 6. Security Considerations

This setup gives you a zero-trust path from GitHub Actions to your local model:

- **Tunnel + Access policy** --- Only requests with a valid service token reach your model server. No ports are opened on your network.
- **Code stays local** --- The model runs on your hardware. Grippy runs on the GitHub Actions runner. Your source code is read by the runner (which already has repo access) and sent to your model through the tunnel. No third-party API sees your code.
- **Cloudflare sees encrypted tunnel traffic only** --- Cloudflare routes the connection but does not inspect the payload.
- **Rotate service tokens periodically** --- Delete and recreate the service token in the Zero Trust dashboard, then update the GitHub repository secret.
- **Monitor access** --- The Zero Trust dashboard logs every request through the tunnel. Check it for unexpected access patterns.
- **Consider container isolation** --- Run the model server in a container (Docker, Podman) to limit its access to the host system. This is especially relevant if you're running models from untrusted sources.

---

## 7. Troubleshooting

### Tunnel connection refused

The model server isn't running on the port specified in `config.yml`. Verify locally:

```bash
# LM Studio
curl http://localhost:1234/v1/models

# Ollama
curl http://localhost:11434/v1/models
```

If the local request works but the tunnel doesn't, check that `config.yml` points to the correct port and that `cloudflared tunnel run` is active.

### 403 Forbidden

The Cloudflare Access policy is blocking the request. Check:

- The service token hasn't expired
- The `CF-Access-Client-Id` and `CF-Access-Client-Secret` headers are correct
- The Access application's domain matches your tunnel hostname exactly
- The policy includes the correct service token

### Timeout in GitHub Actions

The model is too slow to complete the review within `GRIPPY_TIMEOUT` seconds. Options:

- Increase `GRIPPY_TIMEOUT` (e.g., `600` for 10 minutes)
- Use a faster model or upgrade your GPU
- Reduce the PR diff size by splitting large PRs

### Embedding errors

The embedding model isn't loaded or the model name doesn't match `GRIPPY_EMBEDDING_MODEL`. Check:

```bash
curl https://grippy-llm.yourdomain.com/v1/models
```

The response must include a model whose name matches the `GRIPPY_EMBEDDING_MODEL` value exactly.

### Model returns empty or malformed responses

Some models struggle with Grippy's structured output requirements. If you see repeated retries in the action logs, try a model with stronger instruction-following (Devstral-Small handles this well). Check the [Model Recommendations](configuration.md#model-recommendations) for tested options.

### DNS not resolving

If `grippy-llm.yourdomain.com` doesn't resolve, the DNS route may not have been created. Run:

```bash
cloudflared tunnel route dns grippy-llm grippy-llm.yourdomain.com
```

Then verify with `dig grippy-llm.yourdomain.com` or `nslookup grippy-llm.yourdomain.com`. The record should be a CNAME pointing to `<TUNNEL_ID>.cfargotunnel.com`.
