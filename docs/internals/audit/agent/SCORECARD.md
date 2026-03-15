<!-- SPDX-License-Identifier: MIT -->

# Audit Scorecard: agent

**Audit date:** 2026-03-14
**Commit:** f8548ac
**Auditor:** Claude Opus 4.6 (AI draft) / Nelson Spence (human reviewer)
**Unit type:** llm-agent (primary)
**Subprofile:** N/A
**Methodology version:** 1.3

---

## Checklist: LA-01 through LA-08

| ID | Invariant | Status | Evidence |
|----|-----------|--------|----------|
| LA-01 | All untrusted PR content sanitized before prompt insertion | PASS | Tier A: `TestUnicodeInputAttacks` (7 tests: zero-width, bidi, homoglyphs, tags, inline format_pr_context), `TestPromptInjectionDefenses` (8+ tests: XML breakout in diff/title/rule_findings, nested escape, NL injection, confidence manipulation), `TestEscapeXml` (4 tests). Pipeline: `navi_sanitize.clean()` → 7 compiled NL injection patterns → XML entity escape (`& < >`). Every PR metadata field routed through `_escape_xml()` in `format_pr_context()` (`agent.py:317-334`). |
| LA-02 | Data fence boundary separates instructions from untrusted content | PASS | Tier A: `TestDataFenceBoundary::test_fence_present_and_adversarial_content_only_inside_fence` — asserts fence preamble present, adversarial payload escaped, payload appears only after fence (not echoed into instruction layer). `test_xml_breakout_cannot_escape_structural_framing` — structural tag counts verified. Fence preamble: `agent.py:300-305`. |
| LA-03 | Prior LLM responses not included in subsequent prompts | PASS | Tier A: `TestSessionHistoryPoisoning::test_history_disabled_when_db_set` (mocked Agent, db_path configured, asserts `add_history_to_context is not True`). Tier C: security rationale comment at `agent.py:263-267` explaining CH-5 history poisoning risk. `add_history_to_context=False` set unconditionally at `agent.py:279`, not gated on `db_path`. |
| LA-04 | Provider registry covers all transports with explicit failure | PASS | Tier A: `TestResolveTransport` (9 tests): three-tier priority (param > env > API key inference > default), all 6 valid transport names accepted, invalid transport raises `ValueError` with available list, case/whitespace normalization. `TestOutputSchemaConditional::test_anthropic_transport_skips_output_schema` verifies clean `ImportError` with install instructions when SDK missing. |
| LA-05 | Identity loads before mode-specific instructions | PASS | Tier A: `TestIdentityOrdering::test_identity_wired_to_description_instructions_to_instructions` — mocks `load_identity` and `load_instructions` with sentinels, verifies identity → `description` kwarg, instructions → `instructions` kwarg. `test_mode_forwarded_to_instruction_loader_not_identity` — mode reaches `load_instructions()` but not `load_identity()` (identity is mode-agnostic). Tests construction inputs, not opaque Agent internals. |
| LA-06 | Only CodebaseToolkit tools passed in production | PASS | Tier B: repo-wide grep for `create_reviewer(` yields exactly 3 matches: (1) `agent.py:163` — definition, (2) `review.py:551` — CI pipeline: `tools=codebase_tools`, `tool_hooks=[sanitize_tool_hook]`, (3) `mcp_server.py:131` — MCP server: no tools, no tool_hooks. No hidden widening. |
| LA-07 | Structured output correct per provider | PASS | Tier A: `TestOutputSchemaConditional` (3 tests): local transport gets `output_schema=GrippyReview`, OpenAI gets `output_schema=GrippyReview`, Anthropic gets `output_schema=None`. Logic at `agent.py:261`: schema set only when `structured` flag is True (from `_PROVIDERS[transport][2]`) or transport is local. |
| LA-08 | Each mode loads correct prompt subset | PASS | Tier A: `test_grippy_prompts.py` verifies all 6 mode chains map to correct prompt file sequences. `MODE_CHAINS` dict in `prompts.py` is consumed by `load_instructions()` which is tested independently. Agent delegates mode resolution to prompts module. |

