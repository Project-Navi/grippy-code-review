<!-- SPDX-License-Identifier: MIT -->

# Audit Scorecard: rule-sinks

**Audit date:** 2026-03-13
**Commit:** b40d4ec
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
| 2. Robustness | 6/10 | A + C | Pure function. `break` limits to one finding per line (Python). No bounds on total. |
| 3. Security Posture | 7/10 | C | No I/O, no secrets in findings. Evidence shows code patterns, not secret values. |
| 4. Adversarial Resilience | 6/10 | A + C | ReDoS test on subprocess `.*` pattern (Tier A). 1MB line tolerance (Tier A). Positive-heavy fixture matrix. |
| 5. Auditability & Traceability | 6/10 | C | Findings include rule_id/file/line/evidence. Deterministic. No logging. |
| 6. Test Quality | 7/10 | A | 21 tests. Strong positive coverage (16), adversarial (2), but only 2 negative + 1 edge case. |
| 7. Convention Adherence | 9/10 | A | ruff, mypy strict, bandit clean. SPDX header. Mirror test structure. |
| 8. Documentation Accuracy | 7/10 | C | File-level docstring, class docstring accurate. Pattern lists self-documenting. |
| 9. Performance | 8/10 | C | Compiled regexes, linear scan, early break per line. O(files x lines x patterns). |
| 10. Dead Code / Debt | 9/10 | A + C | Zero TODOs, all functions called, all patterns used. |
| 11. Dependency Hygiene | 9/10 | A | 2 internal deps (rules.base, rules.context) -- same phase. No circular deps. |
| **Overall** | **7.4/10** | | **Average of 11 dimensions** |

**Health status:** Adequate (provisional)

**Determination:**
1. Average-based status: 7.4/10 falls in 6.0-7.9 range = Adequate
2. Override gates: None fired.
3. Ceiling gates: None fired. All gate dimensions >= 6.
4. Suffixes: `(provisional)` -- dims 2, 3, 5, 8, 9 include Tier C evidence components.

**Override gates fired:** None
**Ceiling gates fired:** None

---

## Checklist: SR-01 through SR-09

| ID | Verdict | Evidence | Notes |
|----|---------|----------|-------|
| SR-01 | PASS | Tier A: 16 positive tests cover all 7 Python sinks + yaml.load + 5 JS/TS sinks across 4 file extensions (.js, .ts, .jsx, .tsx). 2 negative tests (yaml safe_load, yaml SafeLoader). | All documented patterns detected. |
| SR-02 | PASS | Tier A: `test_redos_subprocess_pattern` exercises the `\bsubprocess\.\w+\(.*shell\s*=\s*True` pattern (the one with `.*`) against 100K-char adversarial input under 5s timeout. | Other patterns use `\b...\s*\(` (word boundary + literal + optional whitespace + paren) -- structurally safe from backtracking. The subprocess pattern is the only one with backtracking risk due to `.*` and it passes. |
| SR-03 | PASS | Tier A: `test_severity_is_error` asserts all findings are ERROR. Tier C: `default_severity = RuleSeverity.ERROR` (line 49), used consistently in `_scan_python` (line 70) and `_scan_js` (line 103). | All sinks are ERROR severity. Matches gate thresholds. |
| SR-04 | PASS | Tier A: `test_context_line_not_flagged` proves context lines (existing `eval()`) next to an added comment are NOT flagged. Tier C: `ctx.added_lines_for(path)` (lines 64, 98) explicitly filters to added lines only. | Strong evidence. Uses `added_lines_for()` -- the engine's canonical added-line filter. |
| SR-05 | PASS | Tier C: All `RuleResult` instances include `rule_id=self.id`, `severity=self.default_severity`, `message=f"Dangerous execution sink: {name}"`, `file=path`, `line=lineno`, `evidence=content.strip()` (lines 70-78, 87-92, 102-111). | Descriptive messages include sink name. Sufficient for human triage. |
| SR-06 | N/A | Ownership: engine-owned. Individual rule units do not own profile dispatch logic. | Per SR-06 scope note: "Mark N/A when auditing individual rule units." |
| SR-07 | PASS | Tier C: Evidence field contains code patterns (`eval(user_input)`, `subprocess.run(cmd, shell=True)`, `pickle.loads(raw)`), not secret values. Edge case where a line contains both a sink and an inline secret is theoretical -- rule-secrets would independently flag the secret with redaction. | Hypothesis only (Tier D), not a finding. |
| SR-08 | PASS | Tier C: All findings use standard `RuleResult` dataclass (imported from rules.base). Fields are compatible with `ResultEnrichment` post-processing. | Standard format matches enrichment contract. |
| SR-09 | Partial | Tier A: Positive (16 tests), negative (2 yaml safe variants), adversarial (1 ReDoS + 1 long-line), edge cases (1 non-code file, 1 context line). Missing: negative tests for non-matching Python code, renamed/binary files, `.pyw`/`.cjs`/`.mjs` extensions. | See F-SNK-001. Positive-heavy skew (16 pos vs 2 neg) is a genuine gap. |

