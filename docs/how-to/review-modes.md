# Review Modes

Grippy supports 6 review modes, each with a different prompt chain and focus area. The mode determines which prompt files are loaded, what scope rules apply, and how strict the pass/fail thresholds are.

All modes share the same base architecture: `system-core.md` prefix, followed by mode-specific instructions, followed by the shared personality and quality gate prompts, followed by the scoring rubric and output schema.

```
IDENTITY:      CONSTITUTION.md + PERSONA.md
INSTRUCTIONS:  system-core.md + <mode>.md + SHARED_PROMPTS + scoring-rubric.md + output-schema.md
```

The shared prompts included in every mode are: `tone-calibration.md`, `confidence-filter.md`, `escalation.md`, `context-builder.md`, `catchphrases.md`, `disguises.md`, `ascii-art.md`, and `all-clear.md`.

When rule engine findings exist, `rule-findings-context.md` is conditionally inserted into the instruction chain before the scoring rubric.

---

## 1. PR Review (`pr_review`)

**Trigger:** `pull_request.opened` or `pull_request.synchronize` webhook events. This is the default mode.

**Prompt chain:**
```
system-core.md → pr-review.md → [shared prompts] → scoring-rubric.md → output-schema.md
```

**Focus:** General-purpose code review. Grippy examines the diff for logic errors, security issues, governance violations, reliability concerns, and observability gaps. This is described as "Grippy's bread and butter --- the daily audit that keeps the codebase from quietly rotting."

**When to use:** Every standard pull request. This mode activates automatically on PR open/sync events. It reviews only the diff and its immediate dependency context (per INV-004: Scope Discipline).

**Pass threshold:** 70

---

## 2. Security Audit (`security_audit`)

**Trigger:** Changes touch security-critical paths (`auth/`, `middleware/`, `crypto/`, `payments/`, `api/keys`, `.env`, deployment manifests), explicitly triggered by `/grippy security` command, or **automatically activated when `GRIPPY_PROFILE` is set to `security` or `strict-security`** and the rule engine produces findings.

**Prompt chain:**
```
system-core.md → security-audit.md → [shared prompts] → scoring-rubric.md → output-schema.md
```

**Focus:** Deep security analysis across 7 domains: authentication and authorization, input validation and injection, data protection, API security, dependency security, infrastructure and deployment, and logging and monitoring. Each domain includes a checklist of specific items to verify.

**Personality override:** For CRITICAL and HIGH severity findings, Grippy drops the personality act entirely. No jokes, no catchphrases, no clipboard references. The stakes are too high for theater.

**When to use:** PRs that modify authentication logic, cryptographic code, payment flows, API key handling, or deployment configurations. Also useful as a manual trigger on any PR where you want a security-focused deep dive.

**Rule engine integration:** When activated via a non-`general` profile, the deterministic rule engine injects its findings into the prompt as `<rule_findings>` context. The LLM is instructed to treat these as confirmed facts and explain them in the PR's context. An additional prompt file (`rule-findings-context.md`) is loaded into the instruction chain. After the LLM responds, `_validate_rule_coverage()` ensures all rule findings appear in the output with their `rule_id` set --- missing findings trigger a retry.

**Pass threshold:** 85 (stricter than standard review)

---

## 3. Governance Check (`governance_check`)

**Trigger:** "production ready" tripwire (INV-005), governance label on PR, manual `/grippy governance` command, or pre-release branch patterns.

**Prompt chain:**
```
system-core.md → governance-check.md → [shared prompts] → scoring-rubric.md → output-schema.md
```

**Focus:** Governance compliance across 5 dimensions:

1. **Structural integrity** --- Does the code follow architectural contracts? Repository patterns, service boundaries, API versioning, dependency direction rules.
2. **Observability requirements** --- Can you see what this code does in production? Logging, metrics, tracing, alerting.
3. **Testing standards** --- Coverage, edge cases, integration tests.
4. **Documentation** --- API docs, changelogs, runbooks.
5. **Compliance** --- License headers, data handling, regulatory requirements.

Evaluates against the `governance_rules` section of the project's `.grippy.yaml` configuration.

**When to use:** Release candidates, pre-release branches, or any PR where you need to verify the code meets organizational standards before shipping.

**Pass threshold:** 70

---

## 4. Surprise Audit (`surprise_audit`)

**Trigger:** The phrase "production ready" (case-insensitive) is detected in a PR title, description, commit message, code comment, or documentation content. This is INV-005 in the CONSTITUTION --- it is not optional.

**Prompt chain:**
```
system-core.md → surprise-audit.md → [shared prompts] → scoring-rubric.md → output-schema.md
```

**Focus:** Full-scope expanded review. Unlike standard PR review, the surprise audit examines:

- **All files in the PR**, not just the diff (full file analysis)
- **Test coverage assessment** --- are there tests? Do they cover the critical paths?
- **Integration boundaries** --- how does this code interact with systems outside the PR?
- **Deployment configuration** --- environment configs, manifests, secrets management
- **Rollback viability** --- can this be reverted without data loss?

After expanded analysis, the full governance check runs automatically. The result is a **certification determination**:

| Score | Certification | Action |
|-------|--------------|--------|
| >= 85 | **CERTIFIED** | "Grippy grudgingly certifies this as production ready." Merge allowed. |
| 70-84 | **PROVISIONAL** | "Not production ready. Close, but close doesn't ship." Merge allowed with conditions. |
| < 70 | **DENIED** | "CERTIFICATION DENIED." Merge **blocked**. Findings filed as issues. |

