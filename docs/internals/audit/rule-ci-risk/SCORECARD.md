<!-- SPDX-License-Identifier: MIT -->

# Audit Scorecard: rule-ci-risk

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
| 1. Contract Fidelity | 7/10 | A | All functions typed, mypy strict clean, RuleResult/RuleContext used correctly |
| 2. Robustness | 6/10 | A + C | Mixed-severity cascade (CRITICAL/WARN). `continue` prevents multi-match. No total bounds. |
| 3. Security Posture | 7/10 | C | No I/O, no secrets in findings. Evidence is CI/shell commands. |
| 4. Adversarial Resilience | 6/10 | A + C | ReDoS test on `_PIPE_EXEC_RE` with `.*` (Tier A). 1MB long-line tolerance (Tier A). |
| 5. Auditability & Traceability | 7/10 | C | Findings include pattern-specific messages ("Remote script piped to shell", "sudo usage", "chmod +x"). |
| 6. Test Quality | 7/10 | A | 15 tests. Positive (8), negative (1), edge (1), context (1), adversarial (2), safe-negatives (2). |
| 7. Convention Adherence | 9/10 | A | ruff, mypy strict, bandit clean. SPDX header. Direct iteration (same as rule-traversal). |
| 8. Documentation Accuracy | 7/10 | C | Accurate docstrings. Inline comments on severity levels. |
| 9. Performance | 8/10 | C | Compiled regexes, linear scan, `continue` short-circuit per pattern priority. Early `_is_ci_file` exit. |
| 10. Dead Code / Debt | 9/10 | A + C | Zero TODOs, all functions called, all patterns used. |
| 11. Dependency Hygiene | 9/10 | A | 2 internal deps (rules.base, rules.context) -- same phase. No circular deps. |
| **Overall** | **7.5/10** | | **Average of 11 dimensions** |

**Health status:** Adequate (provisional)

**Determination:**
1. Average-based status: 7.5/10 falls in 6.0-7.9 range = Adequate
2. Override gates: None fired.
3. Ceiling gates: None fired. All gate dimensions >= 6.
4. Suffixes: `(provisional)` -- dims 2, 3, 5, 8, 9 include Tier C evidence components.

**Override gates fired:** None
**Ceiling gates fired:** None

---

## Checklist: SR-01 through SR-09

| ID | Verdict | Evidence | Notes |
|----|---------|----------|-------|
| SR-01 | PASS | Tier A: 8 positive tests cover all 3 patterns across all file types: `test_curl_pipe_bash` (curl\|bash in workflow), `test_wget_pipe_sh` (wget\|sh in workflow), `test_sudo_in_workflow` (sudo in workflow), `test_chmod_x` (chmod+x in script), `test_dockerfile` (curl\|bash in Dockerfile), `test_makefile` (sudo in Makefile), `test_shell_script` (curl\|bash in .sh), `test_bash_extension` (sudo in .bash). All 3 regexes exercised across 5 file type categories. | Comprehensive file-type × pattern matrix. |
| SR-02 | PASS | Tier A: `test_redos_pipe_exec_re` — 100K-char adversarial input against `_PIPE_EXEC_RE` (the only pattern with `.*` quantifier: `\b(?:curl\|wget)\b.*\|\s*(?:ba)?sh\b`). Input has `curl` prefix but no trailing `\| sh`, forcing `.*` to scan the entire 100K-char string before failing. Completes under 5s timeout. `_SUDO_RE` (`\bsudo\b`) and `_CHMOD_X_RE` (`\bchmod\s+\+x\b`) are structurally safe — word-boundary anchored with no quantifiers beyond `\s+`. `test_extremely_long_line` — >1MB line through full `rule.run()`. | Primary target (`_PIPE_EXEC_RE` with `.*`) passes. Other patterns structurally safe. |
| SR-03 | PASS | Tier A: `test_curl_pipe_bash` asserts `r.severity == RuleSeverity.CRITICAL`. `test_sudo_in_workflow` asserts `r.severity == RuleSeverity.WARN`. Tier C: Mixed severity by pattern — curl\|bash is CRITICAL (line 69), sudo is WARN (line 83), chmod+x is WARN (line 98). `default_severity = RuleSeverity.WARN` (line 51) but overridden to CRITICAL for pipe execution. | Mixed-severity design: supply chain risk (CRITICAL) vs privilege escalation (WARN). |
| SR-04 | PASS | Tier C: `line.type != "add"` check at line 60 plus `line.new_lineno is None` guard. Direct iteration with explicit type check. `test_context_line_not_flagged` (Tier A) proves context lines with pipe patterns are NOT flagged. | Direct iteration — same convention as rule-traversal and rule-llm-sinks. |
| SR-05 | PASS | Tier C: All `RuleResult` instances include `rule_id`, `severity`, `message`, `file`, `line`, `evidence=content.strip()` (lines 67-103). Evidence not truncated. Pattern-specific messages: "Remote script piped to shell — supply chain risk", "sudo usage in CI context", "chmod +x in CI context — verify target script". | Messages are pattern-specific — better traceability than most rules. |
| SR-06 | N/A | Ownership: engine-owned. Individual rule units do not own profile dispatch logic. | Per SR-06 scope note. |
| SR-07 | PASS | Tier C: Evidence contains CI/shell commands (e.g., `curl -sSL https://example.com/install.sh \| bash`), not secret values. URLs in evidence are from CI scripts, not credentials. | No leakage risk. |
| SR-08 | PASS | Tier C: All findings use standard `RuleResult` dataclass. Fields compatible with `ResultEnrichment` post-processing. | Standard format. |
| SR-09 | Partial | Tier A: Positive (8 tests across 5 file types × 3 patterns), negative (1 non-CI file), edge (1 context-line), adversarial (2: ReDoS + long-line), safe-negatives (2: curl-without-pipe, pseudo-sudo). Missing: multi-line shell commands (heredocs), nested Dockerfiles (COPY from stage), `.gitlab-ci.yml` patterns. | See F-CIR-001. Safe-negatives anchor specificity well. |

