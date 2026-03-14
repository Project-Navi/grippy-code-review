<!-- SPDX-License-Identifier: MIT -->

# Audit Scorecard: rule-llm-sinks

**Audit date:** 2026-03-14
**Commit:** 8957771
**Auditor:** Claude Opus 4.6 (AI draft) / Nelson Spence (human reviewer)
**Unit type:** security-rule (primary)
**Subprofile:** N/A

---

## Gate Rules

### Override Gates (force a specific status)

| Override Gate | Condition | Fired? |
|---|---|---|
| Critical finding | Any unresolved CRITICAL finding | No |
| Multi-HIGH block | 2+ unresolved HIGH findings (including provisional) | No (0 HIGH findings) |
| Security collapse | Security Posture < 2 | No (score: 7) |
| Adversarial collapse | Adversarial Resilience < 2 | No (score: 6) |

### Ceiling Gates (cap the best allowed status)

| Ceiling Gate | Condition | Fired? |
|---|---|---|
| Severity cap | Any unresolved HIGH finding | No |
| Security hard floor | Security Posture < 4 | No (score: 7) |
| Adversarial hard floor | Adversarial Resilience < 4 | No (score: 6) |
| Security soft floor | Security Posture < 6 | No (score: 7) |
| Adversarial soft floor | Adversarial Resilience < 6 | No (score: 6) |
| Accepted critical risk | Any ACCEPTED_RISK at CRITICAL | No |
| Accepted high risk | Any ACCEPTED_RISK at HIGH | No |

---

## Summary

| Dimension | Score | Evidence Tier | Notes |
|-----------|------:|:---:|-------|
| 1. Contract Fidelity | 7/10 | A | All functions typed, mypy strict clean, RuleResult/RuleContext/DiffHunk used correctly |
| 2. Robustness | 6/10 | A + C | Forward-scan hunk analysis. `break` limits one finding per model-output→sink chain. No total bounds. |
| 3. Security Posture | 7/10 | C | No I/O, no secrets in findings. Evidence is sink line content (code, not credentials). |
| 4. Adversarial Resilience | 6/10 | A + C | ReDoS tests on all 3 patterns (Tier A). 1MB long-line tolerance (Tier A). No evasion fixtures. |
| 5. Auditability & Traceability | 6/10 | C | Findings include rule_id/file/line/evidence. Generic message -- no pattern specificity. |
| 6. Test Quality | 7/10 | A | 18 tests. Positive (5), negative (2), edge (1), metadata (2), adversarial (3), pattern coverage (4), sanitizer (1). |
| 7. Convention Adherence | 8/10 | A | ruff, mypy strict, bandit clean. SPDX header. Imports DiffHunk directly -- unusual but justified. |
| 8. Documentation Accuracy | 7/10 | C | Accurate docstrings. Inline comments on scan logic. SANITIZERS frozenset documented. |
| 9. Performance | 7/10 | C | Compiled regexes. Forward-scan is O(lines^2) per hunk -- acceptable for typical hunk sizes. |
| 10. Dead Code / Debt | 9/10 | A + C | Zero TODOs, all functions called, all patterns used. SANITIZERS exported for tests. |
| 11. Dependency Hygiene | 8/10 | A | 2 internal deps (rules.base, rules.context). Imports DiffHunk directly -- 3rd symbol from context module. |
| **Overall** | **7.1/10** | | **Average of 11 dimensions** |

**Health status:** Adequate (provisional)

**Determination:**
1. Average-based status: 7.1/10 falls in 6.0-7.9 range = Adequate
2. Override gates: None fired.
3. Ceiling gates: None fired. All gate dimensions >= 6.
4. Suffixes: `(provisional)` -- dims 2, 3, 5, 8, 9 include Tier C evidence components.

**Override gates fired:** None
**Ceiling gates fired:** None

---

## Checklist: SR-01 through SR-09

