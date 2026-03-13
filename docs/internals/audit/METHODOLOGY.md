# Per-Unit Audit Methodology — Grippy

**Version:** 1.1
**Established:** 2026-03-13
**Derived from:** Navi OS audit methodology v2.0 (20-module sweep, 178 findings, 11 remediation PRs)

---

## Ontology

One canonical vocabulary. Used everywhere. No synonyms.

| Term | Definition |
|------|-----------|
| **Audit unit** | The smallest thing that gets its own scorecard, findings doc, and freshness row. One unit = one audit cycle. |
| **Source artifact** | A file or directory under `src/grippy/`, including non-Python supporting assets (e.g., `prompts_data/*.md`). Source artifacts map to audit units via `registry.yaml`. |
| **Cross-cutting target** | A concern that spans multiple units, evaluated only during superset analysis or compound-chain review. Does NOT get its own scorecard. |

**Terminology discipline:** Never say "module commits." Say "commits touching files mapped to the audit unit."

---

## Section A: Principles

### A1. Appreciative Inquiry First

Every audit begins by identifying what works well. Strengths are documented before findings. This establishes the baseline against which deviations are measured and prevents auditors from anchoring on negatives.

### A2. Triangulation Required

Triangulation (2+ independent evidence sources) is preferred for all findings and **required** for Tier C findings or when evidence is ambiguous. A single Tier A test can justify a finding by itself. Single-source observations without machine-verifiable or deterministic evidence are recorded as hypotheses (see Evidence Tiers, Tier D), not findings.

**Evidence types:**

| Evidence Type | Description | Example |
|---|---|---|
| Code reading | Direct inspection at `file:line` | `agent.py:99` _escape_xml pipeline |
| Test gap analysis | Missing coverage for a code path | No adversarial test for NL injection pattern X |
| Caller trace | Following a function's callers to verify contract | `format_pr_context()` → `create_reviewer()` → Agent |
| Static analysis | ruff, mypy, bandit output | Type narrowing failure in mypy strict |
| Behavioral trace | Running code and observing behavior | Rule engine parsing a crafted diff |
| Git archaeology | `git log`/`git blame` for intent | Commit explains history poisoning mitigation |
| Config surface | Environment variable audit | Missing `GRIPPY_` prefix on setting |
| Cross-unit flow | Data flowing across unit boundaries | PR title → `_escape_xml` → prompt → LLM → GitHub comment |
| Documentation delta | Docstring/README vs actual behavior | README claims mode X but `prompts.py` skips it |

### A3. Dependency-Ordered Phases

Units are audited leaf-first, integration-last. When auditing a high-level unit, its dependencies have already been assessed and known issues are factored in. See `registry.yaml` for the canonical phase mapping.

### A4. Findings as Improvements

Findings are framed as improvements, not criticisms. Each finding includes:
- Exact `file:line` citation
- Code snippet showing current behavior
- Explanation of why it matters
- Suggested improvement (when non-obvious)

### A5. Evidence-Backed Findings

Every finding requires evidence meeting the minimum bar for its tier (see Evidence Tiers below). A finding without reproducible evidence is a hypothesis, not a finding.

---

## Section B: Per-Unit Audit Process

### Phase A': Hygiene Pre-Check

**Time budget:** 5 minutes

| Step | Action | Command |
|---|---|---|
| A'1 | Check dependencies for advisories | `uv run pip-audit` |
| A'2 | Check stale TODOs/FIXMEs | `grep -rn "TODO\|FIXME" {source_files}` |
| A'3 | Verify dev tool config is current | Check `pyproject.toml` ruff/mypy sections |

Note: `{source_files}` refers to the paths listed in `registry.yaml` for this unit. Many units are single files, not directories.

**Exit criterion:** No environmental surprises. Findings from A' are LOW severity.

### Phase A: Pre-Audit Prep

**Time budget:** 10-15 minutes

| Step | Action | Output |
|---|---|---|
| A1 | Read `FRESHNESS.md` for last audit date and score | Baseline context |
| A2 | Read unit's prior `FINDINGS.md` if exists | Prior findings to verify |
| A3 | Run `git log --since={last_audit_date} -- {source_files}` | Changes since last audit |
| A4 | Read the unit's `README.md` in `docs/internals/audit/{unit_id}/` | Census and dependency map |

**Exit criterion:** Auditor understands the unit's role, known issues, and recent changes.

### Phase B: Unit Census