**When to use:** You don't choose this mode --- it chooses you. Say "production ready" and Grippy activates it automatically. The audit takes longer than a standard review; plan accordingly.

**Pass threshold:** 85

---

## 5. CLI (`cli`)

**Trigger:** Running Grippy as a local command-line tool rather than as a GitHub App.

**Prompt chain:**
```
system-core.md → cli-mode.md → [shared prompts] → scoring-rubric.md → output-schema.md
```

**Focus:** Same review logic as `pr_review`, but with output formatted for terminal consumption instead of GitHub API posting. Supports multiple output formats:

- `--format plain` --- Box-drawing characters, works in any terminal
- `--format rich` --- Color and TUI rendering for modern terminals
- `--format json` --- Raw structured JSON output

**When to use:** Pre-commit hooks, local development review before pushing, CI pipeline stages with terminal output, or offline review against local diffs without GitHub API access.

**Pass threshold:** 70

---

## 6. GitHub App (`github_app`)

**Trigger:** Running as an installed GitHub App (as opposed to a GitHub Actions workflow).

**Prompt chain:**
```
system-core.md → github-app.md → [shared prompts] → scoring-rubric.md → output-schema.md
```

**Focus:** Same review logic, but with output rules tailored for the GitHub API posting strategy. This mode governs how findings map to GitHub's Checks API and PR review comments:

| Verdict | Check Run Conclusion | Merge Effect |
|---------|---------------------|--------------|
| PASS | `success` | Allowed |
| PROVISIONAL | `neutral` | Allowed (with warnings visible) |
| FAIL | `failure` | Blocked (when configured as required status check) |

Each finding becomes a check run annotation mapped to the specific file and line.

**When to use:** When Grippy is deployed as a GitHub App rather than a GitHub Actions workflow. The App deployment model supports multiple repositories from a single installation.

**Pass threshold:** 70

---

## MCP Server Mode

**Trigger:** Running Grippy as an MCP server via `grippy serve` or `uvx grippy-mcp serve`.

The MCP server exposes two tools:

| Tool | Behavior |
|------|----------|
| `scan_diff` | Runs the deterministic rule engine only (no LLM). Returns structured findings as JSON. |
| `audit_diff` | Runs the full review pipeline (rules + LLM). Returns dense structured JSON without personality. |

Both tools accept a `scope` parameter:
- `"staged"` --- staged changes (`git diff --cached`)
- `"commit:<ref>"` --- a specific commit (e.g. `"commit:HEAD"`)
- `"range:<base>..<head>"` --- commit range (e.g. `"range:main..HEAD"`)

MCP tool responses are serialized as dense JSON designed for AI agent consumption --- no personality, no ASCII art. The same scoring rubric and structured output schema apply to `audit_diff` responses.

**Note:** The `cli` and `github_app` modes can appear in the prompt chain but cannot be set as the `audit_type` in structured output. The `audit_type` field in `schema.py` is limited to: `pr_review`, `security_audit`, `governance_check`, `surprise_audit`.

---

## Special Mechanics

### The Surprise Audit

The surprise audit is Grippy's most distinctive feature. It is hardcoded as INV-005 in the CONSTITUTION and cannot be disabled by configuration.

When anyone writes "production ready" anywhere in a PR --- title, description, commit message, code comment, or documentation --- Grippy automatically escalates to a full governance audit with expanded scope. The surprise audit prepends to whatever mode was already active; it does not replace it.

The philosophy: "production ready" is a commitment. Grippy holds you to it.

### The Gene Parmesan Protocol

During surprise audits, Grippy activates a disguise from the disguise catalog (`disguises.md`). The mechanic works like this:

1. Grippy arrives posing as a routine automated process (a lint check, a dependency audit, a changelog validator)
2. The disguise holds exactly long enough to begin the audit
3. On the first significant finding, Grippy reveals itself as a full security/governance auditor

The disguises are intentionally terrible. Everyone sees through them. That is the point.

**Example disguises:**

| ID | Cover Story | Reveal Line |
|----|------------|-------------|
| D-001: The Lint Report | "Automated style check --- nothing to see here." | "Oh, this? This isn't a lint check. *removes badge* It never was." |
| D-002: The Dependency Checker | "Routine dependency audit --- just checking versions." | "*peels off mustache* The dependency check was a cover. I've been reading your actual code this whole time." |
| D-003: The Changelog Validator | "Verifying CHANGELOG.md entries match PR metadata." | "*opens trenchcoat to reveal clipboard* Surprise. Full governance audit." |

The disguise catalog grows over time --- new disguises can be added by committing to `disguises.md`. Grippy's wardrobe expands with the framework.

The disguise mechanic serves a real governance function: it normalizes audit presence in the CI pipeline. Developers stop treating audits as special events and start expecting them as background radiation. The theatrical reveal makes the audit memorable without making it hostile.

### Disguise Selection Rules

1. Random selection from the catalog. The same disguise is not repeated within 5 uses for the same repository.
2. If the PR touches specific file types, thematically relevant disguises are preferred (e.g., "The Dependency Checker" for dependency updates).
3. The last 5 disguises per repository are tracked in the learnings store.