| ID | Verdict | Evidence | Notes |
|----|---------|----------|-------|
| SR-01 | PASS | Tier A: 5 positive tests cover model-output→sink detection: `test_direct_pipe_to_comment` (.run/.content→create_issue_comment), `test_completion_to_post` (.generate/completion→post), `test_choices_to_body` (.choices→.body=), plus 4 pattern coverage tests: `test_chat_to_comment` (.chat→create_issue_comment), `test_sink_create_comment` (.run→create_comment), `test_sink_render` (.generate→render), `test_sink_fstring_html` (.content→f"<"). 2 negative tests verify sanitizer suppression. | All 3 regexes exercised through end-to-end tests. |
| SR-02 | PASS | Tier A: 3 ReDoS tests. `test_redos_model_output_re` — 100K chars against `_MODEL_OUTPUT_RE` (word-boundary anchored alternation). `test_redos_sink_re` — 100K chars against `_SINK_RE` (word-boundary anchored alternation). `test_extremely_long_line` — >1MB line through full `rule.run()`. All complete under 5s timeout. `_SANITIZER_RE` is auto-generated from `re.escape()`d literals joined by `\|` — structurally cannot backtrack. | All patterns safe. |
| SR-03 | PASS | Tier A: `test_severity_is_error` asserts all findings have `RuleSeverity.ERROR`. Tier C: `default_severity = RuleSeverity.ERROR` (line 44). | ERROR severity. Gates on both security and strict-security profiles. |
| SR-04 | PASS | Tier C: `line.type == "add"` check at line 62 in `_scan_hunk()`. Only added lines with valid `new_lineno` are collected for analysis. Context and removed lines are skipped. | Uses direct iteration with explicit type check -- same convention as rule-ci-risk and rule-traversal. |
| SR-05 | PASS | Tier C: All `RuleResult` instances include `rule_id`, `severity`, `message`, `file`, `line`, `evidence=sink_content.strip()` (line 84). Evidence is the sink line content — not truncated (no `[:120]`). | Sufficient for human triage. No truncation is acceptable here because sink lines are typically short. |
| SR-06 | N/A | Ownership: engine-owned. Individual rule units do not own profile dispatch logic. | Per SR-06 scope note: "Mark N/A when auditing individual rule units." |
| SR-07 | PASS | Tier C: Evidence contains sink code (e.g., `pr.create_issue_comment(result.content)`), not secret values. Model output variable names are code references, not credentials. | No leakage risk. |
| SR-08 | PASS | Tier C: All findings use standard `RuleResult` dataclass. Fields compatible with `ResultEnrichment` post-processing. | Standard format. |
| SR-09 | Partial | Tier A: Positive (5 end-to-end + 4 pattern coverage = 9), negative (2 sanitizer suppression + 1 no-model-output = 3), edge (1 non-Python file), metadata (2: rule_id + severity + sanitizers frozenset), adversarial (3: 2 ReDoS + 1 long-line). Missing: multi-hunk scenarios, model output in different hunk than sink, renamed files. | See F-LLM-001. |

**N/A items:** 1/9 (SR-06 only). Well below the >50% reclassification threshold.

---

## Findings

### F-LLM-001: Fixture matrix missing cross-hunk and boundary scenarios

**Severity:** LOW
**Status:** OPEN
**Checklist:** SR-09
**Evidence tier:** C (manual review of test file)

**Description:** The fixture matrix has good positive coverage (9 tests covering all pattern combinations) and reasonable negative balance (3 suppression/safe tests). However, it lacks tests for:
- Cross-hunk scenarios: model output in one hunk, sink in another (current design scans per-hunk, so this would be a true negative -- worth proving)
- Forward-scan boundary: model output on last line of hunk with no subsequent lines
- Renamed/binary files

**Impact:** LOW -- The per-hunk scan design means cross-hunk model-output→sink chains are intentionally not detected. This is a known limitation of the hunk-level analysis approach (documented in the scan logic). Boundary and renamed-file cases are unlikely to produce false positives.

**Recommendation:** Add 1-2 boundary tests in a future batch to prove the per-hunk isolation is intentional and correct.

### Compound Chain Exposure

`None identified` -- rule-llm-sinks produces RuleResult findings consumed by the engine/enrichment layer. No I/O, no subprocess, no prompt composition. Unusual architecture (forward-scan hunk analysis) is self-contained.

---

## Dimension Details

### 1. Contract Fidelity

**Key question:** Do types, exports, and validation faithfully represent the unit's contract?

**Score:** 7/10
**Evidence:**
- mypy strict passes with zero issues (Tier A: static analysis).
- All functions fully typed: `run(self, ctx: RuleContext) -> list[RuleResult]`, `_scan_hunk(self, path: str, hunk: DiffHunk) -> list[RuleResult]` (Tier A: mypy proves this).
- Imports `DiffHunk` from `rules.context` — unusual for rules (most only import `RuleContext`), but type-correct and justified by the hunk-level analysis design.
- Rule follows duck-typed Rule protocol: exposes `id`, `description`, `default_severity`, `run()`.
- `SANITIZERS` frozenset exported as public API — used by test assertions (Tier A).
- Not 9: No explicit Protocol class. No runtime type checks.
- Calibration: matches rule-secrets (7), rule-sql (7), rule-traversal (7).

---

### 2. Robustness

**Key question:** Does the unit handle errors, retries, and edge cases correctly?