**Time budget:** 15-20 minutes

| Step | Action | Output |
|---|---|---|
| B1 | Inventory all source artifacts with line counts | File table in census |
| B2 | Map internal dependency edges (what this unit imports from grippy.*) | Dependency graph |
| B3 | Map public functions/classes at unit level | Public surface |
| B4 | Map test files to source files with approximate test counts | Test coverage map |
| B5 | Enumerate config surface (env vars, constants, Settings fields) | Config table |
| B6 | Identify unit type(s) from `registry.yaml` | Applicable checklists |
| B6.5 | **Re-classification checkpoint:** If >50% of primary checklist items evaluate as N/A, the primary type is wrong. Reclassify, document in unit's `README.md` audit history, re-run with new primary. If >50% of secondary checklist items evaluate as N/A, remove the secondary type for future audits. | Updated type mapping |

**Exit criterion:** Complete understanding of unit boundaries and public surface.

### Phase C: Systematic Review

#### C1: Static Analysis

| Step | Action | Tool |
|---|---|---|
| C1.1 | Run `uv run ruff check {source_files}` | ruff |
| C1.2 | Run `uv run mypy {source_files}` | mypy |
| C1.3 | Run `uv run bandit -r {source_files}` | bandit |
| C1.4 | Check for unused imports, dead code, unreachable branches | ruff + manual |

#### C2: Behavioral Review

Code path analysis using the applicable checklist(s) from `docs/internals/audit/CHECKLISTS/`.

| Step | Action |
|---|---|
| C2.1 | Walk every public function/method, verifying contracts (input -> processing -> output) |
| C2.2 | Check error handling: are exceptions caught at the right granularity? |
| C2.3 | Verify state management: are mutable shared objects protected? |
| C2.4 | Run the unit-type-specific checklist items |
| C2.5 | Document magic numbers, undocumented constants, and implicit assumptions |

#### C3: Integration Review

| Step | Action |
|---|---|
| C3.1 | Trace all callers of the unit's public API |
| C3.2 | Verify that callers handle all documented error conditions |
| C3.3 | Check coupling: does this unit know too much about its callers or callees? |
| C3.4 | Check for N+1 patterns across unit boundaries |
| C3.5 | **Cross-unit data flow:** Trace this unit's unvalidated outputs to consumers in other units. If neither producer nor consumer validates, finding at MEDIUM+. |
| C3.6 | **Critical data flow (Grippy-specific):** PR content -> `_escape_xml` -> agent prompt -> LLM -> `run_review` JSON parse -> `_validate_rule_coverage` -> `github_review` sanitization -> GitHub API. Any unit touching this path gets extra scrutiny on sanitization completeness. |

#### C4: Stress Review

| Step | Action |
|---|---|
| C4.1 | Boundary conditions: empty inputs, max-length inputs, zero/negative values |
| C4.2 | Concurrency: thread safety, async safety, lock ordering |
| C4.3 | Resource cleanup: file handles, DB connections, async tasks |
| C4.4 | **Compound failure chains:** What dangerous downstream chain can this unit participate in? (see Section D) |
| C4.5 | Graceful degradation: does the unit fail closed or fail open? |
| C4.6 | **Multi-process safety:** If unit uses file-based state (SQLite), verify WAL mode, concurrent access, atomic writes. |

### Phase D: Post-Audit Actions

| Step | Action | Output |
|---|---|---|
| D1 | Write `docs/internals/audit/{unit_id}/FINDINGS.md` | Severity-ordered findings + Compound Chain Exposure + Hypotheses |
| D2 | Write `docs/internals/audit/{unit_id}/SCORECARD.md` using template | 11-dimension scores with gate status |
| D3 | Write `docs/internals/audit/{unit_id}/COVERAGE.md` | Test coverage assessment (gap-first) |
| D4 | Update `docs/internals/audit/FRESHNESS.md` | New date, commit, score, status |
| D5 | Update `docs/internals/audit/{unit_id}/README.md` audit history table | Audit trail |

**COVERAGE.md structure:** Lead with gaps, not census:
1. Test file inventory — summary table
2. Coverage gaps — untested areas with LOC at risk (primary value)
3. Per-source summary — one row per source file
4. Recommendations — prioritized test additions

---

## Section C: Severity Taxonomy

