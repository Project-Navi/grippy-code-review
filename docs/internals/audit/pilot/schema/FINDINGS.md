<!-- SPDX-License-Identifier: MIT -->

# Audit Findings: schema

**Audit date:** 2026-03-13
**Commit:** cebbcab
**Auditor:** Claude Opus 4.6 (AI draft) / Nelson Spence (human reviewer -- pending)
**Unit type:** data-model (primary)

---

## Strengths

Appreciative inquiry first. The schema module demonstrates several properties worth preserving:

1. **Excellent test:source ratio (1.69:1).** 332 LOC of tests covering 196 LOC of source. 44 tests across 6 test classes with boundary value testing, parametrized cases, and round-trip validation.

2. **Clean static analysis across all tools.** ruff, mypy strict, and bandit all pass with zero issues. The single `# nosec B105` on `VerdictStatus.PASS` (schema.py:53) is correctly justified -- bandit flags the string "PASS" as a potential hardcoded password, which is a false positive on an enum value.

3. **True leaf module with zero internal dependencies.** schema.py imports nothing from `grippy.*`. This makes it the ideal starting point for dependency-ordered auditing and eliminates any risk of circular imports or coupling drift.

4. **Defense-in-depth `_sanitize_file_path` validator** (schema.py:104-108). The `field_validator` on `Finding.file` strips newlines and backticks at parse time, preventing injection via file paths before data reaches downstream consumers (github_review.py comment rendering, mcp_response.py serialization).

5. **StrEnum used everywhere categorical.** All 8 categorical dimensions (Severity, ComplexityTier, FindingCategory, EscalationCategory, EscalationTarget, VerdictStatus, ToneRegister, AsciiArtKey) use `StrEnum`, providing both type safety and JSON-friendly string serialization.

6. **JSON-safe by design.** Zero non-JSON-safe types across all 11 models. No `datetime`, `bytes`, `Path`, or `set` fields. All fields serialize cleanly via `model_dump()` without custom encoders.

7. **Frozen Finding model** (schema.py:95). The `model_config = {"frozen": True}` on Finding prevents accidental mutation after construction. This is the only model that transits trust boundaries in its constructed form (findings flow from retry.py through github_review.py to the GitHub API).

8. **No TODO/FIXME debt.** Zero tracked or untracked debt items in the source.

9. **Clean git history.** 6 commits, no churn. Changes have been intentional and additive.

---

## Evidence Index

| Item ID | Description | Tier | Artifact | Assessment |
|---------|-------------|:----:|----------|------------|
| DM-01 | Parse-time validation rejects invalid data | A | 18 validation tests at test_grippy_schema.py:154-209, :277-301 | **PASS** |
| DM-02 | Required fields not marked Optional; missing data fails loudly | A + C | Frozen model proven at test_grippy_schema.py:324-331; 3 Optional fields inspected at schema.py:114-115, :163 | **GAP (minor)** |
| DM-03 | Enum-like fields use constrained types, not bare strings | C | 8 StrEnum classes, 2 Literal usages; 20 bare str fields analyzed as free-text | **PASS** |
| DM-04 | Serialized output is JSON-safe without custom handling | A | 15 serialization tests at test_grippy_schema.py:252-271; round-trip model_dump -> model_validate proven | **PASS** |
| DM-05 | Graph type definitions match graph store usage | N/A | Zero graph references in schema.py | **N/A** |

---

## Findings

### F-SCH-001: Only Finding model is frozen; other 10 models are mutable

**Severity:** LOW
**Status:** OPEN
**File:** `src/grippy/schema.py:95`
**Evidence tier:** C (code inspection)

**Current behavior:**

```python
class Finding(BaseModel):
    model_config = {"frozen": True}
```

Only `Finding` has `frozen=True`. The remaining 10 BaseModel subclasses (`PRMetadata`, `ReviewScope`, `Escalation`, `ScoreBreakdown`, `ScoreDeductions`, `Score`, `Verdict`, `Personality`, `ReviewMeta`, `GrippyReview`) are mutable by default.

**Why it matters:**

This is intentional -- `GrippyReview` and its nested models are constructed incrementally during review pipeline execution (retry.py builds partial state). However, this design decision is undocumented. A future contributor could reasonably freeze additional models not realizing the incremental construction pattern depends on mutability.

**Suggested improvement:**

Add a brief comment near the `Finding` frozen declaration explaining the asymmetry:

```python
class Finding(BaseModel):
    # Frozen: findings transit trust boundaries (retry -> github_review -> GitHub API)
    # and must not be mutated after construction. Other models remain mutable for
    # incremental construction during the review pipeline.
    model_config = {"frozen": True}
```

No code change required. Documentation-only.

---

### F-SCH-002: No test for missing required field rejection on GrippyReview

**Severity:** LOW
**Status:** OPEN
**File:** `tests/test_grippy_schema.py`
**Evidence tier:** C (test gap analysis)

**Current behavior:**

The test suite validates field constraints (max_length, ge/le boundaries), optional field behavior, round-trip serialization, and frozen model enforcement. However, no test explicitly verifies that omitting a required field from `GrippyReview` (or any model) raises `ValidationError`.

**Why it matters:**

This is a DM-01 gap. Pydantic provides this guarantee by default, so the risk is low -- the behavior is framework-guaranteed rather than application-implemented. However, an explicit test would serve as a regression guard if field optionality changes in the future.

**Suggested improvement:**

Add a parametrized test covering omission of 2-3 required fields:

```python
@pytest.mark.parametrize("field", ["audit_type", "pr", "findings"])
def test_missing_required_field_rejected(self, field: str) -> None:
    data = _minimal_review()
    del data[field]
    with pytest.raises(ValidationError):
        GrippyReview(**data)
```

Approximately 5 LOC. Low priority.

---

### F-SCH-003: Finding.id and Escalation.id use bare str (intentional)

**Severity:** LOW
**Status:** OPEN
**File:** `src/grippy/schema.py:97, :121`
**Evidence tier:** C (code inspection + design rationale)

**Current behavior:**

```python
# Finding
id: str = Field(description="F-001 through F-999")

# Escalation
id: str = Field(description="E-001 through E-099")
```

Both `id` fields are bare `str` despite having documented patterns (`F-NNN`, `E-NNN`). No `pattern` constraint or validator enforces the format.

**Why it matters:**

This is intentional for LLM output tolerance. LLMs occasionally produce IDs like `F-1`, `F001`, or `finding-001`. Strict pattern validation would cause retry loops on cosmetically non-conformant but semantically valid output. The `Field(description=...)` serves as a soft guide for the LLM prompt.

No action recommended. Documenting for audit completeness.

---

## Compound Chain Exposure

**None identified.** schema.py defines data structures consumed at trust boundaries but does not own boundary logic. It is a pure type definition layer -- data flows through it but no processing, I/O, or decision-making occurs within the module. The `_sanitize_file_path` validator (schema.py:104-108) is a defensive measure that reduces attack surface at parse time, but the primary boundary defenses live in the consuming modules (agent.py `_escape_xml`, github_review.py 5-stage sanitization, retry.py `_safe_error_summary`).

---

## Hypotheses

None. All observations during this audit produced sufficient evidence for classification as findings or were resolved through code inspection.
