<!-- SPDX-License-Identifier: MIT -->

# Audit Scorecard: rule-creds

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
| Multi-HIGH block | 2+ unresolved HIGH findings (including provisional) | No (1 HIGH finding — see F-CRD-001) |
| Security collapse | Security Posture < 2 | No (score: 8) |
| Adversarial collapse | Adversarial Resilience < 2 | No (score: 6) |

### Ceiling Gates (cap the best allowed status)

| Ceiling Gate | Condition | Fired? |
|---|---|---|
| Severity cap | Any unresolved HIGH finding | **Yes — F-CRD-001 RESOLVED in this commit** |
| Security hard floor | Security Posture < 4 | No (score: 8) |
| Adversarial hard floor | Adversarial Resilience < 4 | No (score: 6) |
| Security soft floor | Security Posture < 6 | No (score: 8) |
| Adversarial soft floor | Adversarial Resilience < 6 | No (score: 6) |
| Accepted critical risk | Any ACCEPTED_RISK at CRITICAL | No |
| Accepted high risk | Any ACCEPTED_RISK at HIGH | No |

---

## Summary

| Dimension | Score | Evidence Tier | Notes |
|-----------|------:|:---:|-------|
| 1. Contract Fidelity | 7/10 | A | All functions typed, mypy strict clean, RuleResult/RuleContext used correctly |
| 2. Robustness | 7/10 | A + C | Multi-layer false-positive suppression (env vars, placeholders, empty strings, comments, test dirs). `break` per line. |
| 3. Security Posture | 8/10 | A + C | **SR-07 focus.** `_redact()` covers both credential assignments AND auth header tokens (fixed in this commit). Evidence truncated at 120 chars. |
| 4. Adversarial Resilience | 6/10 | A + C | ReDoS tests on all 3 detection patterns (Tier A). 1MB long-line tolerance (Tier A). No evasion fixtures. |
| 5. Auditability & Traceability | 6/10 | C | Generic message. Redacted evidence preserves enough context without leaking values. |
| 6. Test Quality | 8/10 | A | 24 tests. Positive (4), negative (5), edge (1), metadata (1), adversarial (4), redaction (3), pattern coverage (3), safe-negatives (3). |
| 7. Convention Adherence | 9/10 | A | ruff, mypy strict, bandit clean. SPDX header. Uses `ctx.added_lines_for()` + `_in_tests_dir()`. |
| 8. Documentation Accuracy | 7/10 | C | Accurate docstrings. Inline comments on patterns. `_redact()` docstring matches post-fix behavior. |
| 9. Performance | 8/10 | C | Compiled regexes, linear scan, `break` per line. Multi-layer early exits. |
| 10. Dead Code / Debt | 9/10 | A + C | Zero TODOs, all functions called, all patterns used. |
| 11. Dependency Hygiene | 9/10 | A | 2 internal deps (rules.base, rules.context) -- same phase. No circular deps. |
| **Overall** | **7.6/10** | | **Average of 11 dimensions** |

**Health status:** Adequate (provisional)

**Determination:**
1. Average-based status: 7.6/10 falls in 6.0-7.9 range = Adequate
2. Override gates: None fired (F-CRD-001 resolved).
3. Ceiling gates: None currently firing. F-CRD-001 was resolved in audit commit 8957771.
4. Suffixes: `(provisional)` -- dims 5, 8, 9 include Tier C evidence components.

**Override gates fired:** None
**Ceiling gates fired:** None (F-CRD-001 resolved)

---

## Checklist: SR-01 through SR-09