**N/A items:** 1/9 (SR-06 only). Well below the >50% reclassification threshold.

---

## Findings

### F-CIR-001: Fixture matrix missing multi-line and alternate CI formats

**Severity:** LOW
**Status:** OPEN
**Checklist:** SR-09
**Evidence tier:** C (manual review of test and source files)

**Description:** The fixture matrix has strong positive coverage (8 tests covering all pattern × file-type combinations) and good safe-negative specificity (curl-without-pipe, pseudo-sudo). However, it lacks tests for:
- Multi-line shell commands: heredocs in workflows where `curl` and `| sh` are on different lines (rule scans per-line — this would be a true negative worth proving)
- Alternative CI formats: `.gitlab-ci.yml`, `Jenkinsfile`, `azure-pipelines.yml` (not matched by `_is_ci_file()` — intentional scope limitation)
- Nested Dockerfile patterns: `COPY --from=` referencing external images

**Impact:** LOW — Multi-line commands are a known limitation of line-by-line scanning. Alternative CI formats are out of scope by design (Grippy focuses on GitHub Actions). The missing tests would prove these are intentional non-detections.

**Recommendation:** Add 1 multi-line true-negative test in a future batch to document the line-by-line limitation.

### Compound Chain Exposure

`None identified` — rule-ci-risk produces RuleResult findings consumed by the engine/enrichment layer. No I/O, no subprocess. `_is_ci_file()` file-type routing is self-contained.

---

## Dimension Details

### 1. Contract Fidelity

**Key question:** Do types, exports, and validation faithfully represent the unit's contract?

**Score:** 7/10
**Evidence:**
- mypy strict passes with zero issues (Tier A: static analysis).
- All functions fully typed: `run(self, ctx: RuleContext) -> list[RuleResult]`, `_is_ci_file(path: str) -> bool` (Tier A: mypy proves this).
- Rule follows duck-typed Rule protocol: exposes `id`, `description`, `default_severity`, `run()`.
- `_CI_FILE_PATTERNS` typed as tuple of strings. `_SHELL_EXTENSIONS` typed as frozenset.
- Not 9: No explicit Protocol class. `default_severity` is WARN but CRITICAL findings are produced — semantic mismatch between attribute name and actual behavior.
- Calibration: matches rule-secrets (7), rule-sql (7), rule-traversal (7).

---

### 2. Robustness

**Key question:** Does the unit handle errors, retries, and edge cases correctly?

**Score:** 6/10
**Evidence:**
- Mixed-severity cascade: `_PIPE_EXEC_RE` → CRITICAL, `_SUDO_RE` → WARN, `_CHMOD_X_RE` → WARN. Priority ordering enforced by `continue` at lines 76 and 90 — a line matching curl|bash won't also be flagged for sudo.
- `_is_ci_file()` handles all file types: prefix matching, basename matching, extension matching. Paths with no dot handled gracefully (Tier C: line 40-41).
- `rsplit("/", 1)[-1]` for basename extraction — handles files at root and in nested dirs (Tier C).
- >1MB line tolerance proven (Tier A: `test_extremely_long_line`).
- No bounds on total result count.
- Not 7: Rubric criteria for 7+ structurally inapplicable.
- Calibration: matches rule-secrets (6), rule-sql (6), rule-traversal (6).

