<!-- SPDX-License-Identifier: MIT -->

# Audit Findings: rule-secrets

**Audit date:** 2026-03-13
**Commit:** 259d0b8
**Auditor:** Claude Opus 4.6 (AI draft) / Nelson Spence (human reviewer -- pending)
**Unit type:** security-rule (primary)

---

## Strengths

1. **Complete positive fixture coverage.** All 10 regex patterns have corresponding positive test fixtures: AWS, GitHub (classic + fine-grained + 4 token types), OpenAI, private key header, generic secret assignment, .env file addition. 14 tests, all passing.

2. **Clean static analysis trifecta.** ruff, mypy strict, and bandit all pass with zero issues. 106 lines of code, no skipped checks.

3. **Built-in redaction.** `_redact()` (secrets_in_diff.py:133-138) ensures finding evidence never contains full secret values. Only the first 4-8 characters are preserved. Proven by `test_evidence_is_redacted`.

4. **Multi-layer false positive reduction.** Three independent filters prevent false positives: `_is_comment_line()` skips hash/slash/star comments (line 60-63), `_is_placeholder()` checks against 15 known placeholder values (line 66-69), `_in_tests_dir()` skips test files entirely (line 72-74). Each has dedicated test coverage.

5. **Efficient early-exit design.** `break` statements at lines 106-107 (one finding per .env file) and line 129 (one finding per diff line) prevent finding spam. `line.type != "add"` check at line 112 skips non-addition lines immediately.

6. **Compiled regex patterns.** All 10 patterns use `re.compile()` at module load time (line 12-37), avoiding recompilation per diff line.

7. **Single commit, no churn.** Introduced in `5f9a6cc` and hasn't changed since. Stable implementation.

---

## Evidence Index

| Item ID | Description | Tier | Artifact | Assessment |
|---------|-------------|:----:|----------|------------|
| SR-01 | Rule detects all documented patterns | A | 8 positive tests: test_aws_key, test_github_classic_pat, test_github_fine_grained_pat, test_github_other_tokens, test_openai_key, test_private_key_header, test_generic_secret_assignment, test_env_file_addition | **PASS** |
| SR-02 | No catastrophic backtracking | C | Manual regex analysis (see F-RS-001) — no Tier A adversarial tests exist | **GAP** |
| SR-03 | Severity matches profile gates | A + C | All 10 patterns assign CRITICAL (secrets_in_diff.py:14-36). .env assigns WARN (line 99). Severity assignment is unconditional — profile gating is engine-level. | **PASS** |
| SR-04 | Only fires on added lines | A | test_context_line_not_flagged (line 97-108): context line with secret pattern produces no finding. Code guard at line 112: `if line.type != "add"`. | **PASS** |
| SR-05 | Finding evidence preserves triage context | C | RuleResult fields populated: rule_id (line 98/119), severity (line 99/122), message (line 100/123), file (line 101/124), line (line 102/125), evidence (line 103/126). All fields present and meaningful. | **PASS** |
| SR-06 | Rule respects profile activation | C | Rule has no profile-awareness — activation is engine-level (registry.py imports, engine selects per profile). N/A at rule level — see friction log. | **N/A (engine scope)** |
| SR-07 | Finding messages never contain raw secrets | A | test_evidence_is_redacted (line 110-116): proves evidence ends with "..." and length < 20. `_redact()` shows only first 4-8 chars. | **PASS** |
| SR-08 | Findings compatible with enrichment | C | Rule returns `list[RuleResult]` which is the standard type consumed by `enrich_results()`. No integration test at rule level. | **PASS (structural)** |
| SR-09 | Fixture matrix coverage | C | See F-RS-002 for gap analysis | **PARTIAL** |

---

## Findings

### F-RS-001: No adversarial/ReDoS test coverage for regex patterns (SR-02)

**Severity:** MEDIUM (downgraded from HIGH during adjudication — gap is absence of Tier A proof, not a demonstrated correctness/security failure)
**Status:** OPEN
**File:** `tests/test_grippy_rule_secrets.py`
**Evidence tier:** C (manual regex analysis; Tier A requires test evidence)

**Current behavior:**