| ID | Verdict | Evidence | Notes |
|----|---------|----------|-------|
| SR-01 | PASS | Tier A: 4 positive tests in original suite (`test_password_string`, `test_db_connection_string`, `test_auth_header`, `test_rule_metadata`) + 3 pattern coverage tests (`test_mysql_conn_string`, `test_basic_auth_header`, `test_secret_keyword`). All 3 detection patterns exercised: `_CREDENTIAL_ASSIGN`, `_CONN_STRING`, `_AUTH_HEADER`. 5 negative tests (env var safe, getenv safe, placeholder safe, empty string safe, test dir skipped). | Comprehensive pattern × suppression matrix. |
| SR-02 | PASS | Tier A: 3 ReDoS tests exercise all 3 detection patterns: `test_redos_credential_assign` — 100K chars against `_CREDENTIAL_ASSIGN`. `test_redos_conn_string` — 100K chars against `_CONN_STRING`. `test_redos_auth_header` — 100K chars against `_AUTH_HEADER`. `test_extremely_long_line` — >1MB line through full `rule.run()`. All complete under 5s timeout. | All patterns structurally safe: bounded by negated character classes (`[^"']`) or literal anchors (`://`, `@`). |
| SR-03 | PASS | Tier A: `test_password_string` asserts `results[0].severity == RuleSeverity.ERROR`. Tier C: `default_severity = RuleSeverity.ERROR` (line 78), used consistently. | ERROR severity. |
| SR-04 | PASS | Tier C: `ctx.added_lines_for(f.path)` at line 87 — uses the engine's canonical added-line filter. Same as rule-sql, rule-crypto, rule-deser. | Standard helper. |
| SR-05 | PASS | Tier C: All `RuleResult` instances include `rule_id`, `severity`, `message`, `file`, `line`, `evidence=self._redact(content.strip())` (lines 96-108). Evidence is redacted AND truncated at 120 chars. | **Redaction is the key quality gate for this rule.** |
| SR-06 | N/A | Ownership: engine-owned. | Per SR-06 scope note. |
| SR-07 | **PASS (post-fix)** | **Tier A: 3 redaction tests prove no raw secrets in evidence.** `test_password_value_redacted` — asserts `"hunter2secret" not in results[0].evidence` and `"****" in results[0].evidence`. `test_conn_string_value_redacted` — asserts `"s3cret" not in results[0].evidence`. `test_auth_header_token_redacted` — asserts `"eyJhbGciOiJIUzI1NiJ9" not in results[0].evidence`. **F-CRD-001 was a genuine pre-existing gap:** the original `_redact()` only covered `=\s*["']...['""]` pattern, missing auth header tokens. Fixed by adding a second `re.sub` for `(Bearer\|Basic\|Token)\s+[token-chars]{8,}`. | **This is the audit's first genuine code-level security finding.** SR-07 is now PASS with Tier A evidence. |
| SR-08 | PASS | Tier C: All findings use standard `RuleResult` dataclass. Fields compatible with `ResultEnrichment` post-processing. | Standard format. |
| SR-09 | PASS | Tier A: Positive (4 + 3 coverage = 7), negative (5: env var, getenv, placeholder, empty, test dir), edge (1: comment ignored), metadata (1), adversarial (4: 3 ReDoS + 1 long-line), redaction (3: password, conn string, auth header). **24 tests total — highest test count in the batch.** Missing: renamed/binary files, multi-DB connection strings. | Strong matrix. 24 tests with balanced category representation. |

**N/A items:** 1/9 (SR-06 only).

---

## Findings

### F-CRD-001: Auth header tokens not redacted in finding evidence (RESOLVED)

**Severity:** HIGH
**Status:** RESOLVED (commit 8957771)
**Checklist:** SR-07
**Evidence tier:** A (test `test_auth_header_token_redacted` failed before fix, passes after)

**Description:** The `_redact()` method (line 113) originally contained only one `re.sub` pattern:
```python
return re.sub(r"""(=\s*["'])[^"']{4,}(["'])""", r"\1****\2", line)[:120]
```
This regex matches `password = "value"` patterns but does NOT match auth header lines like `headers = {"Authorization": "Bearer eyJhbGciOi..."}` because the `=` is followed by ` {` (space then brace), not a quote character. Bearer/Basic/Token values in Authorization headers were exposed verbatim in finding evidence. <!-- pragma: allowlist secret -->

**Fix applied:**
```python
line = re.sub(r"""(=\s*["'])[^"']{4,}(["'])""", r"\1****\2", line)
line = re.sub(
    r"""((?:Bearer|Basic|Token)\s+)[a-zA-Z0-9_.+/=-]{8,}""",
    r"\1****",
    line,
)
return line[:120]
```

