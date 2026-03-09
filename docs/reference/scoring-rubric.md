# Scoring Rubric

Every PR reviewed by Grippy receives a numerical score out of 100, calculated from findings across 5 dimensions. The score drives the verdict (PASS / PROVISIONAL / FAIL), which determines whether the PR is merge-blocking.

---

## Dimensions

Grippy evaluates code across 5 categories. Each finding is classified into exactly one category.

| Dimension | What It Covers | Max Deduction |
|-----------|---------------|---------------|
| **Security** | Auth bypass, injection, secrets exposure, crypto misuse, IDOR, input validation | -50 |
| **Logic** | Incorrect behavior, off-by-one errors, race conditions, wrong return values, missing edge cases | -30 |
| **Governance** | Architectural violations, missing documentation, license headers, naming conventions, structural rules from `.grippy.yaml` | -30 |
| **Reliability** | Missing error handling, swallowed exceptions, no retry logic on external calls, resource leaks, missing timeouts | -20 |
| **Observability** | Missing logging, no metrics, absent tracing, no alerting hooks, silent failures | -15 |

Each category has a **deduction cap** that prevents a single dimension from tanking the entire score. Even if security has 10 critical findings, the security dimension can only deduct a maximum of 50 points total.

The theoretical minimum score is 0 (the score floors at 0, never goes negative).

---

## Severity Definitions

Every finding is assigned one of 4 severity levels. Each level has a strict definition, a confidence minimum, and a point deduction.

### CRITICAL

**Impact:** Will cause data loss, security breach, or service outage in production.

**Examples:** SQL injection, auth bypass, unencrypted secrets in code, data corruption path.

| Property | Value |
|----------|-------|
| Score deduction | **-25 points** per finding |
| Merge blocking | **Always** |
| Confidence minimum | 80 (findings below 80 confidence are not reported at CRITICAL) |

### HIGH

**Impact:** Will cause significant degradation, data integrity issues, or compliance violations.

**Examples:** Missing input validation on user-facing endpoints, IDOR vulnerability, missing error handling on payment paths, governance rule violations.

| Property | Value |
|----------|-------|
| Score deduction | **-15 points** per finding |
| Merge blocking | **Yes** --- when 2+ HIGH findings, or combined with any CRITICAL |
| Confidence minimum | 75 |

### MEDIUM

**Impact:** Will cause degraded experience, technical debt, or operational difficulty.

**Examples:** Missing observability, swallowed exceptions, hardcoded values that should be config, missing retry logic on external calls.

| Property | Value |
|----------|-------|
| Score deduction | **-5 points** per finding |
| Merge blocking | **No** --- advisory only |
| Confidence minimum | 75 |

### LOW

**Impact:** Minor improvement opportunity. No production risk.

**Examples:** Code style inconsistency covered by governance rules, missing documentation, naming conventions.

| Property | Value |
|----------|-------|
| Score deduction | **-2 points** per finding |
| Merge blocking | **No** --- advisory only |
| Confidence minimum | 65 |

---

## Confidence Scoring

Every finding gets a confidence score from 0-100. This represents Grippy's confidence that the finding is real, not the severity of the issue.

| Confidence | Meaning | What Grippy Can Prove |
|------------|---------|----------------------|
| 95-100 | Certain | Exact line, exact failure mode, reproducible |
| 85-94 | Very High | Clear evidence, minor context dependency |
| 75-84 | High | Strong evidence, but runtime behavior could mitigate |
| 65-74 | Moderate | Pattern match, but needs human to verify context |
| 50-64 | Low | Suspicious, but could be intentional or mitigated elsewhere |
| Below 50 | Noise | **Not reported** |

The confidence filter uses per-severity thresholds:

| Severity | Minimum Confidence |
|----------|-------------------|
| CRITICAL | 80 |
| HIGH | 75 |
| MEDIUM | 75 |
| LOW | 65 |

Findings below their severity's threshold are not reported.

### Confidence Calibration

Two adjustments apply before threshold comparison:

- **Category penalty:** Governance and observability findings subtract 15 from their raw confidence. A governance finding at 90% raw confidence becomes 75% after adjustment. This prevents style opinions from competing with concrete vulnerabilities for attention.
- **Specificity ceiling:** Findings about what SHOULD exist (missing error handling, missing logging) rather than what WILL break (SQL injection, auth bypass) are capped at 80 confidence regardless of certainty.

These adjustments stack: a governance "missing pattern" finding at 95% raw → min(95 - 15, 80) = 80.

---

## Deduction Rules

The overall score starts at 100 and deducts based on findings:

```
score = 100 - sum(finding_deductions)
score = max(score, 0)
```

**Deduction caps per category** prevent one dimension from dominating the score:

| Category | Max Deduction |
|----------|--------------|
| Security | -50 |
| Logic | -30 |
| Governance | -30 |
| Reliability | -20 |
| Observability | -15 |

**Example calculation:**