**N/A items:** 1/9 (SR-06 only). Well below the >50% reclassification threshold.

---

## Findings

### F-SNK-001: Positive-heavy fixture matrix

**Severity:** LOW
**Status:** OPEN
**Checklist:** SR-09
**Evidence tier:** A (test file analysis)

**Description:** The fixture matrix has 16 positive tests but only 2 negative tests (both yaml-specific). There are no negative tests for:
- Clean Python code that happens to contain pattern substrings (e.g., `evaluate()`, `execution_context`, `os_system_info`)
- Non-code file types beyond `.md` (e.g., `.txt`, `.json`, `.cfg`)
- Files with ambiguous extensions (e.g., `.pyw`, `.cjs`, `.mjs`)

The 16:2 positive:negative ratio indicates the fixture matrix is optimized for detection confidence but undertests specificity.

**Impact:** LOW -- false positives are unlikely in practice because patterns use word boundaries (`\b`) and require specific function signatures (e.g., `\beval\s*\(`). A function named `evaluate()` would not match `\beval\s*\(`. The risk is primarily theoretical.

**Recommendation:** Add 2-3 negative tests for near-miss patterns (e.g., `evaluate()`, `os.system_info`) in a future batch to prove specificity.

### Compound Chain Exposure

`None identified` -- rule-sinks produces RuleResult findings consumed by the engine/enrichment layer. It does not own trust-boundary behavior. Evidence field contains code patterns (not secrets), so it does not relay sensitive data.

---

## Dimension Details

### 1. Contract Fidelity

**Key question:** Do types, exports, and validation faithfully represent the unit's contract?

**Score:** 7/10
**Evidence:**
- mypy strict passes with zero issues (Tier A: static analysis).
- All functions fully typed: `run(self, ctx: RuleContext) -> list[RuleResult]`, `_scan_python(self, path: str, ctx: RuleContext) -> list[RuleResult]`, `_scan_js(self, path: str, ctx: RuleContext) -> list[RuleResult]`, `_file_ext(path: str) -> str` (Tier A: mypy proves this).
- Rule follows duck-typed Rule protocol: exposes `id`, `description`, `default_severity`, `run()`.
- Pattern lists are typed: `_PYTHON_SINKS: list[tuple[str, re.Pattern[str]]]`, `_JS_SINKS: list[tuple[str, re.Pattern[str]]]` (Tier A: mypy).
- Not 9: No explicit Protocol class. No runtime type checks beyond type annotations.
- Calibration: matches rule-secrets (7), rule-workflows (7).

---

### 2. Robustness

**Key question:** Does the unit handle errors, retries, and edge cases correctly?

**Score:** 6/10
**Evidence:**
- Pure function design: `run()` takes context, returns findings list. If no patterns match, returns empty list (Tier C).
- `break` at line 79 limits to one finding per line in Python scanning, preventing duplicate findings for lines matching multiple patterns (Tier C: code reading).
- Same `break` pattern in JS scanning at line 112 (Tier C).
- yaml.load special handling: only flags when `_YAML_SAFE_RE` does NOT match -- avoids false positives on safe usage (Tier A: 2 tests).
- `_file_ext()` handles files with no extension gracefully (returns `""`) (Tier C: code reading at line 42).
- >1MB line tolerance proven (Tier A: `test_extremely_long_line`).
- No bounds on total result count. No retries/timeouts needed.
- Not 7: Rubric criteria for 7+ structurally inapplicable.
- Calibration: matches rule-secrets (6), rule-workflows (6).

