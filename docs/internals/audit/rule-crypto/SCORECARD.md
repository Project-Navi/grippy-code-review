<!-- SPDX-License-Identifier: MIT -->

# Audit Scorecard: rule-crypto

**Audit date:** 2026-03-13
**Commit:** ab7cc93
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
| 2. Robustness | 6/10 | A + C | Pure function. `break` limits to one finding per line. No bounds on total. |
| 3. Security Posture | 7/10 | C | No I/O, no secrets in findings. Evidence truncated at 120 chars. Tests-dir filtering. |
| 4. Adversarial Resilience | 6/10 | A + C | ReDoS test on random pattern (Tier A). 1MB long-line tolerance (Tier A). All patterns structurally safe. |
| 5. Auditability & Traceability | 7/10 | C | Findings include pattern-specific messages (e.g., "MD5 hash — use SHA-256+"). |
| 6. Test Quality | 8/10 | A | 24 tests. Positive (11), negative (5), edge (3), metadata (1), adversarial (2), safe-negatives (2). |
| 7. Convention Adherence | 9/10 | A | ruff, mypy strict, bandit clean. SPDX header. Mirror test structure. |
| 8. Documentation Accuracy | 7/10 | C | File-level docstring, class docstring accurate. Pattern labels self-documenting. |
| 9. Performance | 8/10 | C | Compiled regexes, linear scan, `break` per line. Early exit on extension + tests-dir. |
| 10. Dead Code / Debt | 9/10 | A + C | Zero TODOs, all functions called, all patterns used. |
| 11. Dependency Hygiene | 9/10 | A | 2 internal deps (rules.base, rules.context) -- same phase. No circular deps. |
| **Overall** | **7.5/10** | | **Average of 11 dimensions** |

**Health status:** Adequate (provisional)

**Determination:**
1. Average-based status: 7.5/10 falls in 6.0-7.9 range = Adequate
2. Override gates: None fired.
3. Ceiling gates: None fired. All gate dimensions >= 6.
4. Suffixes: `(provisional)` -- dims 2, 3, 8, 9 include Tier C evidence components.

**Override gates fired:** None
**Ceiling gates fired:** None

---

## Checklist: SR-01 through SR-09

| ID | Verdict | Evidence | Notes |
|----|---------|----------|-------|
| SR-01 | PASS | Tier A: All 7 `_WEAK_PATTERNS` entries tested. Hash algorithms: `test_md5_hash` (MD5), `test_sha1_hash` (SHA1). Ciphers: `test_des_cipher` (DES), `test_rc4_cipher` (RC4), `test_arc4_cipher` (ARC4), `test_blowfish_cipher` (Blowfish). Mode: `test_ecb_mode` (MODE_ECB). Random: `test_random_for_crypto` (randint), `test_random_sample_flagged` (sample), `test_random_shuffle_flagged` (shuffle), `test_random_random` (random), `test_random_choice` (choice), `test_random_getrandbits` (getrandbits). All 6 `random.*` variants exercised. | Full pattern coverage achieved after Commit 1 gap closure. |
| SR-02 | PASS | Tier A: `test_redos_random_pattern` exercises the most complex pattern (`\brandom\.(?:randint|random|choice|getrandbits|sample|shuffle)\s*\(`) with 100K-char adversarial input (`"random." + "x" * 100_000`) under 5s timeout. Other patterns use `\b...\b` (simple word boundaries with no quantifiers) -- structurally immune. | All patterns safe. The random pattern is the only one with a quantifier (`\s*`) and alternation, and it passes. |
| SR-03 | PASS | Tier A: `test_md5_hash` asserts `results[0].severity == RuleSeverity.WARN`. Tier C: `default_severity = RuleSeverity.WARN` (line 48), used consistently in `RuleResult` constructor (line 66). | All weak-crypto findings are WARN severity. Matches gate thresholds: WARN gates on strict-security only. |
| SR-04 | PASS | Tier C: `ctx.added_lines_for(f.path)` at line 57 explicitly filters to added lines only. Same canonical helper as rule-sql and rule-sinks. | Consistent convention. |
| SR-05 | PASS | Tier C: All `RuleResult` instances include `rule_id=self.id`, `severity=self.default_severity`, `message=f"Weak cryptography: {message}"`, `file=path`, `line=lineno`, `evidence=content.strip()[:120]` (lines 62-71). Message includes the specific pattern label (e.g., "MD5 hash — use SHA-256+", "random module for security — use secrets"). | Pattern-specific messages provide actionable remediation guidance. Better traceability than rule-sql's generic message. |
| SR-06 | N/A | Ownership: engine-owned. Individual rule units do not own profile dispatch logic. | Per SR-06 scope note: "Mark N/A when auditing individual rule units." |
| SR-07 | PASS | Tier C: Evidence contains crypto API call patterns (e.g., `hashlib.md5(password.encode())`, `random.randint(0, 999999)`). These are code snippets, not secret values. | No leakage risk. |
| SR-08 | PASS | Tier C: All findings use standard `RuleResult` dataclass (imported from rules.base). Fields are compatible with `ResultEnrichment` post-processing. | Standard format matches enrichment contract. |
| SR-09 | Partial | Tier A: Positive (11: 2 hash + 3 cipher + 1 mode + 5 random), negative (5: sha256 safe + secrets safe + non-Python + comment + AES-GCM safe + secrets.token_bytes safe), tests-dir edge (2: tests/ and nested tests/), metadata (1: rule ID + severity), adversarial (2: 1 ReDoS + 1 long-line). Missing: renamed/binary files, `random` in non-security context (e.g., random test data generation), hashlib with HMAC wrapping. | See F-CRY-001. Strong positive coverage (all 7 entries + all 6 random variants). Good specificity via 5 negative tests and 2 safe-negative anchors. |

