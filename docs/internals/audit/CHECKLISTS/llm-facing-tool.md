# LLM-Facing Tool Checklist

**Applies to:** codebase

| ID | Invariant | Severity | Evidence Types | Automation |
|----|-----------|----------|---------------|------------|
| LT-01 | File read operations cannot access paths outside the repository root | HIGH | Test with `../`, absolute paths, prefix collision, null bytes | test |
| LT-02 | File search operations do not follow symbolic links outside the repository | HIGH | Symlink escape test | test |
| LT-03 | All tool outputs are sanitized before reaching the LLM context | HIGH | Trace tool return -> middleware -> LLM; verify no bypass path | manual + test |
| LT-04 | Result counts are bounded to prevent context flooding | MEDIUM | Test that results exceeding caps are truncated, not errored | test |
| LT-05 | Long-running tool operations have timeouts that fire inside the operation loop | MEDIUM | Timeout test with slow/large inputs | test |
| LT-06 | Tool error messages do not reveal filesystem structure or internal state | MEDIUM | Error path test; grep output for path patterns | test |
| LT-07 | User-provided regex patterns are validated before execution | LOW | Invalid regex test; verify graceful rejection | test |
| LT-08 | Tool functionality degrades gracefully when optional infrastructure is unavailable | LOW | Run tools without index; verify review completes | test |
