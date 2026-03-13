<!-- SPDX-License-Identifier: MIT -->

# Phase 1 Retrospective: schema (Dry Run)

**Date:** 2026-03-13
**Unit audited:** schema
**Framework version:** v1.0

---

## 1. Did the framework run end-to-end?

**Yes.** Every phase (A' through D) completed without blocking ambiguity.

- Phase A' (hygiene): Clean run, no issues.
- Phase A (prep): FRESHNESS.md row found (status: NEVER), git log produced
  clean 6-commit history, registry.yaml entry located.
- Phase B (census): All 6 census steps producible. B6.5 reclassification
  checkpoint confirmed: all 5 data-model items applicable (4 scored, 1 N/A
  by unit scope). No reclassification needed.
- Phase C (review): Static analysis, checklist evaluation, integration review,
  and stress review all completed. Evidence collected for all items.
- Phase D (artifacts): FINDINGS.md, SCORECARD.md, and COVERAGE.md written
  per templates. Gate rules evaluated. Health status determined.

The full flow took approximately 45 minutes of AI auditor time plus human
review, which is reasonable for a 196-LOC leaf unit.

## 2. Were evidence tiers practical?

**Yes, with one observation.**

- **Tier A worked well.** DM-01 (validation) and DM-04 (serialization) both
  had clear existing tests to cite. Test names and line numbers are
  reproducible evidence.
- **Tier B was not needed.** No checklist item required deterministic repro
  commands; all machine-verifiable items had existing pytest assertions.
- **Tier C worked as intended.** DM-03 (constrained types) required code
  reading and architectural judgment about which fields should be bare str
  vs constrained. The auditor analyzed all 20 bare str fields individually.
- **Tier split (A + C) worked on DM-02.** "Are models frozen?" = Tier A
  (test at line 324-331). "Would mutation violate trust?" = Tier C
  (architectural reasoning about which models transit trust boundaries).
  The split was natural and produced clear evidence at both tiers.
- **N/A handling was clean.** DM-05 (graph types) correctly evaluated as N/A
  with justification.

**Observation:** No Tier B evidence was produced. This is expected for a unit
with strong test coverage — Tier B (deterministic commands/traces) sits between
"has a test" and "manual reading." For well-tested units, evidence tends to be
Tier A or Tier C with little Tier B. This may change for less-tested units in
Phase 2.

## 3. Was the scorecard completable?

**Yes.** All 11 dimensions scored without hand-waving.

Some dimensions required interpretation for a data-model unit:

- **Robustness (scored 7):** Pure data models have minimal error paths. The
  only error path is the field_validator. Scored against "appropriate for
  workload" rather than penalizing absence of retry logic (which would be
  wrong for a data model).
- **Auditability (scored 6):** No logging, but logging is inappropriate for
  a data model. Scored based on structural clarity and Field descriptions.
- **Performance (scored 8):** No algorithms to optimize, no I/O. Scored as
  "optimal for workload" since pure Pydantic models have negligible overhead.

The gate evaluation was straightforward. No override or ceiling gates fired.
The determination algorithm produced a clear result (7.7 average = Adequate).

**No dimensional scoring ambiguity rose to "I can't score this honestly."**

## 4. Were checklist items clear?

**Yes, all 5 items were evaluable.**

- DM-01 through DM-04: Clear invariants with clear evidence types.
- DM-05: Required recognizing it was N/A by unit scope, which was
  straightforward (zero grep matches for graph-related terms).
- DM-02 benefited from the borderline-handling rule (split compound claims
  into Tier A + Tier C). Without that rule, the auditor might have struggled
  to assign a single tier.

**No checklist item was too vague to score consistently.**

## 5. What friction was logged?

**No friction entries.** The framework ran cleanly on this unit.

This is expected — schema is the simplest unit in the pilot (leaf, no
boundaries, strong test coverage). The framework's real test comes in Phase 2
with rule-secrets (deterministic security rules) and retry (trust boundaries
and compound chains).

The absence of friction on schema is not itself a finding. The framework was
designed for units of varying complexity; a clean run on a simple unit
validates the basic flow without stress-testing the harder features.

---

## Gate Decision

**PROCEED** — No structural framework issues found. No friction logged.

The framework ran end-to-end without ambiguity, evidence tiers were practical,
the scorecard was completable, and checklist items were clear. Phase 2 may begin.

---

## Framework Version Stamp

**Phase 2 uses framework v1.0 (unchanged).**

No in-flight clarification fixes were needed during Phase 1. The framework
artifacts (METHODOLOGY.md, SCORECARD-TEMPLATE.md, data-model checklist) were
used exactly as written.

---

## Notes for Phase 2

1. **Tier B will get a real test.** rule-secrets has deterministic security
   patterns that should produce Tier B evidence (grep commands, source-to-sink
   traces). retry has boundary functions that may need Tier B command-based
   repro.

2. **Gate dimensions will matter more.** retry touches TB-5 and TB-8, which
   means Security Posture and Adversarial Resilience scores will affect gate
   evaluation. Schema's scores on these dimensions (7 and 6) set a calibration
   anchor.

3. **Compound chain sections will be exercised.** retry's CH-1 analysis is the
   first real test of the compound chain methodology. The "None identified"
   entries on schema establish the baseline format.

4. **Cross-unit calibration opportunity.** During adjudication, compare
   Convention Adherence (schema: 9) and Test Quality (schema: 8) scores
   against rule-secrets and retry to ensure consistency.
