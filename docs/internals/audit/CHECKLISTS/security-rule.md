# Security Rule Checklist

**Applies to:** rule-engine, rule-enrichment, rule-secrets, rule-workflows, rule-sinks, rule-traversal, rule-llm-sinks, rule-ci-risk, rule-sql, rule-crypto, rule-creds, rule-deser

| ID | Invariant | Severity | Evidence Types | Automation |
|----|-----------|----------|---------------|------------|
| SR-01 | Rule detects all patterns documented in its specification | HIGH | Positive fixture for each pattern + negative fixture for non-matches | test |
| SR-02 | No regex pattern is vulnerable to catastrophic backtracking | HIGH | Adversarial long-input test (100K+ chars) per pattern | test |
| SR-03 | Rule severity assignment matches profile gate thresholds | HIGH | Profile activation test + gate behavior test | test |
| SR-04 | Rule only fires on added lines, not removed or context lines | MEDIUM | Diff fixture with adds/removes/context; verify only adds match | test |
| SR-05 | Finding evidence preserves enough context for human triage | MEDIUM | Inspect finding output for rule_id, file, line, evidence fields | manual |
| SR-06 | Rule respects profile activation (`general` = disabled) | MEDIUM | Profile-gated test fixture | test |
| SR-07 | Finding messages never contain raw secret values | LOW | Grep finding messages for credential patterns | test |
| SR-08 | Findings are compatible with enrichment post-processing | LOW | Integration test through `enrich_results()` | test |
| SR-09 | Fixture matrix covers: positive, negative, adversarial input, renamed/binary/submodule diffs, suppression by `.grippyignore` and `# nogrip` | MEDIUM | Test file review -- each category represented | manual |