---

### 3. Security Posture

**Key question:** Does the unit protect against injection, leakage, and unauthorized access?

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 7/10
**Evidence:**
- No I/O, no network, no subprocess, no logging (Tier C: module-level inspection).
- Evidence field contains CI/shell commands, not secret values (Tier C: SR-07 analysis).
- Evidence NOT truncated — acceptable for CI commands which are typically short single-line statements.
- Uses direct iteration with `line.type != "add"` — added-lines-only filtering (Tier C).
- Does not own trust boundaries.
- Not 9: No input sanitization. Single detection layer.
- Calibration: matches rule-secrets (7), rule-sql (7), rule-traversal (7).

---

### 4. Adversarial Resilience

**Key question:** Can the unit resist adversarial input from untrusted PR content and prompt injection?

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 6/10
**Evidence:**
- **ReDoS defense (Tier A):** `test_redos_pipe_exec_re` — the primary target. `_PIPE_EXEC_RE` has `\b(?:curl|wget)\b.*\|\s*(?:ba)?sh\b` with `.*` quantifier. 100K-char adversarial input with `curl` prefix but no trailing `| sh` forces `.*` to scan full input. Completes under 5s. `_SUDO_RE` and `_CHMOD_X_RE` are structurally safe (word-boundary, no greedy quantifiers).
- **Large input tolerance (Tier A):** >1MB line through full rule.run().
- **Safe-negative specificity (Tier A):** `test_pseudo_sudo_not_flagged` proves `\bsudo\b` word boundary prevents substring matches (e.g., "pseudocode"). `test_curl_download_without_pipe` proves curl without pipe is NOT CRITICAL.
- Not 7: No evasion fixtures (encoded shell commands, Unicode in CI files). No false-positive manipulation tests.
- Calibration: matches rule-sql (6), rule-workflows (6), rule-traversal (6). Safe-negatives are stronger than most Batch 2 units.

---

### 5. Auditability & Traceability

**Key question:** Can operators investigate failures, reproduce review results, and trace the decision path from input to output?

**Score:** 7/10
**Evidence:**
- Each `RuleResult` includes `rule_id`, `severity`, `message`, `file`, `line`, `evidence` (Tier C).
- **Messages are pattern-specific** — better than most rules:
  - "Remote script piped to shell — supply chain risk" (curl|bash)
  - "sudo usage in CI context" (sudo)
  - "chmod +x in CI context — verify target script" (chmod+x)
- Deterministic: same diff input → same findings output. Fully reproducible.
- Priority cascade via `continue` means each line produces at most one finding — clear, no ambiguity.
- No logging — appropriate for a rule.
- Not 8: No trace correlation IDs. No indication of which CI file type matched.
- Calibration: **above** rule-sql (6) and rule-llm-sinks (6) due to pattern-specific messages. Comparable to rule-sinks which also has specific messages.

---

### 6. Test Quality

**Key question:** Do tests verify meaningful behavior with good coverage?

**Score:** 7/10
**Evidence:**
- **Test count:** 15 tests across 4 test classes (Tier A: test_grippy_rule_ci.py).
- **Source:test ratio:** 1.60:1 (169 LOC tests / 106 LOC source).
- **Fixture matrix categories covered:**
  - Positive: 8 tests across 5 file types (workflow, Dockerfile, Makefile, .sh, .bash) × 3 patterns (curl|bash, sudo, chmod+x).
  - Negative: 1 test (non-CI file ignored).
  - Edge: 1 test (context line not flagged).
  - Adversarial: 2 tests (ReDoS + long-line).
  - Safe-negatives: 2 tests (curl without pipe, pseudo-sudo substring).
- **File-type × pattern coverage note:** The positive test matrix is the most thorough in the batch — 8 tests covering the cross-product of patterns and file types.
- Missing categories (F-CIR-001): multi-line commands, alternate CI formats.
- Calibration: matches rule-sql (7: 15 tests), rule-workflows (7: 15 tests).

---

### 7. Convention Adherence

**Key question:** Does the unit follow Grippy project patterns?