---

### 3. Security Posture

**Key question:** Does the unit protect against injection, leakage, and unauthorized access?

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 7/10
**Evidence:**
- No I/O, no network, no subprocess, no logging (Tier C: module-level inspection).
- Evidence field contains code patterns (e.g., `eval(user_input)`, `subprocess.run(cmd, shell=True)`) which are not secret values (Tier C: SR-07 analysis).
- `content.strip()` on evidence prevents whitespace-based injection (Tier C: lines 77, 92, 111).
- Uses `ctx.added_lines_for(path)` -- the engine's canonical added-line filter -- rather than implementing its own line filtering (Tier C: defense delegation to engine).
- Does not own trust boundaries.
- Not 9: No input sanitization (appropriate -- processes structured data). Single detection layer.
- Calibration: matches rule-secrets (7), rule-workflows (7).

---

### 4. Adversarial Resilience

**Key question:** Can the unit resist adversarial input from untrusted PR content and prompt injection?

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 6/10
**Evidence:**
- **ReDoS defense (Tier A):** `test_redos_subprocess_pattern` exercises the `.*` pattern (`\bsubprocess\.\w+\(.*shell\s*=\s*True`) with 100K-char adversarial input. Completes under 5s timeout. This is the only pattern with backtracking risk.
- **Large input tolerance (Tier A):** `test_extremely_long_line` proves >1MB lines are processed without crash.
- Other patterns use `\b...\s*\(` structure -- word boundary anchored, no nested quantifiers, structurally safe (Tier C: regex analysis of 12 patterns).
- Limited adversarial exposure: processes parsed diff lines. Attack surface is ReDoS and false positive/negative manipulation.
- Not 7: Positive-heavy fixture matrix (F-SNK-001). No Unicode adversarial tests. No adversarial fixtures beyond ReDoS + long-line.
- Calibration: between rule-secrets (5) and rule-engine (7). Scored 6 -- ReDoS + long-line proven, but missing specificity testing.

---

### 5. Auditability & Traceability

**Key question:** Can operators investigate failures, reproduce review results, and trace the decision path from input to output?

**Score:** 6/10
**Evidence:**
- Each `RuleResult` includes `rule_id`, `severity`, `message`, `file`, `line`, `evidence` (Tier C: code inspection).
- Messages include the specific sink name: `f"Dangerous execution sink: {name}"` -- directly traceable to `_PYTHON_SINKS`/`_JS_SINKS` tuple labels (Tier C).
- Deterministic: same diff input -> same findings output. Fully reproducible.
- File extension dispatch is explicit and traceable: `.py` -> `_scan_python`, `.js/.ts/.jsx/.tsx` -> `_scan_js` (Tier C).
- No logging -- appropriate for a rule.
- Not 7: No structured error context. No trace correlation IDs.
- Calibration: matches rule-secrets (6), rule-workflows (6).

---

### 6. Test Quality

**Key question:** Do tests verify meaningful behavior with good coverage?

**Score:** 7/10
**Evidence:**
- **Test count:** 21 tests across 2 test classes (Tier A: test_grippy_rule_sinks.py).
- **Source:test ratio:** 1.47:1 (166 LOC tests / 113 LOC source).
- **Fixture matrix categories covered:**
  - Positive: 16 tests (7 Python sinks + yaml unsafe + 4 JS sinks + 2 JSX/TSX).
  - Negative: 2 tests (yaml safe_load, yaml SafeLoader).
  - Adversarial: 2 tests (ReDoS subprocess, 1MB line).
  - Edge cases: 2 tests (non-code file ignored, context line not flagged).
  - Severity: 1 test (all ERROR).
- Missing categories (F-SNK-001): near-miss negatives, non-code file variety, ambiguous extensions.
- Calibration: rule-secrets scored 6 (14 tests, no adversarial). rule-sinks has more tests and adversarial coverage. rule-workflows scored 7 (15 tests, stronger negative coverage proportionally). rule-sinks matches at 7 due to more total tests despite positive skew.

---

### 7. Convention Adherence

**Key question:** Does the unit follow Grippy project patterns?

