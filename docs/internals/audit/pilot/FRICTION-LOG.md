# Pilot Friction Log

**Framework version:** v1.0 (METHODOLOGY.md 2026-03-13)

| # | Unit | Artifact | Issue | Impact | Provisional Handling | Proposed Fix | Fix Class |
|---|------|----------|-------|--------|---------------------|-------------|-----------|
| 1 | rule-secrets | FINDINGS (SR-06) | SR-06 "Rule respects profile activation" is engine-level, not rule-level. Individual rules have no profile-awareness — the engine selects which rules to run. | Cannot evaluate SR-06 at rule unit scope. | Marked N/A with justification: "Profile activation is engine-level." | Clarify in security-rule checklist that SR-06 tests belong to rule-engine unit, or split into engine-vs-rule items. | Clarification |
| 2 | retry | CENSUS (B6.5) | RP-07, RP-08, RP-09 are N/A for retry — they're github-review and review.py responsibilities. 3/9 items inapplicable = 33%. | Reduces effective checklist to 6 items. Slightly inflates apparent coverage. | Evaluated 6 applicable items. Documented N/A justifications per item. | Consider splitting review-pipeline checklist into sub-checklists by unit scope (parsing, posting, orchestration). | Structural |