**Exhaustive list.** The four levels below are the only valid finding severities. There is no INFO, NOTE, or other level. Observations that do not meet the bar for LOW are recorded as hypotheses (Tier D evidence) in the Hypotheses section of FINDINGS.md, not as findings.

### CRITICAL — Actively Exploitable in Production

Security bypass, data loss, or attacker-controlled behavior under normal conditions.

**Evidence requirement:** Tier A only (must be demonstrable).
**Action required:** Fix immediately or halt deployment.

### HIGH — Design Issues Affecting Correctness Under Normal Operation

Correctness failure during normal usage, or security weakness requiring specific but realistic conditions.

**Evidence requirement:** Tier A or B. Tier C allowed as **HIGH (provisional)** — see expiry rule.
**Action required:** Fix before next release or document as accepted risk with mitigation.

### MEDIUM — Correctness Concerns in Edge Cases

Correct under normal conditions but fails under specific (realistic) edge cases, or security hardening gap requiring unusual conditions.

**Evidence requirement:** Tier A, B, or C.
**Action required:** Fix within 2 audit cycles.

### LOW — Style, Maintenance, Documentation

No correctness or security impact. Affects maintainability, readability, or developer experience.

**Evidence requirement:** Tier A, B, or C.
**Action required:** Fix opportunistically or during related refactoring.

### HIGH (provisional) Expiry Rule

A HIGH finding supported only by tier C evidence must be promoted to tier A or B evidence by the **next scheduled audit of that specific unit** — whether triggered by freshness status change (STALE or BOUNDARY_CHANGED) or by the next full sweep. If no re-audit of the unit occurs within 6 months, the provisional HIGH auto-downgrades to MEDIUM and the freshness tracker notes the reason.

This prevents serious issues from being buried into MEDIUM for paperwork reasons, while ensuring that provisional findings don't persist indefinitely without stronger evidence.

---

## Section D: Evidence Tiers

| Tier | Name | Definition | Minimum Bar |
|---|---|---|---|
| A | Machine-verifiable | Automated test, CI artifact, or static analysis output that can be re-run | Test name or CI job that proves the property |
| B | Deterministic repro | A command or trace another auditor can independently replay | (1) exact command + observed output, OR (2) named source-to-sink call path with file:line citations, OR (3) static trace with entry/exit points named |
| C | Manual code trace | Auditor read the code and traced the path; no automated proof exists yet | Must name files, functions, and the traced path. A bare grep hit is a lead, not tier C — requires following the path to a conclusion. |
| D | Hypothesis | Observation without corroborating evidence | **Not scored.** Recorded in "Hypotheses" section of FINDINGS.md only. Promoted when evidence arrives; struck through with refuting evidence when disproven. |

---

## Section E: Resolution States

| State | Meaning | Unresolved for Gates? | Status Consequence |
|---|---|---|---|
| OPEN | Finding acknowledged, no fix yet | Yes | — |
| IN_PROGRESS | Fix underway (linked to PR/branch) | Yes | — |
| RESOLVED | Fix merged and verified | No | — |
| ACCEPTED_RISK | Team decided not to fix. Requires: written justification, project owner or designated approver sign-off, review date. | No | Accepted CRITICAL: caps at "Needs Attention". Accepted HIGH: caps at "Adequate". Both add "(accepted risk)" suffix. Tracked in "Accepted Risks" section of FINDINGS.md. |
| FALSE_POSITIVE | Finding was incorrect. Refuting evidence required. | No | Moved to "Refuted" section. |

**Rollup rules:**
- Multiple instances of same pattern in same unit: one finding at highest severity, with count annotation (e.g., "HIGH x 3 instances").
- Same pattern across different units: counted separately per unit (addressed in superset clustering).

---

## Section F: Compound Failure Chains

### Known Chain Registry

| ID | Chain | Path (by boundary) | End State |
|---|---|---|---|
| CH-1 | Prompt Injection -> Fabricated Finding -> Merge Block | TB-1/TB-3 -> TB-5/TB-8 -> TB-6 | Attacker blocks legitimate merge |
| CH-2 | Path Traversal -> Data Exfiltration -> Prompt Leakage | TB-4 -> tool response -> TB-3 | Internal files exposed in findings |
| CH-3 | Output Injection -> GitHub Comment XSS/Phishing | TB-5 -> TB-6 | Malicious content in PR comments |
| CH-4 | Rule Bypass -> Silent Vulnerability Pass | TB-2 -> rule-engine -> TB-8 | Real vulnerability undetected |
| CH-5 | History Poisoning -> Persistent Instruction Override | TB-9 -> TB-3 -> TB-5 | Prior PR content acts as future instructions |

