<!-- SPDX-License-Identifier: MIT -->

# Test Coverage Assessment: schema

**Audit date:** 2026-03-13
**Commit:** cebbcab
**Auditor:** Claude Opus 4.6 (AI draft) / Nelson Spence (human reviewer -- pending)

---

## 1. Test File Inventory

| Source File | Test File | Source LOC | Test LOC | Tests | Ratio |
|-------------|-----------|----------:|----------:|------:|------:|
| `src/grippy/schema.py` | `tests/test_grippy_schema.py` | 196 (140 code) | 332 | 44 | 1.69:1 |

**Test class breakdown:**

| Test Class | Tests | Lines | Focus |
|------------|------:|------:|-------|
| `TestEnumValues` | 11 | 114-145 | StrEnum value spot-checks |
| `TestFindingConstraints` | 12 | 154-208 | Field constraint validation (ge/le/max_length) |
| `TestOptionalFields` | 4 | 217-243 | Optional/nullable field behavior |
| `TestGrippyReviewRoundTrip` | 15 | 252-318 | Serialization, deserialization, nested validation |
| `TestFindingFrozen` | 1 | 324-331 | Frozen model immutability |
| *(helpers)* | -- | 26-105 | `_minimal_finding()`, `_minimal_review()` fixtures |

Note: `TestGrippyReviewRoundTrip` includes 10 parametrized test cases (5 for breakdown-rejects-negative, 5 for breakdown-rejects-over-100) counted individually.

---

## 2. Coverage Gaps

Gaps are ordered by risk. LOC at risk estimates the source lines whose correctness is unproven by tests.

| Gap ID | Description | Source LOC at Risk | Priority | Finding Ref |
|--------|-------------|---------:|----------|-------------|
| G-01 | No test for missing required field rejection on any model | ~5 | Low | F-SCH-002 |
| G-02 | No direct test for `_sanitize_file_path` validator behavior | ~3 | Low | -- |
| G-03 | No test for invalid enum value rejection (e.g., `Severity("UNKNOWN")`) | ~2 | Low | -- |
| G-04 | No test for `Escalation.severity` Literal constraint rejection | ~1 | Low | -- |

**Total LOC at risk:** ~11 out of 140 code lines (7.9%)

### Gap Details

**G-01: Missing required field rejection.**
No test verifies that omitting a required field from `GrippyReview`, `Finding`, or any other model raises `ValidationError`. Pydantic guarantees this behavior, so the risk is framework regression rather than application bug. Approximately 5 LOC of constructor logic is unproven.

**G-02: `_sanitize_file_path` validator not directly tested.**
The `field_validator` at schema.py:104-108 strips `\n`, `\r`, and backtick from `Finding.file`. No test passes a file path containing these characters and asserts the sanitized output. The validator is exercised indirectly by every test that constructs a `Finding`, but the sanitization behavior itself is not verified. Approximately 3 LOC (the validator body).

**G-03: Invalid enum value rejection.**
No test passes an invalid string (e.g., `"UNKNOWN"`) to a StrEnum field and asserts `ValidationError`. Like G-01, this is framework-guaranteed behavior. Approximately 2 LOC of enum class definition per class, but the risk is negligible since StrEnum + Pydantic provides this for free.

**G-04: Escalation.severity Literal constraint.**
`Escalation.severity` is typed as `Literal["CRITICAL", "HIGH", "MEDIUM"]` (schema.py:122). No test verifies that passing `"LOW"` is rejected. Similar framework guarantee as G-01/G-03. Approximately 1 LOC.

---

## 3. Per-Source Summary

| Source File | Code LOC | Tested Paths | Untested Paths | Estimated Coverage |
|-------------|----------:|:---:|:---:|---:|
| `src/grippy/schema.py` | 140 | Enum values, field constraints (ge/le/max_length), optional fields, round-trip serialization, frozen model, nested model construction | Missing required fields, `_sanitize_file_path` direct behavior, invalid enum values, Literal constraint rejection | ~92% |

**Coverage methodology:** Estimated from test path analysis. No instrumented coverage run was performed during this audit. The estimate is based on mapping each test to the source lines it exercises and identifying unexercised paths.

---

## 4. Recommendations

Ordered by value (gap closure per LOC of test code).

### R-01: Add `_sanitize_file_path` direct test (addresses G-02)

**Priority:** Low
**Estimated effort:** ~8 LOC
**Value:** Proves the only custom validator in the module works as intended.

```python
class TestSanitizeFilePath:
    def test_newlines_stripped(self) -> None:
        f = Finding(**_minimal_finding(file="src/\nmain.py"))
        assert f.file == "src/main.py"

    def test_backticks_stripped(self) -> None:
        f = Finding(**_minimal_finding(file="src/`main`.py"))
        assert f.file == "src/main.py"

    def test_carriage_return_stripped(self) -> None:
        f = Finding(**_minimal_finding(file="src/\rmain.py"))
        assert f.file == "src/main.py"
```

### R-02: Add missing required field rejection test (addresses G-01)

**Priority:** Low
**Estimated effort:** ~7 LOC
**Value:** Regression guard for field optionality changes.

```python
@pytest.mark.parametrize("field", ["audit_type", "pr", "findings", "score", "verdict"])
def test_missing_required_field_rejected(self, field: str) -> None:
    data = _minimal_review()
    del data[field]
    with pytest.raises(ValidationError):
        GrippyReview(**data)
```

### R-03: Add invalid enum rejection test (addresses G-03)

**Priority:** Low
**Estimated effort:** ~5 LOC
**Value:** Minimal -- framework guarantee. Include only for completeness if addressing G-01 and G-02.

```python
def test_invalid_severity_rejected(self) -> None:
    with pytest.raises(ValidationError):
        Finding(**_minimal_finding(severity="UNKNOWN"))
```

### R-04: Add Escalation Literal constraint test (addresses G-04)

**Priority:** Low
**Estimated effort:** ~5 LOC
**Value:** Minimal -- framework guarantee.

```python
def test_escalation_severity_rejects_low(self) -> None:
    esc = {
        "id": "E-001", "severity": "LOW", "category": "security",
        "summary": "test", "details": "test",
        "recommended_target": "security-team", "blocking": False,
    }
    with pytest.raises(ValidationError):
        Escalation(**esc)
```

---

## Summary

The schema module has strong test coverage with a 1.69:1 test:source ratio and 44 tests. The identified gaps are all low priority because they test framework-guaranteed behavior (Pydantic field validation, StrEnum constraint enforcement). The one gap with application-specific value is G-02 (`_sanitize_file_path` direct testing), which would prove the only custom validator in the module. Total estimated LOC at risk is ~11 lines (7.9% of code), all in low-risk categories.
