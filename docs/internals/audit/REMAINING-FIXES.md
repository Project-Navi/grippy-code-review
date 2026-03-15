# Remaining Fixes Register — Grippy

**Date:** 2026-03-15
**Source:** 30 scorecards + 3 pilot FINDINGS.md files
**Total open findings:** 26 (1 HIGH, 2 MEDIUM, 23 LOW)
**Total resolved findings:** 6 (1 HIGH, 1 MEDIUM, 4 LOW)

This register organizes the 26 open findings into governance buckets for prioritized remediation. Each finding's severity, unit, and description are derived from the source scorecards and pilot FINDINGS.md files.

---

## Bucket 1: Open Code / Behavior Defects

Findings where current code behavior is incorrect. These are bugs, not test gaps.

| Finding | Severity | Unit | Description | Effort |
|---|---|---|---|---|
| F-CLI-01 | LOW | cli | Silent fallback to `"local"` transport on invalid interactive input — user gets no error feedback | ~10 LOC |
| F-CB-001 | LOW | codebase | `grep_code` output and error messages expose absolute repo root path in tool responses | ~5 LOC |
| F-GS-001 | LOW | graph-store | WAL mode and foreign key pragma failures logged at `WARNING` instead of `ERROR` — silent degradation | ~5 LOC |

**Total:** 3 findings, all LOW. Estimated effort: ~20 LOC across 3 source files.

**Priority:** Low. None of these defects affect security boundaries or data integrity. F-CB-001 is the most notable because it leaks path information to the LLM through tool responses, but the `sanitize_tool_hook` middleware truncates and sanitizes tool output before it reaches the LLM context.

---

## Bucket 2: Open Assurance / Test Gaps

Findings where code is believed correct but proof is missing. The gap is in tests or verification, not runtime behavior.

| Finding | Severity | Unit | Description | Effort |
|---|---|---|---|---|
| F-RY-001 | **HIGH** | retry | `_validate_rule_coverage()` file-set validation branch (retry.py:102-105) has zero test coverage. TB-8 anchor. Anti-hallucination defense in production but unproven by tests. | ~10 LOC |
| F-RS-001 | MEDIUM | rule-secrets | No adversarial/ReDoS test coverage for 10 regex patterns. Manual analysis shows patterns are structurally safe, but no Tier A evidence exists. | ~15 LOC |
| F-ENR-001 | MEDIUM | rule-enrichment | No adversarial tests for crafted import paths in graph-derived enrichment. Blast radius and recurrence scoring process data from codebase indexing. | ~15 LOC |
| F-CB-002 | LOW | codebase | No property-based testing for path traversal defense. `Path.is_relative_to()` guard exists but no adversarial path corpus. KRC-01 instance elevated due to TB-4 anchor. | ~20 LOC |
| F-PR-002 | LOW | prompts | `context-builder.md` labels PR metadata as untrusted but graph-derived `file_context` as trusted. Graph content originates from codebase indexing, which is not fully adversarial-tested. | ~5 LOC |

**Total:** 5 findings (1 HIGH, 2 MEDIUM, 2 LOW). Estimated effort: ~65 LOC across 5 test files.

**Priority:** F-RY-001 is the only gate-firing finding in the codebase. It should be the first remediation target. F-RS-001 and F-ENR-001 are the next priority — both target code paths that process untrusted input adjacent to trust boundaries.

---

## Bucket 3: Known Recurring Class (KRC-01) — Fixture Matrix Gaps

Batch-addressable fixture matrix gaps. Each instance needs 1-2 tests adding a missing fixture category (adversarial, edge, negative, or renamed/binary diff format).

| Finding | Unit | Gap | Effort |
|---|---|---|---|
| F-SCH-002 | schema | No test for missing required field rejection on `GrippyReview` | ~5 LOC |
| F-RS-002 | rule-secrets | Missing adversarial input, renamed/binary diff categories | ~10 LOC |
| F-SNK-001 | rule-sinks | Positive-heavy fixture matrix, missing negative/edge categories | ~10 LOC |
| F-RW-001 | rule-workflows | Positive-heavy fixture matrix, missing negative/edge categories | ~10 LOC |
| F-TRV-001 | rule-traversal | Positive-heavy fixture matrix, missing negative/edge categories | ~10 LOC |
| F-LLM-001 | rule-llm-sinks | Positive-heavy fixture matrix, missing negative/edge categories | ~10 LOC |
| F-CIR-001 | rule-ci-risk | Positive-heavy fixture matrix, missing negative/edge categories | ~10 LOC |
| F-SQL-001 | rule-sql | Positive-heavy fixture matrix, missing negative/edge categories | ~10 LOC |
| F-CRY-001 | rule-crypto | Positive-heavy fixture matrix, missing negative/edge categories | ~10 LOC |
| F-DSR-001 | rule-deser | Positive-heavy fixture matrix, missing negative/edge categories | ~10 LOC |
| KRC-01 | graph-store | Missing edge-case fixture categories | ~10 LOC |
| KRC-01 | graph-context | Missing edge-case fixture categories | ~10 LOC |
| F-PR-001 | prompts | No adversarial test fixtures | ~10 LOC |

**Total:** 13 instances, all LOW. Estimated effort: ~125 LOC across ~13 test files.

**Priority:** Low individually, moderate collectively. Best addressed as a single batch PR adding 1-2 tests per instance. The batch should be organized by test file rather than by finding — many rule test files share identical patterns (`_make_diff()` helper, `_ctx()` fixture factory).

---

## Bucket 4: Accepted Design Choices / No Action

Findings documented for audit completeness where current behavior is intentional. No code change planned.

| Finding | Unit | Rationale |
|---|---|---|
| F-SCH-001 | schema | Only `Finding` model is frozen; other 10 mutable. Intentional — `GrippyReview` is constructed incrementally during pipeline execution. |
| F-SCH-003 | schema | `Finding.id` and `Escalation.id` use bare `str` without pattern constraint. Intentional — strict patterns cause retry loops on cosmetically non-conformant but semantically valid LLM output. |
| F-EMB-001 | embedder | Passthrough params (`dimensions`, `encoding_format`) consumed by OpenAI SDK, not user-facing. |
| F-RS-003 | rule-secrets | `_is_comment_line()` misses HTML/CSS/Lua comment syntax. Acceptable — comment-line secrets are still worth flagging in most cases. |
| F-RY-002 | retry | `import warnings` lazy inside function body. Style choice for rarely-hit code path. ruff does not flag. |

**Total:** 5 findings, all LOW. No action required.

**Note:** These findings retain OPEN status in the source scorecards/FINDINGS.md. They are not formally ACCEPTED_RISK (which would require sign-off and a review date per methodology Section E). They are design observations where the finding text itself documents why no action is recommended.