**Score:** 6/10
**Evidence:**
- Forward-scan design: `_scan_hunk()` collects added lines, then for each model-output line scans forward for sinks. `break` at line 87 limits to one finding per chain — prevents flooding.
- Empty hunk handled gracefully: `added_lines` list is empty, loop doesn't execute (Tier C).
- `line.type == "add"` and `line.new_lineno is not None` guard at line 62 — defensive (Tier C).
- >1MB line tolerance proven (Tier A: `test_extremely_long_line`).
- No bounds on total result count across all hunks.
- Not 7: No handling for pathologically large hunks (hundreds of model output tokens). Quadratic forward-scan acceptable for typical diffs.
- Calibration: matches rule-secrets (6), rule-sql (6), rule-traversal (6).

---

### 3. Security Posture

**Key question:** Does the unit protect against injection, leakage, and unauthorized access?

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 7/10
**Evidence:**
- No I/O, no network, no subprocess, no logging (Tier C: module-level inspection).
- Evidence field contains sink code lines, not secret values (Tier C: SR-07 analysis).
- Evidence NOT truncated (unlike rule-sql/rule-crypto). Acceptable: sink lines are typically short code statements.
- Uses direct hunk iteration with `line.type == "add"` — added-lines-only filtering (Tier C).
- `SANITIZERS` frozenset used for matching — immutable, no mutation risk (Tier C).
- Does not own trust boundaries.
- Not 9: Evidence not truncated could theoretically expose long lines. Single detection layer.
- Calibration: matches rule-secrets (7), rule-sql (7), rule-traversal (7).

---

### 4. Adversarial Resilience

**Key question:** Can the unit resist adversarial input from untrusted PR content and prompt injection?

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 6/10
**Evidence:**
- **ReDoS defense (Tier A):** 2 ReDoS tests exercise the 2 user-facing patterns (`_MODEL_OUTPUT_RE`, `_SINK_RE`). Both are word-boundary anchored alternations with no nested quantifiers — structurally safe. `_SANITIZER_RE` is auto-generated from `re.escape()`d literals joined by `|` — cannot backtrack. All complete under 5s timeout.
- **Large input tolerance (Tier A):** `test_extremely_long_line` proves >1MB lines processed without crash.
- Not 7: No adversarial evasion tests (e.g., Unicode model-output tokens, obfuscated sink names). No false-positive manipulation tests. ReDoS coverage is complete but narrow.
- Calibration: matches rule-sql (6), rule-workflows (6), rule-traversal (6). _SANITIZER_RE is structurally the safest pattern in the batch (escaped literals only).

---

### 5. Auditability & Traceability

**Key question:** Can operators investigate failures, reproduce review results, and trace the decision path from input to output?

**Score:** 6/10
**Evidence:**
- Each `RuleResult` includes `rule_id`, `severity`, `message`, `file`, `line`, `evidence` (Tier C: code inspection at lines 77-85).
- Message is generic: "LLM output used in sink without sanitization" — does not identify which model-output token or sink triggered (Tier C).
- Deterministic: same diff input → same findings output. Fully reproducible.
- `break` at line 87: first sink match wins per chain. Finding doesn't reveal which specific model-output line was the source.
- No logging — appropriate for a rule.
- Not 7: Generic message loses specificity. Forward-scan index not preserved in output.
- Calibration: matches rule-secrets (6), rule-sql (6), rule-traversal (6).

---

### 6. Test Quality

**Key question:** Do tests verify meaningful behavior with good coverage?

**Score:** 7/10
**Evidence:**
- **Test count:** 18 tests across 4 test classes (Tier A: test_grippy_rule_llm.py).
- **Source:test ratio:** 2.34:1 (211 LOC tests / 90 LOC source).
- **Fixture matrix categories covered:**
  - Positive: 5 end-to-end (direct pipe, sanitized, html.escape, completion→post, choices→body) + 4 pattern coverage = 9 total.
  - Negative: 3 tests (sanitized output, html.escape suppression, no model output present).
  - Edge: 1 test (non-Python file ignored).
  - Metadata: 2 tests (severity is ERROR, SANITIZERS frozenset contents).
  - Adversarial: 3 tests (2 ReDoS + 1 long-line).
- **Pattern coverage note:** 4 new tests in Commit 1 exercised untested pattern combinations (.chat, create_comment, render, fstring_html). Closes the SR-01 gap.
- Missing categories (F-LLM-001): cross-hunk scenarios, forward-scan boundary.
- Calibration: matches rule-sql (7: 15 tests), rule-workflows (7: 15 tests). Higher test count (18) with good category spread.

---

### 7. Convention Adherence

**Key question:** Does the unit follow Grippy project patterns?