A PR with 1 CRITICAL security finding (-25), 1 HIGH logic finding (-15), and 2 MEDIUM reliability findings (-10):

```
100 - 25 - 15 - 10 = 50/100
```

---

## Finding Deduplication

Before scoring, Grippy deduplicates findings:

1. Group findings by file + line range + category
2. If multiple findings overlap the same code, keep the highest severity
3. If findings share the same root cause, merge into one finding with combined evidence
4. Never double-count the same issue

---

## Finding Caps

Noise reduction limits prevent wall-of-findings fatigue:

- Maximum **5 findings per file** (keep highest severity)
- Maximum **20 findings per review** (keep highest severity, then highest confidence)
- Maximum **3 LOW findings total** (developers ignore walls of nits)

---

## Verdict Thresholds

The verdict is determined by comparing the overall score against the **pass threshold** for the active review mode.

### Thresholds by Mode

| Context | Pass Threshold |
|---------|---------------|
| Standard PR review | 70 |
| Security audit mode | 85 |
| Governance audit mode | 70 |
| Surprise audit ("production ready") | 85 |
| Release branch | 80 |
| Hotfix branch | 75 |

### Verdict Statuses

| Verdict | Condition | Meaning |
|---------|-----------|---------|
| **PASS** | Score >= threshold | PR meets quality standards. Merge allowed. |
| **PROVISIONAL** | Score >= (threshold - 20) and < threshold | PR is close but has issues. Merge allowed with warnings. |
| **FAIL** | Score < (threshold - 20) | PR does not meet quality standards. Merge blocked. |

These are represented in the codebase as the `VerdictStatus` enum with values `PASS`, `PROVISIONAL`, and `FAIL`.

---

## Rule Engine Gate vs. Score

The deterministic rule engine and the LLM scoring system are **separate mechanisms**:

- **Rule engine gate** --- A binary pass/fail based on the maximum rule finding severity and the active profile threshold. Controlled by `GRIPPY_PROFILE`. When the gate fails, CI exits non-zero **regardless of the numeric score**.
- **LLM scoring** --- The 0-100 score computed from LLM-generated findings per the deduction rules above.

Rule severity levels (`INFO`, `WARN`, `ERROR`, `CRITICAL`) do NOT directly become score deductions. Instead:
1. The rule engine detects findings and injects them into the LLM prompt
2. The LLM generates corresponding `Finding` objects with `schema.Severity` levels (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`)
3. Those LLM-generated findings drive the normal deduction calculation
4. The rule gate is evaluated independently --- it can fail CI even if the LLM gives a high score

| Profile | Gate fails on | Score effect |
|---|---|---|
| `general` | --- (rules off) | LLM-only scoring |
| `security` | ERROR or CRITICAL rule findings | CI fails independently of score |
| `strict-security` | WARN+ rule findings | CI fails independently of score |

Each `Finding` in the output includes a `rule_id` field (optional) that links LLM-generated findings back to deterministic rule engine findings. The retry validation pipeline (`_validate_rule_coverage()`) ensures all rule findings appear in the output with `rule_id` set.

---

## Merge Blocking

The `merge_blocking` flag on the verdict is set to `true` when:

- **Any CRITICAL finding** is present (regardless of score)
- **The verdict is FAIL** (score below the fail threshold)
- **2+ HIGH findings** are present, or HIGH findings combined with any CRITICAL

When `merge_blocking` is true and Grippy is configured as a required status check, the PR cannot be merged until the blocking findings are resolved.

---

## Score Interpretation

Grippy's personality tone adjusts based on the score:

| Score | Grippy's Assessment | Tone |
|-------|--------------------|----- |
| 90-100 | Clean | Grudging respect |
| 80-89 | Solid with minor notes | Mild, professional |
| 70-79 | Acceptable with caveats | Standard grumpy |
| 60-69 | Below standard | Disappointed |
| 40-59 | Significant issues | Frustrated, direct |
| 20-39 | Not ready | Alarmed, professional |
| 0-19 | Reject | Direct, urgent, no personality |

---

## Structured Output

The score is part of the full `GrippyReview` JSON output, structured as:

```python
class Score(BaseModel):
    overall: int          # 0-100, the final score
    breakdown: ScoreBreakdown  # per-dimension scores
    deductions: ScoreDeductions  # counts by severity + total deduction

class ScoreBreakdown(BaseModel):
    security: int         # 0-100
    logic: int            # 0-100
    governance: int       # 0-100
    reliability: int      # 0-100
    observability: int    # 0-100

class ScoreDeductions(BaseModel):
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    total_deduction: int
```

The score, breakdown, and deductions are nested inside the top-level `GrippyReview` model alongside findings, verdict, escalations, and personality data. See [Architecture](../explanation/architecture.md) for the full data model.

---

## Score Presentation

The summary comment posted to the PR includes the score in this format:

```
Score: 82/100 -- PASS

Findings:
  CRITICAL: 0
  HIGH:     1
  MEDIUM:   2
  LOW:      1

Reviewed: 12/14 files (86%)
```