**Impact:** HIGH — Bearer tokens, Basic auth credentials, and Token values appeared in finding evidence. Evidence is passed to the enrichment layer and ultimately to LLM prompts and GitHub PR comments. Token exposure in any of these outputs is a security leak.

**Verification:** 3 Tier A redaction tests now pass, proving password values, connection string credentials, and auth header tokens are all redacted.

### Compound Chain Exposure

`F-CRD-001 was a compound chain exposure` — unredacted tokens in evidence → enrichment layer → LLM prompt composition → GitHub PR comment posting. The token could traverse TB-1 (PR metadata ingress), TB-3 (prompt composition), and TB-6 (GitHub posting boundary). The fix at the rule level (evidence generation) prevents the token from entering the chain at all.

---

## Dimension Details

### 1. Contract Fidelity

**Key question:** Do types, exports, and validation faithfully represent the unit's contract?

**Score:** 7/10
**Evidence:**
- mypy strict passes with zero issues (Tier A: static analysis).
- All functions fully typed: `run(self, ctx: RuleContext) -> list[RuleResult]`, `_redact(line: str) -> str`, helper functions (`_file_ext`, `_is_comment`, `_in_tests_dir`, `_is_placeholder`, `_is_empty_string`) all fully typed (Tier A: mypy proves this).
- Rule follows duck-typed Rule protocol: exposes `id`, `description`, `default_severity`, `run()`.
- `_PLACEHOLDERS` frozenset, `_PYTHON_EXTENSIONS` frozenset — clean immutable data.
- Not 9: No explicit Protocol class. No runtime type checks.
- Calibration: matches rule-secrets (7), rule-sql (7), rule-traversal (7).

---

### 2. Robustness

**Key question:** Does the unit handle errors, retries, and edge cases correctly?

**Score:** 7/10
**Evidence:**
- **Multi-layer false-positive suppression** — the strongest in any rule unit:
  1. File extension filter (line 83): only `.py` files.
  2. Test directory skip (line 85): `_in_tests_dir()`.
  3. Comment skip (line 88): `_is_comment()`.
  4. Env var exemption (line 90): `_ENV_VAR_RE.search()`.
  5. Placeholder/empty string exemption (line 92): `_is_placeholder()`, `_is_empty_string()`.
- `break` at line 109 limits to one finding per line.
- `_redact()` ensures even on false positives, actual credential values are masked.
- >1MB line tolerance proven (Tier A: `test_extremely_long_line`).
- No bounds on total result count.
- **Above 6** because the suppression pipeline is more sophisticated than typical rules. 5 suppression layers vs 1-2 in most rules.
- Calibration: above rule-sql (6), rule-traversal (6). The multi-layer suppression design justifies 7.

---

### 3. Security Posture

**Key question:** Does the unit protect against injection, leakage, and unauthorized access?

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 8/10
**Evidence:**
- No I/O, no network, no subprocess, no logging (Tier C: module-level inspection).
- **`_redact()` is the security-critical function (Tier A):** 3 redaction tests prove credential values, connection string passwords, and auth header tokens are all replaced with `****` before entering evidence. This is defense-in-depth — even if downstream systems mishandle evidence, credentials are not present.
- Evidence truncated at 120 chars (`return line[:120]`) after redaction — prevents long lines from carrying additional context.
- Uses `ctx.added_lines_for(path)` — canonical added-line filter (Tier C).
- `_in_tests_dir()` suppresses findings in test directories — prevents false positives on test fixtures with fake credentials.
- F-CRD-001 was found and fixed in this audit — the fix is proven by Tier A tests.
- **Above 7** because `_redact()` is a deliberate security mechanism that other credential-adjacent rules lack. The compound chain exposure analysis (evidence → enrichment → prompt → GitHub) demonstrates defense-in-depth thinking.
- Calibration: above rule-sql (7), rule-traversal (7). The redaction mechanism is a genuine security feature, not just absence of risk.

