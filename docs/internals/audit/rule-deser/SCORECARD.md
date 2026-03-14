<!-- SPDX-License-Identifier: MIT -->

# Audit Scorecard: rule-deser

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
| 2. Robustness | 7/10 | A + C | torch.load safe-mode exemption. Explicit coordination with dangerous_sinks.py. `matched` flag prevents double-counting. |
| 3. Security Posture | 7/10 | C | No I/O, no secrets in findings. Evidence truncated at 120 chars. Pattern-specific messages name the library. |
| 4. Adversarial Resilience | 6/10 | A + C | ReDoS test on shelve pattern (Tier A). 1MB long-line tolerance (Tier A). All patterns structurally safe. |
| 5. Auditability & Traceability | 8/10 | A + C | **Pattern-specific messages** name the library and risk: "shelve.open — uses pickle internally", "torch.load without weights_only=True". Best traceability in batch. |
| 6. Test Quality | 7/10 | A | 17 tests. Positive (5), negative (1), edge (2), metadata (1), adversarial (2), pattern coverage (2), safe-negatives (2), torch-safe (1), yaml-coordination (1). |
| 7. Convention Adherence | 9/10 | A | ruff, mypy strict, bandit clean. SPDX header. Uses `ctx.added_lines_for()`. Explicit cross-rule coordination comments. |
| 8. Documentation Accuracy | 8/10 | C | Excellent cross-rule coordination documentation. Explicit notes about pickle/yaml ownership. |
| 9. Performance | 8/10 | C | Compiled regexes, linear scan. `matched` flag + `break` prevent redundant work. |
| 10. Dead Code / Debt | 9/10 | A + C | Zero TODOs, all functions called, all patterns used. |
| 11. Dependency Hygiene | 9/10 | A | 2 internal deps (rules.base, rules.context) -- same phase. No circular deps. |
| **Overall** | **7.5/10** | | **Average of 11 dimensions** |

**Health status:** Adequate (provisional)

**Determination:**
1. Average-based status: 7.5/10 falls in 6.0-7.9 range = Adequate
2. Override gates: None fired.
3. Ceiling gates: None fired. All gate dimensions >= 6.
4. Suffixes: `(provisional)` -- dims 3, 9 include Tier C evidence components.

**Override gates fired:** None
**Ceiling gates fired:** None

---

## Checklist: SR-01 through SR-09

| ID | Verdict | Evidence | Notes |
|----|---------|----------|-------|
| SR-01 | PASS | Tier A: 5 positive tests cover all detection targets: `test_shelve_open` (shelve), `test_jsonpickle_decode` (jsonpickle), `test_dill_loads` (dill.loads), `test_torch_load_unsafe` (torch.load), `test_cloudpickle_loads` (cloudpickle.loads — coverage test). Plus `test_dill_load_singular` proves `dill.load` (file-based, not just `dill.loads`) is also caught. `test_torch_load_safe` proves `weights_only=True` exemption works. | All 4 `_DESER_PATTERNS` entries + torch.load exercised. |
| SR-02 | PASS | Tier A: `test_redos_shelve_pattern` — 100K-char adversarial input against `_DESER_PATTERNS[0]` (shelve pattern). `test_extremely_long_line` — >1MB line through full `rule.run()`. All patterns are word-boundary anchored with `\s*\(` — no nested quantifiers, no backtracking risk. | All patterns structurally safe. Shelve pattern proven by Tier A test. |
| SR-03 | PASS | Tier A: `test_rule_metadata` asserts `rule.default_severity == RuleSeverity.ERROR`. Tier C: `default_severity = RuleSeverity.ERROR` (line 48), used consistently in all `RuleResult` constructors. | ERROR severity for all deserialization findings. |
| SR-04 | PASS | Tier C: `ctx.added_lines_for(f.path)` at line 55 — uses the engine's canonical added-line filter. Same as rule-sql, rule-crypto, rule-creds. | Standard helper. |
| SR-05 | PASS | Tier C: All `RuleResult` instances include `rule_id`, `severity`, `message`, `file`, `line`, `evidence=content.strip()[:120]` (lines 63-72, 82-93). Evidence truncated at 120 chars. **Pattern-specific messages** include library name and risk description (e.g., "Insecure deserialization: shelve.open — uses pickle internally"). | Best evidence quality in the batch — messages name the specific library and explain the risk. |
| SR-06 | N/A | Ownership: engine-owned. | Per SR-06 scope note. |
| SR-07 | PASS | Tier C: Evidence contains deserialization API calls (e.g., `db = shelve.open('data')`), not secret values. Library names and function calls are code references, not credentials. | No leakage risk. |
| SR-08 | PASS | Tier C: All findings use standard `RuleResult` dataclass. Fields compatible with `ResultEnrichment` post-processing. | Standard format. |
| SR-09 | Partial | Tier A: Positive (5 + 2 pattern coverage = 7), negative (1 yaml-not-this-rule), edge (2: comment ignored, non-Python ignored), metadata (1), adversarial (2: ReDoS + long-line), safe-negatives (2: json.loads safe, pickle.loads not-this-rule), torch-safe (1). **17 tests with good cross-rule coordination coverage.** Missing: renamed/binary files, multi-line deserialization calls. | See F-DSR-001. Safe-negatives anchor cross-rule boundaries well. |