**N/A items:** 1/9 (SR-06 only). Well below the >50% reclassification threshold.

---

## Findings

### F-CRY-001: Fixture matrix missing context-sensitive negatives

**Severity:** LOW
**Status:** OPEN
**Checklist:** SR-09
**Evidence tier:** C (manual review of test file)

**Description:** The fixture matrix has the strongest positive coverage in the batch (11 tests covering all entries and variants) and good specificity anchoring (5 negatives + 2 safe-negatives). However, it lacks tests for:
- Context-sensitive negatives: `random.randint` used in non-security contexts (e.g., test data generation, game logic) -- the rule flags all uses regardless of context, which is by design but untested
- `hashlib.md5` in HMAC context (e.g., `hmac.new(key, msg, hashlib.md5)`) -- still flagged, which is correct but a known source of developer pushback
- Renamed/binary files

**Impact:** LOW -- the rule deliberately flags all weak crypto usage regardless of context. This is an intentional design choice: the LLM review layer handles context-sensitive triage. The fixture matrix correctly tests this behavior (tests-dir filtering IS the only context-sensitive suppression). Renamed/binary files are handled by the diff parser.

**Recommendation:** Consider documenting the "flag-all, triage-later" design decision in the rule's docstring to reduce developer confusion.

### Compound Chain Exposure

`None identified` -- rule-crypto produces RuleResult findings consumed by the engine/enrichment layer. No I/O, no subprocess, no prompt composition. Does not own trust-boundary behavior.

---

## Dimension Details

### 1. Contract Fidelity

**Key question:** Do types, exports, and validation faithfully represent the unit's contract?

**Score:** 7/10
**Evidence:**
- mypy strict passes with zero issues (Tier A: static analysis).
- All functions fully typed: `run(self, ctx: RuleContext) -> list[RuleResult]`, `_file_ext(path: str) -> str`, `_in_tests_dir(path: str) -> bool`, `_is_comment(content: str) -> bool` (Tier A: mypy proves this).
- `_WEAK_PATTERNS` typed as `list[tuple[str, re.Pattern[str]]]` (Tier A: mypy, line 11).
- Rule follows duck-typed Rule protocol: exposes `id`, `description`, `default_severity`, `run()`.
- Not 9: No explicit Protocol class. No runtime type checks.
- Calibration: matches rule-secrets (7), rule-workflows (7), rule-sinks (7), rule-traversal (7), rule-sql (7).

---

### 2. Robustness

**Key question:** Does the unit handle errors, retries, and edge cases correctly?

**Score:** 6/10
**Evidence:**
- Pure function design: `run()` takes context, returns findings list (Tier C).
- `break` at line 72 limits to one finding per line (Tier C).
- `_file_ext()` handles files with no extension gracefully (Tier C: line 29).
- `_is_comment()` handles empty strings gracefully (Tier C).
- `_in_tests_dir()` handles edge cases: `tests/` prefix (top-level) and `/tests/` infix (nested) (Tier A: 2 tests prove this).
- >1MB line tolerance proven (Tier A: `test_extremely_long_line`).
- No bounds on total result count.
- Not 7: Rubric criteria for 7+ structurally inapplicable.
- Calibration: matches all prior units at 6.

---

### 3. Security Posture