### Per-Unit Compound Chain Exposure

Every unit audit (Phase C4.4) must produce a "Compound Chain Exposure" section in FINDINGS.md:

- Chains this unit participates in (by chain ID)
- This unit's role: **origin** (where bad state enters), **relay** (passes through), or **terminus** (where impact lands)
- Whether this unit has a circuit breaker for its chain role

If the auditor concludes the unit does not participate in any known chain: write "None identified" with a one-sentence justification. Do not silently skip the section.

New chains discovered during audit are assigned the next ID and added to this registry in the same commit as the finding.

### Chain Template

```markdown
## Compound Chain: [Name]

**Trigger:** [Initial event]

**Chain:**
1. Unit A: [Finding Ax] -- [what happens]
2. Unit B: [Finding Bx] -- [how it receives the bad state]
3. Unit C: [Finding Cx] -- [how the chain completes]

**End state:** [What the user/system experiences]
**Severity:** [Based on end state, not individual findings]

**Evidence:**
- [Evidence type 1]: [citation]
- [Evidence type 2]: [citation]

**Mitigation:** [How to break the chain]
```

---

## Section G: CI Structural Checks

| Check | Enforcement | Status |
|---|---|---|
| F1: Test file parity | `scripts/check_test_parity.py` (CI) | Exists |
| F2: Quality gate floor | `scripts/check_quality_gate.py` (CI) | Exists |
| F3: SPDX license headers | pre-commit hook | Exists |
| F4: SHA-pinned Actions | manual audit (scriptable) | Manual |
| F5: Thread-safety scan | `tests.yml` job step | Exists |
| F6: Trust boundary change detection | `FRESHNESS.md` manual review | Manual |

---

## Appendix A: Audit Unit Type -> Checklist Map

| Type | Checklist | Units |
|---|---|---|
| Security Rule | `CHECKLISTS/security-rule.md` | rule-engine, rule-enrichment, 10x rule-* |
| LLM Agent | `CHECKLISTS/llm-agent.md` | agent, prompts |
| LLM-Facing Tool | `CHECKLISTS/llm-facing-tool.md` | codebase |
| Review Pipeline | `CHECKLISTS/review-pipeline.md` | retry, github-review, review |
| Data Model | `CHECKLISTS/data-model.md` | schema, graph-types |
| Infrastructure | `CHECKLISTS/infrastructure.md` | See subprofiles below |

**Infrastructure subprofiles:**

| Subprofile | Characteristic | Key Concerns | Units |
|---|---|---|---|
| Config | Passive utilities, parsers, factories. No external I/O. | Input validation, error clarity, edge cases | ignore, imports, embedder, mcp-config, mcp-response |
| State | Reads/writes persistent data. | Concurrent access, corruption, migration | graph-store, graph-context |
| Boundary | Interfaces with external systems. | Subprocess safety, timeouts, sanitization, error opacity | local-diff, mcp-server, cli |

---

## Appendix B: Dual-Type Scoring Policy

One scorecard per unit. Always.

1. Primary checklist determines the scorecard structure and all 11 dimension scores.
2. Secondary checklist items are appended. They only affect dimensions they explicitly touch. Where primary and secondary evidence conflicts on the same dimension, the lower score governs.
3. **Secondary findings are fully gate-bearing.** A HIGH finding from secondary-checklist evidence triggers gates exactly the same as primary evidence.
4. Scorecard header notes both types: `Unit type: Infrastructure: Boundary (primary), LLM Agent (secondary)`.
5. Reclassification: >50% primary items N/A -> reclassify primary. >50% secondary items N/A -> remove secondary.

---

## Revision History

| Version | Date | Changes |
|---|---|---|
| 1.0 | 2026-03-13 | Initial Grippy adaptation from navi-os v2.0. 30 units, 11 dimensions, v4.1 gate model, trust boundary register, compound chain registry. |
| 1.1 | 2026-03-13 | Pilot friction fixes: SR-06 scoped to rule-engine unit (Friction #1). Review-pipeline checklist gains Scope column — RP-07 to github-review, RP-08/09 to review (Friction #2). `(provisional)` suffix clarified as evidence-maturity signal (Friction #3). Severity taxonomy declared exhaustive — no INFO level (Friction #3 derivative). |