**N/A items:** 1/9 (SR-06 only).

---

## Findings

### F-DSR-001: Fixture matrix missing boundary and multi-line scenarios

**Severity:** LOW
**Status:** OPEN
**Checklist:** SR-09
**Evidence tier:** C (manual review of test file)

**Description:** The fixture matrix has strong positive and cross-rule coordination coverage. The safe-negative tests (`test_json_loads_safe`, `test_pickle_loads_not_this_rule`) are particularly valuable — they prove the rule's boundary with dangerous_sinks.py is correct. However, it lacks tests for:
- Multi-line deserialization: `shelve.open(\n    'data'\n)` split across lines (rule scans per-line)
- Renamed/binary files
- torch.load with other keyword arguments but NOT weights_only (e.g., `torch.load('model.pt', map_location='cpu')`)

**Impact:** LOW — Multi-line calls are a known limitation of line-by-line scanning. The torch.load near-miss would prove specificity of the `_TORCH_SAFE_RE` check. Renamed/binary files are handled by the diff parser.

**Recommendation:** Add 1 torch.load near-miss test (`map_location` without `weights_only`) in a future batch.

### Compound Chain Exposure

`None identified` — rule-deser produces RuleResult findings consumed by the engine/enrichment layer. No I/O, no subprocess, no prompt composition. Explicit cross-rule coordination with dangerous_sinks.py documented in source comments.

---

## Dimension Details

### 1. Contract Fidelity

**Key question:** Do types, exports, and validation faithfully represent the unit's contract?

**Score:** 7/10
**Evidence:**
- mypy strict passes with zero issues (Tier A: static analysis).
- All functions fully typed: `run(self, ctx: RuleContext) -> list[RuleResult]`, `_file_ext(path: str) -> str`, `_is_comment(content: str) -> bool` (Tier A: mypy proves this).
- Rule follows duck-typed Rule protocol: exposes `id`, `description`, `default_severity`, `run()`.
- `_DESER_PATTERNS` is a `list[tuple[str, re.Pattern[str]]]` — message + pattern paired together (Tier A: mypy).
- `_TORCH_LOAD_RE` and `_TORCH_SAFE_RE` are `re.Pattern[str]` (Tier A: mypy).
- Not 9: No explicit Protocol class. No runtime type checks.
- Calibration: matches rule-secrets (7), rule-sql (7), rule-traversal (7).

---

### 2. Robustness

**Key question:** Does the unit handle errors, retries, and edge cases correctly?

**Score:** 7/10
**Evidence:**
- **Explicit cross-rule coordination:** Comments at lines 11-12 and 80 document that pickle/marshal are owned by dangerous_sinks.py and yaml.load is owned by dangerous_sinks.py. This prevents duplicate findings across rules.
- **torch.load safe-mode exemption:** `_TORCH_SAFE_RE` checks for `weights_only=True` — modern PyTorch safe deserialization. `test_torch_load_safe` (Tier A) proves the exemption works.
- `matched` flag at line 60 + `break` at line 74 + `continue` at line 77 — prevent double-counting when a line matches both a standard pattern and torch.load.
- `_file_ext()` handles files with no extension gracefully (Tier C).
- `_is_comment()` handles empty strings gracefully (Tier C).
- >1MB line tolerance proven (Tier A: `test_extremely_long_line`).
- **Above 6** because the cross-rule coordination and torch.load safe-mode exemption are deliberate robustness features beyond basic pattern matching.
- Calibration: above rule-sql (6), rule-traversal (6). Same as rule-creds (7) — both have sophisticated suppression logic.

---

### 3. Security Posture