**Score:** 8/10
**Evidence:**
- SPDX header present on source and test file (Tier A: file inspection).
- ruff check passes with zero issues (Tier A: static analysis).
- mypy strict passes with zero issues (Tier A: static analysis).
- bandit passes with zero issues (Tier A: static analysis).
- Test file follows mirror structure: `src/grippy/rules/llm_output_sinks.py` → `tests/test_grippy_rule_llm.py` (Tier A). Note: test file name uses abbreviated `llm` not `llm_output_sinks` — acceptable convention.
- Test file exceeds 50 LOC minimum (211 LOC) (Tier A).
- Uses `DiffHunk` import — **unusual**: most rules import only `RuleContext`. Justified by the hunk-level analysis design. Not a convention violation, but a divergence worth noting.
- Uses direct iteration with `line.type == "add"` — same as rule-ci-risk and rule-traversal.
- Not 9: DiffHunk direct import is a minor convention divergence. Test file name abbreviation.
- Calibration: slightly below rule-sql (9) due to import convention divergence. Matches convention adherence of units with justified divergences.

---

### 8. Documentation Accuracy

**Key question:** Do docstrings, comments, and docs match actual behavior?

**Score:** 7/10
**Evidence:**
- File-level docstring: "Rule 5: llm-output-unsanitized — detect LLM output piped to sinks without sanitization." (line 2) — accurate (Tier C).
- Class docstring: "Detect LLM output piped directly to sinks without sanitization." (line 40) — accurate (Tier C).
- `_scan_hunk` docstring: "Scan a single hunk for model output → sink without sanitizer." — accurate (Tier C).
- Comment "Central sanitizer registry — single source of truth" (line 11) — accurate, SANITIZERS is the canonical list (Tier C).
- Inline comments on scan logic: "Collect added lines in order", "Look for model output tokens, then scan forward for sinks", "Check if any sanitizer appears between model output and sink" (lines 59, 65, 74).
- Not 9: No documentation of the per-hunk isolation design decision. No usage examples.
- Calibration: matches rule-secrets (7), rule-sql (7).

---

### 9. Performance

**Key question:** Is the unit efficient for its workload?

**Score:** 7/10
**Evidence:**
- 3 regex patterns compiled once at module load via `re.compile()` (Tier C: lines 27-36). `_SANITIZER_RE` generated once from `SANITIZERS` frozenset.
- File extension check (`f.path.endswith(".py")`) at entry provides early exit for non-Python files (Tier C: line 49).
- Forward-scan is O(n^2) per hunk where n = added lines count. For typical PR hunks (10-50 added lines), this is negligible. For pathologically large hunks, could be slow — but PRs with 10K+ added lines in a single hunk are rare.
- `break` at line 87 short-circuits after first sink match per chain.
- `" ".join()` at line 75 creates intermediate string for sanitizer check — allocation per chain check.
- Not 8: O(n^2) scan is not linear. No profiling data.
- Calibration: slightly below rule-sql (8) due to O(n^2) scan design. Practical performance is acceptable.

---

### 10. Dead Code / Debt

**Key question:** Is the unit free of unused code and tracked debt?

**Score:** 9/10
**Evidence:**
- Zero `TODO` or `FIXME` comments (Tier A: grep search).
- All functions called: `LlmOutputSinksRule` registered in `RULE_REGISTRY`, `_scan_hunk` at line 52 (Tier C: caller trace).
- All 3 compiled patterns used: `_MODEL_OUTPUT_RE` at line 67, `_SINK_RE` at line 73, `_SANITIZER_RE` at line 76 (Tier C).
- `SANITIZERS` frozenset used both for `_SANITIZER_RE` generation and exported for test assertions (Tier C).
- ruff detects no unused imports (Tier A).
- Not 10: F-LLM-001 identifies fixture matrix gaps — not code debt, but tracked.
- Calibration: matches rule-secrets (9), rule-sql (9), rule-traversal (9).

---

### 11. Dependency Hygiene

**Key question:** Are unit boundaries clean with no circular or unnecessary deps?

**Score:** 8/10
**Evidence:**
- 2 internal dependencies: `grippy.rules.base` (RuleResult, RuleSeverity) and `grippy.rules.context` (DiffHunk, RuleContext). Both are same-phase (Phase 1) sibling modules (Tier A: import inspection at lines 8-9).
- 1 external dependency: `re` (stdlib) (Tier A: import inspection at line 6).
- No circular imports (Tier A: ruff check).
- Imports 3 symbols from context module (`DiffHunk`, `RuleContext`) vs the typical 1 (`RuleContext`). This is a wider dependency surface, but `DiffHunk` is a stable type from the same module — not a hygiene concern.
- Not 9: 3 symbols from context module is above the typical 1. Minor but notable.
- Calibration: slightly below rule-sql (9) due to wider import surface.
