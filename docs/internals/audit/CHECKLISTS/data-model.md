# Data Model Checklist

**Applies to:** schema, graph-types

| ID | Invariant | Severity | Evidence Types | Automation |
|----|-----------|----------|---------------|------------|
| DM-01 | Schema models validate field types at parse time, rejecting invalid data | HIGH | Validation test with wrong types, missing required fields, extra fields | test |
| DM-02 | Required fields are not marked Optional -- missing data fails loudly | MEDIUM | Schema inspection; test that omitting required fields raises | test |
| DM-03 | Enum-like fields use constrained types, not bare strings | MEDIUM | Schema inspection for `Literal` or `Enum` usage | manual |
| DM-04 | Serialized output is safe for JSON serialization without custom handling | LOW | Round-trip test: model -> `.model_dump()` -> `json.dumps()` | test |
| DM-05 | Graph type definitions match graph store usage -- no orphan types | LOW | Cross-reference type definitions against store operations | manual |
