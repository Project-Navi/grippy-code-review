# LLM Agent Checklist

**Applies to:** agent, prompts, mcp-server (secondary)

| ID | Invariant | Severity | Evidence Types | Automation |
|----|-----------|----------|---------------|------------|
| LA-01 | All untrusted PR-derived content is sanitized before prompt insertion | HIGH | Trace all PR metadata fields (title, body, author, branch, diff, comments) to prompt insertion points; verify sanitizer covers each | manual + test |
| LA-02 | A data fence boundary separates instructions from untrusted content | HIGH | Read prompt composition; verify fence preamble exists before PR content | manual |
| LA-03 | Prior LLM responses are not included in subsequent prompts | HIGH | Verify session history is disabled in agent configuration | manual |
| LA-04 | Provider registry covers all supported transports with explicit failure modes | MEDIUM | Provider construction test per transport; verify unsupported transport raises clear error | test |
| LA-05 | Identity prompts (constitution, persona) load before mode-specific instructions and cannot be overridden | MEDIUM | Prompt chain order test; verify identity layer is first | test |
| LA-06 | Only audited tool classes are attached to the agent | MEDIUM | Enumerate attached tools; verify against allowed list | manual |
| LA-07 | Structured output configuration is correct for each provider's capabilities | MEDIUM | Provider-specific output test; verify no schema sent to non-supporting providers | test |
| LA-08 | Each review mode loads the correct prompt subset | LOW | Mode-prompt mapping test per mode | test |