No test exercises the 10 regex patterns with adversarial-length input (100K+ characters). SR-02 requires Tier A evidence (test).

**Manual analysis of regex patterns:**

| Pattern | ReDoS Risk | Rationale |
|---------|:----------:|-----------|
| `-----BEGIN.*PRIVATE KEY-----` | Low | `.*` is greedy but bounded by literal anchors. Applied per-line, not multi-line. |
| `AKIA[0-9A-Z]{16}` | None | Fixed-width character class. |
| `ghp_[a-zA-Z0-9]{36}` (and 5 similar) | None | Fixed-width character class. |
| `sk-[a-zA-Z0-9]{20,}` | None | Single character class, no ambiguity. |
| Generic: `(?:token\|...)\s*[:=]\s*["']?[^\s"']{12,}` | Low | Groups are non-overlapping. `[^\s"']{12,}` is a single char class. |

**Assessment:** Patterns are structurally safe from catastrophic backtracking based on manual analysis. However, without Tier A test evidence, this remains a gap per the evidence discipline requirement.

**Suggested improvement:**

Add a parametrized adversarial test:

```python
@pytest.mark.parametrize("pattern_idx", range(10))
def test_no_backtracking_on_long_input(self, pattern_idx: int) -> None:
    long_line = "x" * 200_000
    diff = _make_diff("config.py", long_line)
    # Should complete in <1s, not hang
    SecretsInDiffRule().run(_ctx(diff))
```

~10 LOC.

---

### F-RS-002: Fixture matrix missing several categories (SR-09)

**Severity:** MEDIUM
**Status:** OPEN
**File:** `tests/test_grippy_rule_secrets.py`
**Evidence tier:** C (test file review)

**Coverage matrix:**

| Category | Present? | Tests |
|----------|:--------:|-------|
| Positive fixtures (known secret patterns) | Yes | 8 tests |
| Negative fixtures (non-secret patterns) | Yes | 3 tests (comment, 2 placeholders) |
| Diff-line filtering (added-only) | Yes | 2 tests (tests dir, context line) |
| Output safety (redaction) | Yes | 1 test |
| Adversarial input (long, Unicode, nested) | **No** | — |
| Renamed/binary/submodule diffs | **No** | — |
| Suppression by `.grippyignore` | N/A | Engine-level, not rule-level |
| Suppression by `# nogrip` | N/A | Engine-level, not rule-level |

**Why it matters:** Missing adversarial and edge-case diff format categories mean the rule's behavior on unusual inputs is unproven by tests.

**Suggested improvement:** Add 3-5 tests for adversarial/edge inputs: Unicode in secret values, very long lines, binary diff markers, renamed file diffs. ~20 LOC.

---

### F-RS-003: `_is_comment_line` misses multi-line comment bodies and CSS/HTML comments

**Severity:** LOW
**Status:** OPEN
**File:** `src/grippy/rules/secrets_in_diff.py:60-63`
**Evidence tier:** C (code inspection)

**Current behavior:**

```python
def _is_comment_line(content: str) -> bool:
    stripped = content.strip()
    return stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("*")
```

This catches Python/shell (`#`), C/JS (`//`), and multi-line comment bodies (`*`), but misses:
- HTML/XML comments: `<!-- ... -->`
- CSS comments not starting with `*`: `/* ... */` (first line)
- Lua/SQL comments: `--`

**Why it matters:** A secret in an HTML comment could be flagged when it should be suppressed. Low severity because comment-line secrets are still worth flagging in most cases — the false positive is arguably a feature.

**Suggested improvement:** Consider adding `<!--` and `--` patterns. Low priority.

---

## Compound Chain Exposure

**None identified.** rule-secrets operates within the diff ingestion boundary (TB-2) but is not an anchor owner for that boundary. The rule engine (rule-engine unit) owns TB-2. rule-secrets is a pure pattern detector: it receives parsed diff context, scans for patterns, and returns findings. It does not compose prompts, post to APIs, or manage state. No trust-boundary-owned behavior exists in this unit.

---

## Hypotheses

None. All observations during this audit produced sufficient evidence for classification as findings or were resolved through code inspection.
