# Review Pipeline Checklist

**Applies to:** retry, github-review, review

| ID | Invariant | Severity | Scope | Evidence Types | Automation |
|----|-----------|----------|-------|---------------|------------|
| RP-01 | Error paths produce distinguishable error states, not values that look like success | HIGH | all | Trace error paths; verify no empty-review or default-score returns | manual + test |
| RP-02 | All LLM-generated text is sanitized before posting to external APIs | HIGH | github-review, review | Trace LLM output -> sanitization -> posting; verify pipeline completeness | manual + test |
| RP-03 | LLM output is validated against deterministic rule findings -- hallucinated or missing findings are caught | HIGH | retry | Rule coverage validation test with injected hallucinations and omissions | test |
| RP-04 | Retry error messages do not echo untrusted PR content back to the LLM | HIGH | retry | Validation error test; verify raw field values stripped | test |
| RP-05 | Deterministic rules run on the full diff; the LLM sees a truncated diff | MEDIUM | review | Verify rule execution precedes truncation in pipeline | manual |
| RP-06 | JSON parsing handles multiple response formats without crashing | MEDIUM | retry | Parse test with raw JSON, dict, markdown-fenced JSON, malformed JSON | test |
| RP-07 | Repeated reviews of the same PR do not accumulate duplicate comments | MEDIUM | github-review | Thread lifecycle test; verify stale resolution | test |
| RP-08 | CI pipeline correctly sets exit code and Actions outputs on all verdict paths | LOW | review | Gate behavior test per verdict | test |
| RP-09 | Review timeout is enforced and produces a clean exit, not a hang | LOW | review | Timeout test | test |