---

### 4. Adversarial Resilience

**Key question:** Can the unit resist adversarial input from untrusted PR content and prompt injection?

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 6/10
**Evidence:**
- **ReDoS defense (Tier A):** 3 ReDoS tests exercise all 3 detection patterns. `_CREDENTIAL_ASSIGN` uses `[^"']{4,}` — bounded by negated character class, structurally safe. `_CONN_STRING` uses `[^:]+:[^@]+@` — bounded by negated character classes. `_AUTH_HEADER` uses `[a-zA-Z0-9_.+/=-]{8,}` — bounded by character class. All complete under 5s.
- **Large input tolerance (Tier A):** >1MB line through full rule.run().
- **Redaction resilience (Tier A):** `_redact()` cannot be bypassed by input crafting — both `re.sub` patterns run unconditionally on all evidence.
- Not 7: No evasion fixtures (base64-encoded credentials, multi-line connection strings, Unicode password values). No false-positive injection tests (crafting input to trigger false positives that waste reviewer time).
- Calibration: matches rule-sql (6), rule-traversal (6). Redaction adds a security dimension but Dim 4 measures adversarial resilience of detection, not security posture.

---

### 5. Auditability & Traceability

**Key question:** Can operators investigate failures, reproduce review results, and trace the decision path from input to output?

