# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in Grippy, **please report it privately** rather than opening a public issue.

**Email:** security@project-navi.dev

**GitHub:** Use [GitHub's private vulnerability reporting](https://github.com/Project-Navi/grippy-code-review/security/advisories/new) to submit a report directly on this repository.

Please include:

- Description of the vulnerability
- Steps to reproduce
- Impact assessment (what an attacker could do)
- Affected version(s)

## Response Timeline

| Stage | Target |
|-------|--------|
| Acknowledgment | 48 hours |
| Initial assessment | 5 business days |
| Fix or mitigation | 30 days for critical, 90 days for others |

## Scope

The following are in scope:

- **Prompt injection** — bypassing Grippy's input sanitization to manipulate LLM behavior
- **Output sanitization bypass** — getting unsanitized LLM content posted to GitHub PRs
- **Codebase tool exploitation** — path traversal, symlink following, or data exfiltration via `read_file`, `grep_code`, `list_files`
- **MCP server** — unauthorized access, scope parameter injection, subprocess escape
- **Supply chain** — compromised dependencies, CI workflow manipulation
- **Information leakage** — internal paths, stack traces, or secrets exposed in PR comments

The following are **out of scope**:

- LLM hallucinations (incorrect findings) — these are a quality issue, not a security issue
- Personality/tone of review comments
- Findings in the adversarial test suite (`tests/test_hostile_environment.py`) that are already tested and passing

## Security Architecture

Grippy operates in an adversarial environment — PR diffs are untrusted input. See the [Security Model](https://github.com/Project-Navi/grippy-code-review/wiki/Security-Model) wiki page for the full threat model, including:

- 5-stage output sanitization pipeline
- Prompt injection defense (XML escaping, NL pattern neutralization, data-fence boundaries)
- Codebase tool protections (path traversal, symlink, timeout, result caps)
- 44-test adversarial test suite across 9 attack domains

## Supply Chain Security

- All GitHub Actions are **SHA-pinned** (no tag references)
- Releases use **OIDC trusted publishing** to PyPI (no stored credentials)
- **SLSA Level 3** build provenance attestations on every release
- **SBOM** generated in both CycloneDX and SPDX formats
- **OpenSSF Scorecard** monitored continuously