**Key question:** Does the unit protect against injection, leakage, and unauthorized access?

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 7/10
**Evidence:**
- No I/O, no network, no subprocess, no logging (Tier C: module-level inspection).
- Evidence truncated at 120 chars (`content.strip()[:120]`) -- consistent with rule-sql (Tier C: line 69).
- `_in_tests_dir()` filtering prevents noise findings in test files (Tier C: line 55-56). This is a security-positive choice: test files legitimately use weak crypto for testing purposes.
- Does not own trust boundaries.
- Not 9: No input sanitization. Single detection layer.
- Calibration: matches all prior units at 7.

---

### 4. Adversarial Resilience

**Key question:** Can the unit resist adversarial input from untrusted PR content and prompt injection?

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 6/10
**Evidence:**
- **ReDoS defense (Tier A):** `test_redos_random_pattern` exercises the random pattern (the only one with a quantifier `\s*` and alternation `(?:randint|random|choice|getrandbits|sample|shuffle)`) with 100K-char adversarial input under 5s timeout.
- **Other patterns structural analysis (Tier C):** 6 patterns use simple `\b...\b` word boundaries with no quantifiers and no alternation (e.g., `\bhashlib\.md5\b`, `\bDES\.new\b`, `\bMODE_ECB\b`). These are structurally immune to backtracking.
- **Large input tolerance (Tier A):** `test_extremely_long_line` proves >1MB lines processed without crash.
- Not 7: Only 2 adversarial tests (1 ReDoS + 1 long-line). All 7 patterns are structurally safe, so adversarial ReDoS testing is less critical here than for rule-sql. No false-positive manipulation tests.
- Calibration: matches rule-workflows (6), rule-sinks (6), rule-traversal (6), rule-sql (6). Above rule-secrets (5). Scored 6 -- patterns are simpler than rule-sql's but the adversarial test surface is proportionally smaller too.

---

### 5. Auditability & Traceability

**Key question:** Can operators investigate failures, reproduce review results, and trace the decision path from input to output?

**Score:** 7/10
**Evidence:**
- Each `RuleResult` includes `rule_id`, `severity`, `message`, `file`, `line`, `evidence` (Tier C: lines 62-71).
- **Message includes pattern-specific label:** `f"Weak cryptography: {message}"` where `message` is the tuple label from `_WEAK_PATTERNS` (e.g., "MD5 hash — use SHA-256+", "random module for security — use secrets"). This directly identifies which pattern matched AND provides remediation guidance (Tier C).
- Deterministic: same diff input -> same findings output. Fully reproducible.
- Pattern labels are self-documenting: each `_WEAK_PATTERNS` entry has a human-readable label as the first tuple element (Tier C: lines 12-22).
- `_in_tests_dir()` filtering is explicit and traceable (Tier C: line 55).
- Not 8: No structured error context. No trace correlation IDs.
- Better than rule-sql (6): pattern-specific messages vs generic message. On par with rule-sinks which also uses `f"Dangerous execution sink: {name}"`.
- Calibration: 7 -- above rule-sql (6) and rule-traversal (6) due to pattern-specific actionable messages. Matches rule-workflows (6) base but upgraded because message quality directly aids triage.

---

### 6. Test Quality

**Key question:** Do tests verify meaningful behavior with good coverage?

**Score:** 8/10
**Evidence:**
- **Test count:** 24 tests across 4 test classes (Tier A: test_grippy_rule_weak_crypto.py).
- **Source:test ratio:** 2.81:1 (205 LOC tests / 73 LOC source).
- **Fixture matrix categories covered:**
  - Positive: 11 tests (2 hash + 3 cipher + 1 mode + 5 random variants). Covers all 7 `_WEAK_PATTERNS` entries and all 6 `random.*` function variants.
  - Negative: 3 tests (sha256 safe, secrets module safe, non-Python ignored).
  - Edge: 3 tests (comment ignored, tests-dir ignored, nested tests-dir ignored).
  - Metadata: 1 test (rule ID + severity).
  - Adversarial: 2 tests (1 ReDoS + 1 long-line).
  - Safe-negatives: 2 tests (AES-GCM safe, secrets.token_bytes safe) -- anchoring specificity.
- **SR-01 complete:** All 7 pattern entries tested, all 6 random variants tested. Strongest SR-01 coverage in the batch.
- Missing categories (F-CRY-001): context-sensitive negatives, HMAC wrapping, renamed files.
- Calibration: rule-secrets scored 6 (14 tests). rule-workflows and rule-sinks scored 7 (15 and 21 tests). rule-crypto scores 8: 24 tests, best test:source ratio, complete pattern coverage, good positive:negative balance (11:5 with safe-negatives).

---

### 7. Convention Adherence

**Key question:** Does the unit follow Grippy project patterns?