**Score:** 6/10
**Evidence:**
- Each `RuleResult` includes `rule_id`, `severity`, `message`, `file`, `line`, `evidence` (Tier C: code inspection at lines 96-108).
- Message is generic: "Hardcoded credential — use environment variables or a secrets manager" — does not identify which pattern (credential assign, conn string, auth header) matched (Tier C).
- Evidence is redacted — provides enough context for triage (you can see it's a password assignment or auth header) without leaking values.
- Deterministic: same diff input → same findings output. Fully reproducible.
- `break` at line 109: first pattern match wins. Finding doesn't reveal which specific pattern triggered.
- Not 7: Generic message. Could identify pattern type for better triage.
- Calibration: matches rule-sql (6), rule-llm-sinks (6). Below rule-ci-risk (7) which has pattern-specific messages.

---

### 6. Test Quality

**Key question:** Do tests verify meaningful behavior with good coverage?

**Score:** 8/10
**Evidence:**
- **Test count:** 24 tests across 5 test classes (Tier A: test_grippy_rule_hardcoded_credentials.py).
- **Source:test ratio:** 1.76:1 (215 LOC tests / 122 LOC source).
- **Fixture matrix categories covered:**
  - Positive: 4 tests (password string, DB connection string, auth header, rule metadata).
  - Negative: 5 tests (env var safe, getenv safe, placeholder safe, empty string safe, test dir skipped).
  - Edge: 1 test (comment ignored).
  - Metadata: 1 test (rule ID + severity).
  - Adversarial: 4 tests (3 ReDoS + 1 long-line).
  - Redaction (SR-07): 3 tests (password value, conn string, auth header token).
  - Pattern coverage: 3 tests (MySQL conn string, Basic auth header, secret keyword).
- **24 tests — highest test count in the batch.** The redaction tests (SR-07) are unique to this rule and justified by F-CRD-001.
- **Above 7** because the test suite covers a security-critical property (redaction) with dedicated Tier A evidence that most rules don't need.
- Calibration: above rule-sql (7: 15 tests), rule-ci-risk (7: 15 tests). Justified by SR-07 redaction evidence and broader category coverage.

---

### 7. Convention Adherence

**Key question:** Does the unit follow Grippy project patterns?

**Score:** 9/10
**Evidence:**
- SPDX header present on source and test file (Tier A: file inspection).
- ruff check passes with zero issues (Tier A: static analysis).
- mypy strict passes with zero issues (Tier A: static analysis).
- bandit passes with zero issues (Tier A: static analysis).
- Test file follows mirror structure: `src/grippy/rules/hardcoded_credentials.py` → `tests/test_grippy_rule_hardcoded_credentials.py` (Tier A).
- Test file exceeds 50 LOC minimum (215 LOC) (Tier A).
- Uses `ctx.added_lines_for()` — canonical helper (same as rule-sql, rule-crypto, rule-deser).
- Uses `_in_tests_dir()` — established convention shared with rule-secrets and rule-crypto.
- Uses `_PLACEHOLDERS` frozenset — similar pattern to TAINT_NAMES in rule-traversal.
- Calibration: matches rule-sql (9), rule-traversal (9).

---

### 8. Documentation Accuracy

**Key question:** Do docstrings, comments, and docs match actual behavior?

**Score:** 7/10
**Evidence:**
- File-level docstring: "Rule 9: hardcoded-credentials -- detect passwords, connection strings, and auth tokens." (line 2) — accurate (Tier C).
- Class docstring: "Detect hardcoded passwords, connection strings, and auth tokens." (line 74) — accurate (Tier C).
- `_redact()` docstring: "Redact credential values from evidence." — accurate post-fix (Tier C).
- Inline comments on each pattern: "password/secret = \"literal\"" (line 11), "Connection strings with embedded credentials" (line 17), "Authorization header with literal token" (line 23), "Safe patterns — env var lookups" (line 29).
- `# pragma: allowlist secret` comments on test fixtures — correct detect-secrets integration (Tier A).
- Not 9: No documentation of the suppression pipeline order. No explanation of `_PLACEHOLDERS` entries.
- Calibration: matches rule-secrets (7), rule-sql (7).

---

### 9. Performance

**Key question:** Is the unit efficient for its workload?

**Score:** 8/10
**Evidence:**
- 4 regex patterns compiled once at module load via `re.compile()` (Tier C: lines 12-30). All use `re.IGNORECASE` where needed.
- `_PLACEHOLDERS` frozenset and `_PYTHON_EXTENSIONS` frozenset — O(1) membership tests (Tier C).
- Multi-layer early exits: extension check → test dir → comment → env var → placeholder/empty → pattern match. Most lines skip quickly.
- Linear scan: O(files × lines × patterns). Each line tested against 3 patterns.
- `break` at line 109 short-circuits after first match per line.
- `_redact()` runs 2 `re.sub` calls only on matched lines — not on every line.
- Not 9: No profiling data. `_is_placeholder()` uses `any()` with linear scan of 10-element frozenset per line.
- Calibration: matches rule-secrets (8), rule-sql (8), rule-traversal (8).

---

### 10. Dead Code / Debt

**Key question:** Is the unit free of unused code and tracked debt?

**Score:** 9/10
**Evidence:**
- Zero `TODO` or `FIXME` comments (Tier A: grep search).
- All functions called: `HardcodedCredentialsRule` registered in `RULE_REGISTRY`, helper functions called in `run()` method (Tier C: caller trace).
- All 4 compiled patterns used: `_CREDENTIAL_ASSIGN`, `_CONN_STRING`, `_AUTH_HEADER` at line 94, `_ENV_VAR_RE` at line 90 (Tier C).
- `_PLACEHOLDERS` used at line 66, `_PYTHON_EXTENSIONS` used at line 83 (Tier C).
- ruff detects no unused imports (Tier A).
- Not 10: F-CRD-001 was found and resolved — no residual debt.
- Calibration: matches rule-secrets (9), rule-sql (9), rule-traversal (9).

---

### 11. Dependency Hygiene

**Key question:** Are unit boundaries clean with no circular or unnecessary deps?

**Score:** 9/10
**Evidence:**
- 2 internal dependencies: `grippy.rules.base` (RuleResult, RuleSeverity) and `grippy.rules.context` (RuleContext). Both are same-phase (Phase 1) sibling modules (Tier A: import inspection at lines 8-9).
- 1 external dependency: `re` (stdlib) (Tier A: import inspection at line 6).
- No circular imports (Tier A: ruff check).
- Lean imports: only `RuleContext` from context module. Same pattern as rule-sql, rule-crypto.
- Not 10: Has 2 internal dependencies. Necessary and clean but not zero.
- Calibration: matches rule-secrets (9), rule-sql (9), rule-traversal (9).