**Score:** 9/10
**Evidence:**
- SPDX header present on source and test file (Tier A: file inspection).
- ruff check passes with zero issues (Tier A: static analysis).
- mypy strict passes with zero issues (Tier A: static analysis).
- bandit passes with zero issues (Tier A: static analysis).
- Test file follows mirror structure: `src/grippy/rules/dangerous_sinks.py` -> `tests/test_grippy_rule_sinks.py` (Tier A).
- Test file exceeds 50 LOC minimum (166 LOC) (Tier A).
- Naming consistent: PascalCase for class, snake_case for functions, UPPER_CASE for module constants.
- Calibration: matches all prior units at 9.

---

### 8. Documentation Accuracy

**Key question:** Do docstrings, comments, and docs match actual behavior?

**Score:** 7/10
**Evidence:**
- File-level docstring: "Rule 3: dangerous-execution-sinks -- eval/exec/subprocess/pickle detection." (line 2) -- accurate (Tier C).
- Class docstring: "Detect dangerous execution sinks in Python and JavaScript/TypeScript." (line 46) -- accurate (Tier C).
- `_file_ext` helper has docstring: "Get file extension including the dot." -- accurate (Tier C).
- Pattern lists use descriptive tuple labels: `("eval()", ...)`, `("subprocess with shell=True", ...)`, `("new Function()", ...)` -- self-documenting (Tier C).
- Inline comments: "yaml.load without SafeLoader -- special handling" (line 23), "one finding per line" (line 79).
- Not 9: No usage examples. No documented rationale for why each sink is considered dangerous. `_scan_python` and `_scan_js` lack docstrings.
- Calibration: matches rule-secrets (7), rule-workflows (7).

---

### 9. Performance

**Key question:** Is the unit efficient for its workload?

**Score:** 8/10
**Evidence:**
- 14 regex patterns compiled once at module load via `re.compile()` (Tier C: lines 13-33). No per-invocation recompilation.
- Linear scan: O(files x lines x patterns). Each line tested against 7 Python or 5 JS patterns.
- `break` at lines 79/112 short-circuits after first match per line -- avoids redundant pattern testing.
- File extension check (`_file_ext`) at entry provides early exit for non-code files (Tier C).
- `frozenset` for extension lookups: O(1) per file (Tier C: lines 35-36).
- yaml.load special handling is sequential (two regex checks per yaml.load line) -- negligible overhead.
- Not 9: No profiling data.
- Calibration: matches rule-secrets (8), rule-workflows (8).

---

### 10. Dead Code / Debt

**Key question:** Is the unit free of unused code and tracked debt?

**Score:** 9/10
**Evidence:**
- Zero `TODO` or `FIXME` comments (Tier A: grep search).
- All functions called: `DangerousSinksRule` registered in `RULE_REGISTRY` (registry.py), `_scan_python` at line 57, `_scan_js` at line 59, `_file_ext` at line 55 (Tier C: caller trace).
- All 12 sink patterns used: `_PYTHON_SINKS` at line 67, `_JS_SINKS` at line 100, `_YAML_LOAD_RE` at line 82, `_YAML_SAFE_RE` at line 82 (Tier C).
- `_PYTHON_EXTENSIONS` and `_JS_EXTENSIONS` both used at lines 56, 58 (Tier C).
- ruff detects no unused imports (Tier A).
- Not 10: F-SNK-001 identifies a fixture matrix skew -- not code debt, but tracked.
- Calibration: matches rule-secrets (9), rule-workflows (9).

---

### 11. Dependency Hygiene

**Key question:** Are unit boundaries clean with no circular or unnecessary deps?

**Score:** 9/10
**Evidence:**
- 2 internal dependencies: `grippy.rules.base` (RuleResult, RuleSeverity) and `grippy.rules.context` (RuleContext). Both are same-phase (Phase 1) sibling modules (Tier A: import inspection at lines 8-9).
- 1 external dependency: `re` (stdlib) (Tier A: import inspection at line 6).
- No circular imports (Tier A: ruff check).
- Leaner than rule-workflows: imports only `RuleContext` (not `ChangedFile`, `DiffHunk`, `DiffLine`) because it delegates line iteration to `ctx.added_lines_for()`.
- Not 10: Has 2 internal dependencies. Necessary and clean but not zero.
- Calibration: matches rule-secrets (9), rule-workflows (9).