**Score:** 9/10
**Evidence:**
- SPDX header present on source and test file (Tier A: file inspection).
- ruff check passes with zero issues (Tier A: static analysis).
- mypy strict passes with zero issues (Tier A: static analysis).
- bandit passes with zero issues (Tier A: static analysis).
- Test file follows mirror structure: `src/grippy/rules/weak_crypto.py` -> `tests/test_grippy_rule_weak_crypto.py` (Tier A).
- Test file exceeds 50 LOC minimum (205 LOC) (Tier A).
- Uses `ctx.added_lines_for()` helper -- consistent with rule-sql and rule-sinks.
- Uses `_is_comment()` for comment filtering -- same pattern as rule-sql.
- Uses `break` for one-finding-per-line -- same pattern as rule-sql and rule-sinks.
- **Design observation:** `_in_tests_dir()` filtering at rule level. This is a convention shared with rule-secrets and rule-creds (grep confirms 3 rules use identical `_in_tests_dir()` implementations). It is NOT an ownership drift -- it's an established per-rule pattern for suppressing noise in test directories where weak crypto/secrets are legitimately used. If this were engine-level, ALL rules would suppress test-dir findings, which is not always desired (e.g., rule-sinks should still flag `eval()` in tests).
- Calibration: matches all prior units at 9.

---

### 8. Documentation Accuracy

**Key question:** Do docstrings, comments, and docs match actual behavior?

**Score:** 7/10
**Evidence:**
- File-level docstring: "Rule 8: weak-crypto -- detect weak hash algorithms, broken ciphers, and insecure RNG." (line 2) -- accurate (Tier C).
- Class docstring: "Detect usage of weak hash algorithms, broken ciphers, and insecure RNG." (line 44) -- accurate (Tier C).
- `_file_ext` has docstring: "Get file extension including the dot." -- accurate (Tier C).
- `_in_tests_dir` has docstring: "Check if path is under a tests directory." -- accurate (Tier C).
- `_is_comment` has docstring: "Check if a line is a Python comment." -- accurate (Tier C).
- Pattern labels in `_WEAK_PATTERNS` are self-documenting: "MD5 hash — use SHA-256+", "RC4/ARC4 cipher — use AES", etc. (Tier C: lines 12-22). Each label names the issue AND suggests remediation.
- Not 9: No usage examples. No documentation of the tests-dir filtering design decision (why this rule suppresses test-dir findings when others don't).
- Calibration: matches all prior units at 7.

---

### 9. Performance

**Key question:** Is the unit efficient for its workload?

**Score:** 8/10
**Evidence:**
- 7 regex patterns compiled once at module load (Tier C: lines 11-22). No per-invocation recompilation.
- Linear scan: O(files x lines x patterns). Each line tested against 7 patterns.
- `break` at line 72 short-circuits after first match per line.
- Two early exits: file extension check (`_file_ext` at line 53) and tests-dir check (`_in_tests_dir` at line 55). Tests-dir check skips entire files, reducing pattern matching work.
- `_is_comment()` check before pattern matching provides early exit for comments (Tier C: line 59).
- `frozenset` for extension lookups: O(1) per file (Tier C: line 24).
- Not 9: No profiling data.
- Calibration: matches all prior units at 8.

---

### 10. Dead Code / Debt

**Key question:** Is the unit free of unused code and tracked debt?

**Score:** 9/10
**Evidence:**
- Zero `TODO` or `FIXME` comments (Tier A: grep search).
- All functions called: `WeakCryptoRule` registered in `RULE_REGISTRY` (registry.py), `_file_ext` at line 53, `_in_tests_dir` at line 55, `_is_comment` at line 59 (Tier C: caller trace).
- All 7 `_WEAK_PATTERNS` entries iterated at line 60 (Tier C).
- ruff detects no unused imports (Tier A).
- Not 10: F-CRY-001 identifies a fixture matrix gap -- not code debt, but tracked.
- Calibration: matches all prior units at 9.

---

### 11. Dependency Hygiene

**Key question:** Are unit boundaries clean with no circular or unnecessary deps?

**Score:** 9/10
**Evidence:**
- 2 internal dependencies: `grippy.rules.base` (RuleResult, RuleSeverity) and `grippy.rules.context` (RuleContext). Both are same-phase (Phase 1) sibling modules (Tier A: import inspection at lines 8-9).
- 1 external dependency: `re` (stdlib) (Tier A: import inspection at line 7).
- No circular imports (Tier A: ruff check).
- Lean imports: only `RuleContext` from context module. Same pattern as rule-sql and rule-sinks.
- Not 10: Has 2 internal dependencies.
- Calibration: matches all prior units at 9.