---

## Gate Rules

### Override Gates (force a specific status)

| Override Gate | Condition | Fired? |
|---|---|---|
| Critical finding | Any unresolved CRITICAL finding | No |
| Multi-HIGH block | 2+ unresolved HIGH findings (including provisional) | No (0 HIGH findings) |
| Security collapse | Security Posture < 2 | No (score: 9) |
| Adversarial collapse | Adversarial Resilience < 2 | No (score: 7) |

### Ceiling Gates (cap the best allowed status)

| Ceiling Gate | Condition | Fired? |
|---|---|---|
| Severity cap | Any unresolved HIGH finding | No |
| Security hard floor | Security Posture < 4 | No (score: 9) |
| Adversarial hard floor | Adversarial Resilience < 4 | No (score: 7) |
| Security soft floor | Security Posture < 6 | No (score: 9) |
| Adversarial soft floor | Adversarial Resilience < 6 | No (score: 7) |
| Accepted critical risk | Any ACCEPTED_RISK at CRITICAL | No |
| Accepted high risk | Any ACCEPTED_RISK at HIGH | No |

---

## Summary

| Dimension | Score | Evidence Tier | Notes |
|-----------|------:|:---:|-------|
| 1. Contract Fidelity | 8/10 | A | Typed signatures throughout, `tuple[str, str]` return on _resolve_transport, typed _PROVIDERS registry, mypy strict clean. Small public API (2 functions). |
| 2. Robustness | 7/10 | A | Clean 3-tier fallback in _resolve_transport with source tracking. Deferred imports with descriptive ImportError. ValueError for bad config. No graceful degradation for LLM API failures (retry's job). |
| 3. Security Posture | 9/10 | A | 4-layer sanitization (navi_sanitize -> NL pattern neutralization -> XML escape -> data fence). Unconditional history disable. Deferred imports for provider isolation. Static _PROVIDERS dict (no user input in import paths). 4 trust boundaries defended. |
| 4. Adversarial Resilience | 7/10 | A | 18+ adversarial tests across hostile_environment (Unicode: 7, prompt injection: 8+, history poisoning: 2, info leakage: 1). TB-7 gap closed by 9 _resolve_transport tests. NL patterns are finite (7 compiled regexes) — new attack patterns could bypass. |
| 5. Auditability & Traceability | 7/10 | A + C | Security rationale comments inline (TB-9 at agent.py:263-267, _PROVIDERS at agent.py:61-65). Transport resolution logged (`log.info`). Deterministic prompt chain. No structured sanitization telemetry. |
| 6. Test Quality | 7/10 | A | 41 dedicated tests (7 classes, 565 LOC) + ~18 hostile env = ~59 total for 345 source LOC (1.64:1 ratio). Good breadth across transport, sanitization, ordering, boundary. Adversarial coverage split across two files. |
| 7. Convention Adherence | 9/10 | A | SPDX header, ruff clean, mypy strict clean, test mirror (`test_grippy_agent.py`, 565 LOC). |
| 8. Documentation Accuracy | 8/10 | C | Security comments for TB-9 history poisoning, data fence preamble, _PROVIDERS structure, _LocalModel structured-output conflict. `create_reviewer()` docstring covers all params. No formal API docs. |
| 9. Performance | 8/10 | B | Deferred imports — no SDK loaded until needed. One-shot prompt composition (no repeated file reads). No hot paths in agent factory. Compiled _INJECTION_PATTERNS regexes. |
| 10. Dead Code / Debt | 9/10 | A | `_LocalModel` actively used (local transport). All _INJECTION_PATTERNS exercised by hostile env tests. `_VALID_TRANSPORTS` used in validation. Zero TODOs. ruff detects no unused imports. |
| 11. Dependency Hygiene | 7/10 | A | Internal: grippy.prompts (Phase 2, audited), grippy.schema (Phase 0, audited). External: navi_sanitize (security-critical), agno (framework). Provider SDKs deferred via importlib. |
| **Overall** | **7.8/10** | | **Average of 11 dimensions** |

**Health status:** Adequate

**Determination:**
1. Average-based status: 7.8/10 falls in 6.0-7.9 range = **Adequate**
2. Override gates: None fired.
3. Ceiling gates: None fired. All gate dimensions >= 6.
4. Suffixes: No `(provisional)` — Dim 3 (9/10) supported by Tier A (adversarial sanitization tests, NL injection tests). Dim 4 (7/10) supported by Tier A (hostile_environment test suite, TestResolveTransport, TestDataFenceBoundary). Under v1.2 rules, non-security dimensions with Tier C (dims 5, 8) do not trigger the suffix.

**Override gates fired:** None
**Ceiling gates fired:** None

---

## Compound Chain Exposure

agent participates in 3 of the 5 compound chains, with distinct roles in each.

### CH-1: Prompt Injection -> Fabricated Finding -> Merge Block

**Role:** Origin — agent constructs the prompt that could be manipulated.

**Data flow:**
```
PR content (title, body, diff, branch) → _escape_xml() 4-layer pipeline
  → format_pr_context() with data fence preamble
  → create_reviewer() → Agent(description=identity, instructions=mode_chain)
  → LLM processes sanitized prompt
```

**Circuit breakers:**
1. **LA-01:** `_escape_xml()` — navi_sanitize → NL pattern neutralization → XML entity escape. Covers all PR metadata fields.
2. **LA-02:** Data fence preamble warns LLM that content below is untrusted. Adversarial payload confined to fenced section (Tier A: `TestDataFenceBoundary`).
3. **TB-1:** `format_pr_context()` is the sole ingress point for PR content into the prompt.

### CH-5: History Poisoning -> Persistent Instruction Override

**Role:** Circuit breaker — agent disables history re-injection.

**Data flow:**
```
Prior LLM response (may contain echoed attacker content)
  → session history in SQLite
  → Agent(add_history_to_context=False) ← BLOCKED HERE
  → history never re-injected into subsequent prompts
```

**Circuit breaker:**
1. **LA-03:** `add_history_to_context=False` set unconditionally at `agent.py:279`. Not gated on `db_path`. Security rationale comment at `agent.py:263-267`. Tested: `test_history_disabled_when_db_set` verifies with mocked Agent.

### CH-2: Path Traversal -> Data Exfiltration -> Prompt Leakage

**Role:** Consumer — agent passes tools to LLM via `create_reviewer()`.

**Data flow:**
```
create_reviewer(tools=codebase_tools, tool_hooks=[sanitize_tool_hook])
  → Agent configured with CodebaseToolkit
  → LLM tool calls → codebase.py validates paths → sanitize_tool_hook filters output
```

**Circuit breaker:**
1. **LA-06:** Only `CodebaseToolkit` passed as tools in production (repo-wide trace: 2 call sites, 1 with tools, 1 without). No hidden tool widening.
2. **TB-4 defense (owned by codebase unit):** `is_relative_to()` path traversal, `sanitize_tool_hook()` output sanitization.

agent does **not** participate in CH-3 (Output Injection -> XSS/Phishing) — agent does not post to GitHub. That boundary is owned by `github-review` (TB-6).

agent does **not** participate in CH-4 (Rule Bypass -> Silent Vulnerability Pass) — rule execution is owned by `rule-engine` (TB-2).

---

## Dimension Details

### 1. Contract Fidelity

**Score:** 8/10
**Evidence:**
- mypy strict passes with zero issues (Tier A).
- `_resolve_transport()`: typed `(str | None, str) -> tuple[str, str]` with documented return semantics (Tier A).
- `create_reviewer()`: 13 typed keyword-only parameters, returns `Agent` (Tier A).
- `format_pr_context()`: 11 typed keyword-only parameters, returns `str` (Tier A).
- `_escape_xml()`: `str -> str`, pure function (Tier A).
- `_LocalModel(OpenAILike)`: typed `get_request_params()` override (Tier A).
- `_PROVIDERS`: `dict[str, tuple[str, str, bool]]` — static registry (Tier A).
- Small public API surface: `create_reviewer()` and `format_pr_context()` (2 functions).
- Not 9: `tools: list[Any] | None`, `tool_hooks: list[Any] | None`, `tool_call_limit: int | None` in `create_reviewer()` use `Any` (Agno's tool types are not publicly typed). `kwargs: dict[str, Any]` internally.
- Calibration: matches codebase (8). Both have typed throughout with some `Any` for framework interop.

---

### 2. Robustness

**Score:** 7/10
**Evidence:**
- **_resolve_transport fallback chain:** Tier 1 (param) → Tier 2 (env) → Tier 3 (API key inference) → default. Each tier returns source metadata for debugging. Tested with 9 tests covering all paths (Tier A).
- **Deferred imports:** `importlib.import_module()` catches `ImportError`/`ModuleNotFoundError`, wraps with descriptive message including install command (Tier A: `test_anthropic_transport_skips_output_schema`).
- **Config validation:** `ValueError` for invalid transport with sorted available list (Tier A: `test_invalid_transport_raises_valueerror`).
- **Input normalization:** `.strip().lower()` on both param and env var transport values (Tier A: 2 normalization tests).
- Not 8: No graceful degradation for LLM API failures — that's `retry.py`'s responsibility (`run_review()` with retry + error feedback). Agent factory constructs the agent but doesn't handle runtime API errors. `print()` used for Tier 3 inference notice instead of `logging` (GitHub Actions `::notice::` format, intentional but not filterable). No timeout on model construction.
- Calibration: below graph-store (8, WAL mode + busy_timeout + pragma fallbacks). Agent is a factory, not a stateful system — its robustness scope is narrower.

---

### 3. Security Posture

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 9/10
**Evidence:**
- **4-layer sanitization pipeline (LA-01):** `navi_sanitize.clean()` (invisible chars, bidi, homoglyphs, NFKC) → 7 compiled `_INJECTION_PATTERNS` (scoring overrides, confidence manipulation, system update claims, instruction ignoring) → XML entity escape (`& < >`) → data fence preamble. Each layer is independently tested (Tier A).
- **Data fence boundary (LA-02):** `format_pr_context()` opens with explicit warning that all content below is user-provided data. Adversarial content fenced — cannot appear before preamble (Tier A: `TestDataFenceBoundary`).
- **History disable (LA-03):** `add_history_to_context=False` unconditional. Security rationale inline. Blocks CH-5 (Tier A + C).
- **Provider isolation (TB-7):** `_PROVIDERS` dict uses static string module paths and class names. No user input reaches `importlib.import_module()`. Transport validated against `_VALID_TRANSPORTS` before lookup (Tier A: 9 tests).
- **Deferred imports:** Provider SDKs loaded only when needed. Failure produces clean `ImportError`, not silent misconfiguration (Tier A).
- **Tool boundary (LA-06):** Only `CodebaseToolkit` passed in production paths. Repo-wide trace confirms (Tier B).
- Not 10: NL injection patterns are finite (7 regexes) — novel attack patterns could bypass. `_INJECTION_PATTERNS` rely on case-insensitive matching, which is effective but not semantic. No content-security-policy equivalent for the prompt itself. `navi_sanitize` is an external dependency whose contract is trusted but not independently verified in grippy's test suite.
- Calibration: matches local-diff (9). Both defend critical trust boundaries with defense-in-depth. Agent has more boundaries (4 vs 1) but the sanitization pipeline is the primary defense, not subprocess safety.

---

### 4. Adversarial Resilience

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 7/10
**Evidence:**
- **Adversarial test count:** 41 dedicated tests + ~18 hostile environment tests = ~59 total. Of the hostile env tests, 18+ are agent-relevant (import `_escape_xml`, `format_pr_context`, `create_reviewer` from `grippy.agent`).
- **Attack vectors tested:**
  - Unicode normalization: zero-width, bidi overrides, homoglyphs, tag characters (Tier A: 7 tests)
  - XML breakout: tag injection in diff, title, rule_findings; nested escape idempotency (Tier A: 4+ tests)
  - NL injection: scoring overrides, confidence manipulation, system update claims, instruction ignoring (Tier A: 4+ tests)
  - History poisoning: disabled with db_path, security rationale documented (Tier A: 2 tests)
  - Information leakage: no stdout leak of infrastructure details (Tier A: 1 test)
  - Data fence integrity: preamble present, payload fenced, structural tags preserved (Tier A: 2 tests)
  - Transport validation: invalid values rejected, valid values accepted (Tier A: 9 tests)
- Not 8: Adversarial tests split across two files (`test_grippy_agent.py` and `test_hostile_environment.py`). NL injection patterns are finite — no test for novel bypass patterns. No property-based testing for `_escape_xml()` with arbitrary Unicode input. Indirect LLM attack surface (agent constructs prompts but doesn't directly process LLM output — that's retry's job).
- Calibration: below codebase (8, 12 adversarial tests with direct LLM-facing tool exposure). Agent has more total adversarial tests but codebase has more direct attack surface (4 LLM-callable tools). Agent's attack surface is indirect (prompt construction) which limits the adversarial depth achievable.

---

### 5. Auditability & Traceability

**Score:** 7/10
**Evidence:**
- **Security rationale comments:** TB-9 history poisoning (`agent.py:263-267`), `_PROVIDERS` structure (`agent.py:61-65`), `_INJECTION_PATTERNS` purpose (`agent.py:75-78`), `_LocalModel` design rationale (`agent.py:29-41`), structured output conditional (`agent.py:254-261`).
- **Transport logging:** `log.info("Grippy transport=%s (source: %s)", ...)` at `agent.py:230` — transport selection and source are logged on every agent creation.
- **Deterministic prompt chain:** `load_identity()` + `load_instructions()` produce the same output for the same inputs. No randomization or dynamic prompt modification.
- **GitHub Actions annotation:** `::notice::` format for API key inference provides visible feedback in CI logs (Tier B).
- Not 8: No structured sanitization telemetry — when `_INJECTION_PATTERNS` match and replace, no log records which patterns fired or what was replaced. `print()` for Tier 3 notice is not captured by logging infrastructure. No audit trail for which `_escape_xml()` calls processed adversarial content vs clean text.
- Calibration: above codebase (6, no tool-call logging). Agent has inline security commentary and logged transport resolution. Below local-diff (7, has structured command logging). Matches graph-store (7, pragma logging + deterministic IDs).

---

### 6. Test Quality

**Score:** 7/10
**Evidence:**
- **Test count:** 41 dedicated tests across 7 classes + ~18 hostile env = ~59 total.
- **Source:test ratio:** 345 LOC source / 565 LOC tests = 1.64:1 test-to-source ratio.
- **Test class breakdown (7 classes):**
  - TestFormatPrContext (16): sections, optional fields, stats, escaping, ordering, review context
  - TestEscapeXml (4): angle brackets, ampersand, passthrough, empty
  - TestOutputSchemaConditional (3): local, openai, anthropic provider-specific schema
  - TestLocalModel (5): tool/response_format conflict regression
  - TestResolveTransport (9): three-tier priority, validation, normalization, all transports
  - TestIdentityOrdering (2): construction wiring, mode forwarding
  - TestDataFenceBoundary (2): fence integrity, structural framing
- **Hostile environment suite:** ~18 agent-relevant tests (Unicode: 7, prompt injection: 8+, history poisoning: 2, info leakage: 1).
- **Fixture categories:** Positive (format_pr_context sections, valid transports), negative (invalid transport, empty inputs), adversarial (XML breakout, NL injection, Unicode attacks, history poisoning), edge cases (normalization, empty tools list).
- Not 8: Adversarial tests split across two files — auditing requires reading both. No integration test that exercises the full `create_reviewer()` → Agent → run path (requires LLM). No property-based testing for `_escape_xml()`. Construction tests use mocks rather than real Agno Agent inspection.
- Calibration: below codebase (9, 106 tests, 1.62:1 ratio, 23 test classes). Below graph-store (9, 81 tests, 17 classes). Agent's test count and class coverage are thinner relative to its security importance.

---

### 7. Convention Adherence

**Score:** 9/10
**Evidence:**
- SPDX header on source and test file (Tier A: `agent.py:1`, `test_grippy_agent.py:1`).
- ruff check passes with zero issues (Tier A).
- mypy strict passes with zero issues (Tier A).
- Test file follows mirror structure: `src/grippy/agent.py` -> `tests/test_grippy_agent.py` (Tier A).
- Test file exceeds 50 LOC minimum (565 LOC) (Tier A).
- Commit message conventions followed (Tier A: git log).
- Calibration: matches codebase (9), graph-store (9), local-diff (9).

---

### 8. Documentation Accuracy

**Score:** 8/10
**Evidence:**
- Module-level docstring: "Grippy agent factory — builds Agno agents for each review mode" — accurate (Tier C).
- `create_reviewer()` docstring: 15-line doc covering all parameters, transport resolution, mode options, return value. Accurate and comprehensive (Tier C).
- `format_pr_context()` docstring: matches actual behavior (Tier C).
- `_resolve_transport()` docstring: documents three-tier priority, return tuple semantics, ValueError condition (Tier C).
- `_LocalModel` docstring: explains tool + structured-output grammar conflict, the two fallback mechanisms, and when response_format passes through (Tier C).
- Security comments: TB-9 rationale (`agent.py:263-267`), _PROVIDERS registry purpose (`agent.py:61-65`), _INJECTION_PATTERNS rationale (`agent.py:75-78`), structured output conditional (`agent.py:254-261`). Each explains the *why*, not just the *what*.
- Not 9: No formal API documentation beyond docstrings. The relationship between `_escape_xml()` (per-field) and `format_pr_context()` (composition) could be documented as a named pipeline.
- Calibration: above codebase (7, fewer security comments), local-diff (8, all functions docstringed). Agent's inline security rationale is the strongest in the project.

---

### 9. Performance

**Score:** 8/10
**Evidence:**
- **Deferred imports:** Provider SDKs loaded via `importlib.import_module()` only when the transport is selected. A local-transport review never loads the anthropic/google/groq/mistral SDKs (Tier B: code trace `agent.py:244-252`).
- **Compiled regex patterns:** `_INJECTION_PATTERNS` compiled at module load, reused across calls (Tier B: `agent.py:79-90`).
- **One-shot prompt composition:** `load_identity()` and `load_instructions()` each read prompt files once. No repeated file I/O during agent construction (Tier B).
- **No hot paths:** Agent factory is called once per review session. `format_pr_context()` is called once per review. Neither is in a loop or called frequently.
- Not 9: `_escape_xml()` applies all 7 regex patterns sequentially to the entire text for each field. No short-circuit on clean input. For large diffs (500K chars), this could be measurable but is bounded by `GRIPPY_MAX_DIFF_CHARS`. No profiling data.
- Calibration: matches codebase (8) and local-diff (8). All have bounded operations and no unnecessary work.

---

### 10. Dead Code / Debt

**Score:** 9/10
**Evidence:**
- `_LocalModel` actively used: local transport path at `agent.py:233` (Tier A: `TestLocalModel` 5 tests).
- All 7 `_INJECTION_PATTERNS` exercised: hostile env tests trigger each pattern category (Tier A: `TestPromptInjectionDefenses`).
- `_VALID_TRANSPORTS` used in validation at `agent.py:153` (Tier A: `test_invalid_transport_raises_valueerror`).
- `_escape_xml()` called by `format_pr_context()` for every metadata field (Tier A: 16 format tests).
- `_resolve_transport()` called by `create_reviewer()` (Tier A: 9 dedicated tests + 3 OutputSchemaConditional tests).
- Zero `TODO` or `FIXME` comments (Tier A: grep search).
- ruff detects no unused imports (Tier A).
- Not 10: `include_rule_findings` parameter in `create_reviewer()` is used only by `review.py` (1 call site with `include_rule_findings=True`) — legitimate but narrow usage.
- Calibration: matches codebase (9), graph-store (9).

---

### 11. Dependency Hygiene

**Score:** 7/10
**Evidence:**
- **Internal deps:** `grippy.prompts` (Phase 2, audited: 7.8/10), `grippy.schema` (Phase 0, audited: 7.7/10). Both audited before agent. No circular imports.
- **External deps:**
  - `navi_sanitize` — security-critical external dependency. `_escape_xml()` pipeline relies on `navi_sanitize.clean()` for invisible char stripping, bidi removal, homoglyph normalization (Tier A: tested through hostile env).
  - `agno` — framework dependency. `Agent`, `OpenAILike` classes. Framework coupling but no alternative (project is built on Agno).
  - `importlib` — stdlib, used for deferred provider SDK loading (Tier A).
  - `os` — stdlib, env var access (Tier A).
  - `re` — stdlib, compiled injection patterns (Tier A).
  - `logging` — stdlib, transport resolution logging.
- **Provider SDKs:** Deferred via `importlib.import_module()`. Not loaded unless transport selected. Each is an optional extra (`grippy-mcp[anthropic]`, etc.).
- Not 8: `navi_sanitize.clean()` is a security-critical external dependency whose contract is trusted but not independently verified in grippy's test suite — changes to that library could silently weaken sanitization. `agno` framework coupling means agent.py depends on Agno's `Agent` constructor signature remaining stable.
- Calibration: matches codebase (7, also depends on navi_sanitize + agno). Below graph-store (8, stdlib only).

---

## Calibration Assessment

agent scores **7.8/10** against calibration peers:
- **local-diff (8.4):** local-diff has simpler scope (1 boundary, 3 functions, stdlib only). Agent has wider attack surface (4 boundaries, 2 public functions, 7 internal components) and more external deps. The 0.6 gap reflects the wider scope and external dependency risk. Agent's stronger security commentary partially compensates but doesn't close the gap.
- **codebase (7.9):** Closest peer. Both are security-critical units with LLM-adjacent attack surfaces. Agent has stronger sanitization (4-layer vs 3-layer) but codebase has stronger adversarial test depth (12 focused tests vs 18+ split tests). The 0.1 gap is appropriate — both are strong units at similar maturity.
- **graph-store (8.0):** graph-store has no LLM-facing exposure and stdlib-only deps. Agent has 4 trust boundaries and external deps. The 0.2 gap reflects the higher risk surface. Graph-store's Healthy status (8.0 exact boundary) vs agent's Adequate (7.8) is consistent — agent has more attack surface requiring more defensive investment.

The framework discriminates between the capstone orchestration unit (agent at 7.8 with 4 TB anchors) and leaf infrastructure (graph-store at 8.0 with 0 TB anchors). The LA checklist added value: LA-02 and LA-04 gaps were identified and closed by Commit 1 test additions. Without those tests, agent would have scored lower on dims 4 and 6. This is the first orchestration unit to achieve a clean (no provisional suffix) Adequate status.

---

## Findings

No findings generated. All 8 LA checklist items PASS with Tier A or A+B evidence. No CRITICAL, HIGH, or MEDIUM gaps identified during audit. The test gaps that existed pre-audit (LA-02 Tier C only, LA-04 zero tests for `_resolve_transport()`) were closed in Commit 1 before scoring, following the evidence-first principle.

### Hypotheses

None.