**Key question:** Does the unit protect against injection, leakage, and unauthorized access?

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 7/10
**Evidence:**
- No I/O, no network, no subprocess, no logging (Tier C: module-level inspection).
- Evidence contains deserialization API calls, not secret values (Tier C: SR-07 analysis).
- Evidence truncated at 120 chars (`content.strip()[:120]`) — prevents excessively long evidence (Tier C).
- Uses `ctx.added_lines_for(path)` — canonical added-line filter (Tier C).
- Does not own trust boundaries.
- Not 8: No redaction mechanism (appropriate — no secrets in deserialization call evidence). Single detection layer.
- Calibration: matches rule-sql (7), rule-traversal (7). Below rule-creds (8) which has active redaction.

---

### 4. Adversarial Resilience

**Key question:** Can the unit resist adversarial input from untrusted PR content and prompt injection?

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 6/10
**Evidence:**
- **ReDoS defense (Tier A):** `test_redos_shelve_pattern` — 100K-char adversarial input against `_DESER_PATTERNS[0]` (shelve pattern: `\bshelve\.open\s*\(`). Word-boundary anchored with `\s*\(` — structurally safe. All other patterns follow the same structure: `\b{module}\.{function}\s*\(`. No nested quantifiers.
- **`_TORCH_LOAD_RE` and `_TORCH_SAFE_RE` structural analysis (Tier C):** Both use `\b...\s*\(` or `\b...\s*=\s*True\b` — no backtracking risk.
- **Large input tolerance (Tier A):** >1MB line through full rule.run().
- Not 7: Only 1 ReDoS test (shelve) — other patterns not individually proven, though structurally identical. No evasion fixtures.
- Calibration: matches rule-sql (6), rule-ci-risk (6), rule-traversal (6).

---

### 5. Auditability & Traceability

**Key question:** Can operators investigate failures, reproduce review results, and trace the decision path from input to output?

**Score:** 8/10
**Evidence:**
- Each `RuleResult` includes `rule_id`, `severity`, `message`, `file`, `line`, `evidence` (Tier C).
- **Pattern-specific messages — best in the batch:**
  - "Insecure deserialization: shelve.open — uses pickle internally"
  - "Insecure deserialization: jsonpickle.decode — arbitrary object instantiation"
  - "Insecure deserialization: dill.loads — superset of pickle"
  - "Insecure deserialization: cloudpickle.loads — arbitrary code execution"
  - "Insecure deserialization: torch.load without weights_only=True"
- Each message names the specific library AND explains the risk. Operators can immediately understand what was found and why it matters.
- Deterministic: same diff input → same findings output. Fully reproducible.
- `matched` flag logic is clear: one finding per line, standard patterns checked first, torch.load checked only if no standard match.
- **Above 7** because pattern-specific messages with risk explanations are the best traceability evidence in the batch. Operators don't need to look up what "insecure deserialization" means — the message tells them.
- Calibration: above rule-ci-risk (7) which has pattern-specific messages but no risk explanations. Above rule-sql (6) and rule-llm-sinks (6) which have generic messages.

---

### 6. Test Quality

**Key question:** Do tests verify meaningful behavior with good coverage?

**Score:** 7/10
**Evidence:**
- **Test count:** 17 tests across 5 test classes (Tier A: test_grippy_rule_insecure_deserialization.py).
- **Source:test ratio:** 1.63:1 (155 LOC tests / 95 LOC source).
- **Fixture matrix categories covered:**
  - Positive: 5 tests (shelve, jsonpickle, dill, torch unsafe, cloudpickle).
  - Negative: 1 test (yaml.load not-this-rule — cross-rule coordination).
  - Edge: 2 tests (comment ignored, non-Python ignored).
  - Metadata: 1 test (rule ID + severity).
  - Adversarial: 2 tests (ReDoS + long-line).
  - Pattern coverage: 2 tests (cloudpickle.loads, dill.load singular).
  - Safe-negatives: 2 tests (json.loads safe, pickle.loads not-this-rule).
  - Torch-safe: 1 test (weights_only=True).
- **Cross-rule coordination coverage:** The yaml and pickle safe-negative tests are unique to this rule — they prove the boundary with dangerous_sinks.py.
- Missing categories (F-DSR-001): torch.load near-miss, multi-line calls.
- Calibration: matches rule-sql (7: 15 tests), rule-ci-risk (7: 15 tests). Cross-rule tests add distinctive value.

---

### 7. Convention Adherence

**Key question:** Does the unit follow Grippy project patterns?