**Score:** 9/10
**Evidence:**
- SPDX header present on source and test file (Tier A: file inspection).
- ruff check passes with zero issues (Tier A: static analysis).
- mypy strict passes with zero issues (Tier A: static analysis).
- bandit passes with zero issues (Tier A: static analysis).
- Test file follows mirror structure: `src/grippy/rules/ci_script_risk.py` → `tests/test_grippy_rule_ci.py` (Tier A). Note: test file name uses abbreviated `ci` — acceptable convention.
- Test file exceeds 50 LOC minimum (169 LOC) (Tier A).
- Uses direct iteration with `line.type != "add"` — same convention as rule-traversal and rule-llm-sinks.
- Mixed-severity output differs from `default_severity` attribute — documented design choice, not convention violation.
- Calibration: matches rule-sql (9), rule-traversal (9).

---

### 8. Documentation Accuracy

**Key question:** Do docstrings, comments, and docs match actual behavior?

**Score:** 7/10
**Evidence:**
- File-level docstring: "Rule 6: ci-script-execution-risk — curl|bash, sudo, chmod+x detection in CI files." (line 2) — accurate (Tier C).
- Class docstring: "Detect risky script execution patterns in CI/infrastructure files." (line 47) — accurate (Tier C).
- `_is_ci_file` docstring: "Check if a file is a CI/infrastructure file." — accurate (Tier C).
- Inline comments on each pattern: "curl|bash or wget|bash — piping remote scripts" (line 20), "sudo usage" (line 23), "chmod +x patterns" (line 26).
- Inline severity comments in run(): "curl|bash — CRITICAL" (line 64), "sudo — WARN" (line 78), "chmod +x — WARN" (line 92).
- Not 9: No documentation of file-type routing logic in `_is_ci_file()`. No explanation of why `.gitlab-ci.yml` is excluded.
- Calibration: matches rule-secrets (7), rule-sql (7).

---

### 9. Performance

**Key question:** Is the unit efficient for its workload?

**Score:** 8/10
**Evidence:**
- 3 regex patterns compiled once at module load via `re.compile()` (Tier C: lines 21-27).
- `_is_ci_file()` early exit at line 56 — O(1) for non-CI files (tuple prefix check + basename check + extension check).
- `_CI_FILE_PATTERNS` is a small tuple (4 entries) — fast prefix scan.
- `_SHELL_EXTENSIONS` frozenset — O(1) membership test (Tier C: line 41).
- Linear scan: O(files × lines × patterns). Priority cascade with `continue` means at most 2 regex evaluations per line (CRITICAL → WARN, never all 3 unless no match).
- Not 9: No profiling data.
- Calibration: matches rule-secrets (8), rule-sql (8), rule-traversal (8).

---

### 10. Dead Code / Debt

**Key question:** Is the unit free of unused code and tracked debt?

**Score:** 9/10
**Evidence:**
- Zero `TODO` or `FIXME` comments (Tier A: grep search).
- All functions called: `CiScriptRiskRule` registered in `RULE_REGISTRY`, `_is_ci_file` at line 56 (Tier C: caller trace).
- All 3 compiled patterns used: `_PIPE_EXEC_RE` at line 65, `_SUDO_RE` at line 79, `_CHMOD_X_RE` at line 93 (Tier C).
- `_CI_FILE_PATTERNS` used at line 33, `_SHELL_EXTENSIONS` used at line 41 (Tier C).
- ruff detects no unused imports (Tier A).
- Not 10: F-CIR-001 identifies fixture matrix gaps — not code debt, but tracked.
- Calibration: matches rule-secrets (9), rule-sql (9), rule-traversal (9).

---

### 11. Dependency Hygiene

**Key question:** Are unit boundaries clean with no circular or unnecessary deps?

**Score:** 9/10
**Evidence:**
- 2 internal dependencies: `grippy.rules.base` (RuleResult, RuleSeverity) and `grippy.rules.context` (RuleContext). Both are same-phase (Phase 1) sibling modules (Tier A: import inspection at lines 8-9).
- 1 external dependency: `re` (stdlib) (Tier A: import inspection at line 6).
- No circular imports (Tier A: ruff check).
- Lean imports: only `RuleContext` from context module (same as rule-sql, rule-crypto). Unlike rule-llm-sinks, does not import `DiffHunk` — uses direct iteration instead.
- Not 10: Has 2 internal dependencies. Necessary and clean but not zero.
- Calibration: matches rule-secrets (9), rule-sql (9), rule-traversal (9).
