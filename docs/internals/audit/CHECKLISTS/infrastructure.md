# Infrastructure Checklist

**Applies to:** ignore, imports, embedder, local-diff, graph-store, graph-context, mcp-config, mcp-response, mcp-server, cli

## Shared Items (All Subprofiles)

| ID | Invariant | Severity | Evidence Types | Automation |
|----|-----------|----------|---------------|------------|
| IN-01 | Missing configuration (API keys, endpoints) produces a clear error, not a cryptic traceback | MEDIUM | Missing-config test; verify error message quality | test |
| IN-02 | Unit follows project conventions (SPDX, naming, typing) | LOW | ruff + mypy check | CI |

## Config Subprofile (ignore, imports, embedder, graph-context, mcp-config, mcp-response)

| ID | Invariant | Severity | Evidence Types | Automation |
|----|-----------|----------|---------------|------------|
| IN-C01 | Edge case inputs (empty files, malformed patterns, unicode filenames) are handled gracefully | MEDIUM | Edge case test fixtures | test |
| IN-C02 | AST/parsing operations do not crash on malformed input | LOW | Malformed-file test; verify graceful handling | test |

## State Subprofile (graph-store)

| ID | Invariant | Severity | Evidence Types | Automation |
|----|-----------|----------|---------------|------------|
| IN-S01 | File-based state (SQLite) handles concurrent access safely | MEDIUM | Verify WAL mode or equivalent; concurrent access test | test |
| IN-S02 | Schema migrations do not lose data or corrupt state | MEDIUM | Migration test with populated database | test |
| IN-S03 | State operations are idempotent where possible | LOW | Repeated-operation test | test |

## Boundary Subprofile (local-diff, mcp-server, cli)

| ID | Invariant | Severity | Evidence Types | Automation |
|----|-----------|----------|---------------|------------|
| IN-B01 | Subprocess invocations use list arguments with timeout, never shell interpolation | HIGH | Code path trace of all subprocess calls; verify no `shell=True`, no f-string commands | manual + test |
| IN-B02 | CLI dispatch routes valid subcommands correctly and produces helpful errors for invalid ones | MEDIUM | Subcommand routing test; unknown command test | test |
| IN-B03 | MCP client detection handles all supported clients and fails explicitly for unsupported ones | MEDIUM | Client detection test per supported client | test |
| IN-B04 | External system timeouts are enforced and produce clean errors | MEDIUM | Timeout test | test |