**Score:** 9/10
**Evidence:**
- SPDX header present on source and test file (Tier A: file inspection).
- ruff check passes with zero issues (Tier A: static analysis).
- mypy strict passes with zero issues (Tier A: static analysis).
- bandit passes with zero issues (Tier A: static analysis).
- Test file follows mirror structure: `src/grippy/rules/insecure_deserialization.py` → `tests/test_grippy_rule_insecure_deserialization.py` (Tier A).
- Test file exceeds 50 LOC minimum (155 LOC) (Tier A).
- Uses `ctx.added_lines_for()` — canonical helper (same as rule-sql, rule-crypto, rule-creds).
- Uses `_file_ext()` and `_is_comment()` — same helpers as rule-sql, rule-crypto.
- **Explicit cross-rule coordination comments** (lines 11-12, 80) — excellent convention for multi-rule systems.
- Calibration: matches rule-sql (9), rule-traversal (9).

---

### 8. Documentation Accuracy

**Key question:** Do docstrings, comments, and docs match actual behavior?

**Score:** 8/10
**Evidence:**
- File-level docstring: "Rule 10: insecure-deserialization -- detect unsafe deserialization of untrusted data." (line 2) — accurate (Tier C).
- Class docstring: "Detect unsafe deserialization of untrusted data." (line 44) — accurate (Tier C).
- Class description: "Flag shelve, jsonpickle, dill, cloudpickle, and torch.load" (line 47) — accurate and specific (Tier C).
- **Cross-rule coordination comments (lines 11-12, 25, 80):**
  - "NOTE: pickle/marshal are already covered by dangerous_sinks.py (Rule 3)." — accurate.
  - "NOTE: yaml.load is handled by dangerous_sinks.py (Rule 3)" — accurate.
  - These comments are the best cross-rule documentation in the codebase.
- Pattern messages include risk descriptions (e.g., "uses pickle internally", "arbitrary code execution") — documentation embedded in output.
- **Above 7** because the cross-rule coordination documentation is excellent and the pattern messages are self-documenting.
- Calibration: above rule-sql (7), rule-ci-risk (7). Best documentation accuracy in the batch.

---

### 9. Performance

**Key question:** Is the unit efficient for its workload?

**Score:** 8/10
**Evidence:**
- 6 regex patterns compiled once at module load via `re.compile()` (Tier C: lines 14-27). 4 in `_DESER_PATTERNS` list + `_TORCH_LOAD_RE` + `_TORCH_SAFE_RE`.
- `_PYTHON_EXTENSIONS` frozenset — O(1) membership test (Tier C: line 29).
- File extension check at entry provides early exit for non-Python files (Tier C: line 53).
- `_is_comment()` check before pattern matching provides early exit for comments (Tier C: line 56).
- Linear scan: O(files × lines × patterns). Each line tested against 4 standard patterns + optional torch.load.
- `break` at line 74 short-circuits after first standard pattern match per line.
- `matched` flag + `continue` prevents redundant torch.load check when standard pattern already matched.
- `_TORCH_SAFE_RE` check only runs when `_TORCH_LOAD_RE` matches — conditional evaluation (Tier C: line 81).
- Not 9: No profiling data.
- Calibration: matches rule-secrets (8), rule-sql (8).

---

### 10. Dead Code / Debt

**Key question:** Is the unit free of unused code and tracked debt?

**Score:** 9/10
**Evidence:**
- Zero `TODO` or `FIXME` comments (Tier A: grep search).
- All functions called: `InsecureDeserializationRule` registered in `RULE_REGISTRY`, `_file_ext` at line 53, `_is_comment` at line 56 (Tier C: caller trace).
- All 6 compiled patterns used: 4 `_DESER_PATTERNS` at line 61-74, `_TORCH_LOAD_RE` at line 81, `_TORCH_SAFE_RE` at line 81 (Tier C).
- `_PYTHON_EXTENSIONS` frozenset used at line 53 (Tier C).
- ruff detects no unused imports (Tier A).
- Not 10: F-DSR-001 identifies fixture matrix gaps — not code debt, but tracked.
- Calibration: matches rule-secrets (9), rule-sql (9), rule-traversal (9).

---

### 11. Dependency Hygiene

**Key question:** Are unit boundaries clean with no circular or unnecessary deps?

**Score:** 9/10
**Evidence:**
- 2 internal dependencies: `grippy.rules.base` (RuleResult, RuleSeverity) and `grippy.rules.context` (RuleContext). Both are same-phase (Phase 1) sibling modules (Tier A: import inspection at lines 8-9).
- 1 external dependency: `re` (stdlib) (Tier A: import inspection at line 6).
- No circular imports (Tier A: ruff check).
- Lean imports: only `RuleContext` from context module. Same pattern as rule-sql, rule-crypto, rule-creds.
- **No runtime dependency on dangerous_sinks.py** — coordination is by convention (comments), not by import. Clean boundary.
- Not 10: Has 2 internal dependencies. Necessary and clean but not zero.
- Calibration: matches rule-secrets (9), rule-sql (9), rule-traversal (9).
