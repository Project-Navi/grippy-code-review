<!-- SPDX-License-Identifier: MIT -->

# Audit Scorecard: review

**Audit date:** 2026-03-14
**Commit:** c862022
**Auditor:** Claude Opus 4.6 (AI draft) / Nelson Spence (human reviewer)
**Unit type:** review-pipeline (primary)
**Subprofile:** N/A
**Methodology version:** 1.3

---

## Checklist: RP-01, RP-02, RP-05, RP-08, RP-09

Items RP-03, RP-04, RP-06, RP-07 are scoped to retry or github-review per the RP checklist.

| ID | Invariant | Status | Evidence |
|----|-----------|--------|----------|
| RP-01 | Error paths produce distinguishable error states, not values that look like success | PASS | Tier A: 7 dedicated error-path test classes (`TestMainEarlyExits`, `TestMainDiffFetchErrors`, `TestMainProfileError`, `TestMainTimeoutError`, `TestMainNestedErrorHandlers`, `TestMainPostReviewFailure`, `TestTransportErrorUX`). 7 distinct `_failure_comment()` error types (CONFIG ERROR, DIFF ERROR, PARSE ERROR, TIMEOUT, ERROR, POST ERROR, CONFIG ERROR for profile). Every error path ends with `sys.exit(1)` + `::error::` or `::warning::` annotation. No error path returns `None` or writes a score to `GITHUB_OUTPUT`. The `_check_already_reviewed` early exit correctly uses `sys.exit(0)` with valid outputs — tested by `TestMainSameCommitGuard`. |
| RP-02 | All LLM-generated text is sanitized before posting to external APIs | PASS (delegated) | Tier B: review.py does NOT sanitize LLM output directly. It delegates posting entirely to `github_review.post_review()` (call at `review.py:679`). **Delegation is complete:** no code path in review.py directly posts LLM-generated content to GitHub. `post_comment()` (`review.py:177-184`) is used only for static error messages via `_failure_comment()`. `_escape_rule_field()` (`review.py:215-223`) sanitizes rule findings for the LLM *prompt* (navi_sanitize + XML escape), which is input-side, not output-side. review gets credit for delegating correctly, not for implementing sanitization. See github-review scorecard for the actual TB-6 defense. |
| RP-05 | Deterministic rules run on full diff; LLM sees truncated diff | PASS | Tier B: `run_rules(diff, profile_config)` at `review.py:522`, then `diff = truncate_diff(diff)` at `review.py:537`. Same variable, 15 lines apart, strictly sequential inside `main()`. `original_len = len(diff)` captured at line 536 before truncation; `diff_truncated` flag set at line 538. The rule engine also operates on the pre-`filter_diff()` result (line 490 filters, line 522 runs rules on filtered-but-untruncated diff). No test explicitly verifies this ordering as an invariant — the evidence is a deterministic code trace through the sequential `main()` flow. |
| RP-08 | CI pipeline correctly sets exit code and Actions outputs on all verdict paths | PASS | Tier A: `TestMainOrchestration` and `TestMainWiringNewAPI` verify `GITHUB_OUTPUT` writes. Lines 786-794: outputs written for score, verdict, findings-count, merge-blocking, rule-findings-count, rule-gate-failed, profile. Lines 797-802: `sys.exit(1)` for `rule_gate_failed` OR `review.verdict.merge_blocking`. Lines 344-354: early-exit path writes correct outputs. `TestMainRuleEngine` tests gate-failed exit behavior. |
| RP-09 | Review timeout enforced with clean exit | PASS | Tier A: `TestReviewTimeout` class. `_with_timeout()` (`review.py:187-204`) uses `signal.SIGALRM` with handler restoration in `finally` block. `TimeoutError` caught at `review.py:644-655` with distinct "TIMEOUT" error comment and `sys.exit(1)`. `_ERROR_HINTS["TIMEOUT"]` provides user guidance. |

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
| 1. Contract Fidelity | 7/10 | A | All functions typed, mypy strict clean. `main()` uses `sys.exit()` as control flow. PR event as untyped `dict[str, Any]`. |
| 2. Robustness | 8/10 | A | 7 distinct error categories with dedicated handlers. SIGALRM timeout. Non-fatal degradation for indexing/graph/re-review. |
| 3. Security Posture | 7/10 | A + B | TB-1 via `_escape_rule_field()` + delegation to agent's `format_pr_context()`. TB-2 via `fetch_pr_diff()`. Title newline stripping. `.dev.vars` gated on `not CI`. Posting fully delegated to TB-6. |
| 4. Adversarial Resilience | 6/10 | A + C | 4 hostile env tests relevant. `_escape_rule_field()` for rule injection. Title annotation injection defense. Adversarial exposure primarily via delegation to agent/github-review. |
| 5. Auditability & Traceability | 6/10 | B + C | GitHub Actions `::error::`/`::warning::` annotations. Distinct `_failure_comment()` error types. But: 523-LOC `main()` is hard to trace. No structured logging. |
| 6. Test Quality | 8/10 | A | 78 tests, 22 classes, 2103 LOC (2.61:1 ratio). Strong error-path coverage. Rule engine integration tests. Missing: no RP-05 ordering test as explicit invariant. |
| 7. Convention Adherence | 9/10 | A | SPDX header, ruff clean, mypy strict clean, test mirror at 2103 LOC. |
| 8. Documentation Accuracy | 7/10 | C | Module docstring with env var list. Function docstrings accurate. No inline security comments explaining RP-02 delegation strategy. |
| 9. Performance | 7/10 | B | File-boundary-aware `truncate_diff()`. Rules on full diff before truncation. Deferred imports. Two full iterations of py_files in graph build. |
| 10. Dead Code / Debt | 8/10 | A | All functions called. `_SEVERITY_MAP`, `_ERROR_HINTS` used. Zero TODOs. `fetch_changed_since()` narrow usage (re-review only) but legitimate. |
| 11. Dependency Hygiene | 6/10 | A | 12+ grippy imports (heaviest in project). External: requests, github, navi_sanitize, agno. Deferred: lancedb, agno.vectordb. Expected for orchestrator role. |
| **Overall** | **7.2/10** | | **Average of 11 dimensions** |

**Health status:** Adequate

**Determination:**
1. Average-based status: 7.2/10 falls in 6.0-7.9 range = **Adequate**
2. Override gates: None fired.
3. Ceiling gates: None fired. All gate dimensions >= 6.
4. Suffixes: No `(provisional)` — Dim 3 (7/10) supported by Tier A (`TestMainEarlyExits`, `TestMainDiffFetchErrors`, `_escape_rule_field` tests, hostile env) + Tier B (RP-02 delegation trace). Dim 4 (6/10) supported by Tier A (hostile env: `test_failure_comment_no_path_leak`, `test_annotation_injection_via_pr_title`, `test_xml_breakout_in_rule_findings_escaped`) + Tier C (delegation trace). Not exclusively Tier C — Tier A tests anchor both dimensions.

**Override gates fired:** None
**Ceiling gates fired:** None

---

## Compound Chain Exposure

review participates in all 4 applicable chains (CH-1 through CH-4) as orchestrator. It does not participate in CH-5 (History Poisoning — that's agent's domain).

### CH-1: Prompt Injection -> Fabricated Finding -> Merge Block

**Role:** Origin + Relay — loads PR metadata, delegates sanitization to agent, passes context to LLM.

**Data flow:**
```
load_pr_event() [review.py:319] → pr_event dict (untrusted title, author, description)
  → _escape_rule_field() [review.py:271-279] sanitizes rule findings
  → format_pr_context() [agent.py, called at review.py:610-618] sanitizes all PR metadata
  → run_review() [review.py:623-631] sends sanitized prompt to LLM
```

**Circuit breakers:**
1. `_escape_rule_field()` (`review.py:215-223`): navi_sanitize + XML escape on rule finding fields before they enter the prompt.
2. Title newline stripping (`review.py:320`): prevents annotation injection via `::error::` in PR title.
3. Delegation to agent's `format_pr_context()`: 4-layer sanitization pipeline (navi_sanitize → NL injection patterns → XML escape → data fence).

### CH-2: Path Traversal -> Data Exfiltration -> Prompt Leakage

**Role:** Relay — provides codebase tools to the agent.

**Data flow:**
```
CodebaseToolkit [review.py:424] + sanitize_tool_hook [review.py:548]
  → create_reviewer(tools=codebase_tools, tool_hooks=[sanitize_tool_hook]) [review.py:551-563]
  → LLM tool calls bounded by codebase.py's is_relative_to() + sanitize_tool_hook()
```

**Circuit breaker:** review.py wires `sanitize_tool_hook` (from `codebase.py`) into the agent. Defense is owned by codebase unit (TB-4). review.py's role is correct wiring — tested by `TestMainWiringNewAPI`.

### CH-3: Output Injection -> GitHub Comment XSS/Phishing

**Role:** Relay — passes LLM output from `run_review()` to `post_review()`.

**Data flow:**
```
run_review() [retry.py, called at review.py:623-631]
  → GrippyReview with findings (untrusted LLM output, Pydantic-validated)
  → review.model = model_id [review.py:670] (override self-reported model)
  → post_review(findings=review.findings, ...) [review.py:679-689]
  → github_review.py owns sanitization from here (TB-6)
```

**Circuit breaker:** review.py does NOT sanitize LLM output. It delegates entirely to `github_review.post_review()`. The delegation is complete — there is no code path in review.py that directly creates GitHub comments with LLM content. The relay role is correct: review.py transports validated Pydantic objects to github_review's sanitization pipeline.

**Cross-unit note:** This is the key pairing rationale for Phase 3B. review.py trusts that github_review.py's 5-stage `_sanitize_comment_text()` pipeline defends TB-6. Verified in github-review scorecard.

### CH-4: Rule Bypass -> Silent Vulnerability Pass

**Role:** Origin — executes rule engine on full diff.

**Data flow:**
```
diff = fetch_pr_diff() [review.py:463] → full diff
  → diff = filter_diff(diff, spec) [review.py:490] → filtered but untruncated
  → rule_findings = run_rules(diff, profile_config) [review.py:522] → rules on full diff
  → diff = truncate_diff(diff) [review.py:537] → LLM sees truncated version
  → expected_rule_counts / expected_rule_files [review.py:528-532] → passed to run_review()
    → retry.py's _validate_rule_coverage() ensures LLM doesn't hallucinate/drop findings
```

**Circuit breaker:** RP-05 ordering invariant — rules execute on full diff (line 522), truncation happens after (line 537). Rule coverage validation (`_validate_rule_coverage()` in retry.py) cross-references LLM findings against deterministic rule findings. Defense-in-depth: deterministic rules + LLM validation + coverage check.

---

## Dimension Details

### 1. Contract Fidelity

**Score:** 7/10
**Evidence:**
- mypy strict passes with zero issues (Tier A).
- All public functions typed: `load_pr_event(Path) -> dict[str, Any]`, `truncate_diff(str, int) -> str`, `fetch_pr_diff(str, str, int) -> str`, `fetch_changed_since(str, str, str, str) -> list[str]`, `post_comment(str, str, int, str) -> None`, `main(*, profile: str | None) -> None` (Tier A).
- Internal functions typed: `_with_timeout(Callable[[], Any], *, timeout_seconds: int) -> Any`, `_escape_rule_field(str) -> str`, `_check_already_reviewed(Any, str, *, pr_number: int) -> dict[str, Any] | None`, `_format_rule_findings(list[RuleResult]) -> str` (Tier A).
- `_ERROR_HINTS: dict[str, str]` and `_SEVERITY_MAP: dict[RuleSeverity, str]` — typed constants (Tier A).
- Not 8: `main()` uses `sys.exit()` as control flow — exit codes are the "return values" but this is implicit, not contractual. `load_pr_event()` returns `dict[str, Any]` instead of a typed dataclass. `_check_already_reviewed(pr: Any, ...)` uses `Any` for PyGithub's PullRequest type. `_with_timeout()` returns `Any`.
- Calibration: matches graph-context (7), below agent (8) and codebase (8). The untyped PR event dict and `sys.exit()` control flow justify the gap.

---

### 2. Robustness

**Score:** 8/10
**Evidence:**
- **7 distinct error categories:** CONFIG ERROR (transport/profile), DIFF ERROR (fetch failure + 403 hint), PARSE ERROR (review parse failure), TIMEOUT (SIGALRM), ERROR (generic agent failure), POST ERROR (posting failure). Each has a distinct `_failure_comment()` template and `sys.exit(1)` (Tier A: 7 dedicated test classes).
- **SIGALRM timeout:** `_with_timeout()` at `review.py:187-204`. Handler installed, alarm set, restored in `finally`. Tested by `TestReviewTimeout` (Tier A).
- **Non-fatal degradation:** Codebase indexing (`review.py:425-426`), graph store init (`review.py:456-458`), graph context query (`review.py:587`), re-review detection (`review.py:357-358`), graph persistence (`review.py:781-782`), thread resolution — all wrapped in `try/except` with `::warning::` annotations. Pipeline continues without these components.
- **Error comment posting:** All error paths attempt to post a `_failure_comment()` to the PR, wrapped in `try/except: pass` (`nosec B110` annotated) to prevent masking the original error.
- Not 9: `bare except: pass` pattern on error comment posting is correct but not ideal — failures to post error comments are completely silent. No retry on transient HTTP errors in `fetch_pr_diff()`. `requests.get()` has 60s timeout but no retry with backoff.
- Calibration: matches codebase (8) and local-diff (8). Strong error handling for an orchestration unit. Above graph-context (6).

---

### 3. Security Posture

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 7/10
**Evidence:**
- **TB-1 defense (rule finding injection):** `_escape_rule_field()` at `review.py:215-223`: `navi_sanitize.clean()` + XML entity escape (`& < >`). Applied to file, message, and evidence fields before they enter the LLM prompt. Tested: `test_xml_breakout_in_rule_findings_escaped` in hostile env (Tier A).
- **TB-1 defense (PR metadata):** Delegated to agent's `format_pr_context()`. review.py calls `format_pr_context()` at line 610-618 with raw PR metadata — agent's 4-layer pipeline sanitizes. Delegation is complete (Tier B: call trace).
- **TB-2 defense (diff ingestion):** `fetch_pr_diff()` at `review.py:127-142` uses `requests.get()` with `Authorization` header and 60s timeout. Diff is treated as opaque text — no structural parsing that could be exploited. `filter_diff()` (from ignore module, audited) removes excluded files.
- **Title annotation injection:** `review.py:320`: `pr_event["title"].replace("\n", " ").replace("\r", " ")` prevents `::error::` annotation injection via newlines in PR title. Tested: `test_annotation_injection_via_pr_title` in hostile env (Tier A).
- **`.dev.vars` protection:** `review.py:286-293`: dev vars loaded only when `not os.environ.get("CI")`. Never in production.
- **RP-02 delegation:** All LLM output posting delegated to `github_review.post_review()`. No direct posting of untrusted content (Tier B: call trace).
- Not 8: 523-LOC `main()` makes it harder to verify no sanitization gaps exist. No independent defense — relies entirely on agent (TB-1) and github-review (TB-6) for their respective boundaries. `fetch_changed_since()` passes untrusted `before` SHA to GitHub compare API — not exploitable (GitHub validates SHAs) but no input validation in review.py itself.
- Calibration: below agent (9, owns 4-layer sanitization pipeline) and codebase (8, 5 independent defensive layers). Matches graph-context (7). review.py's security posture is primarily through delegation to stronger units.

---

### 4. Adversarial Resilience

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 6/10
**Evidence:**
- **Hostile environment tests (review-relevant):** 4 tests directly exercise review.py functions:
  - `test_failure_comment_no_path_leak` — error messages don't leak `/home` or traceback (Tier A)
  - `test_annotation_injection_via_pr_title` — newline stripping prevents `::error::` injection (Tier A)
  - `test_xml_breakout_in_rule_findings_escaped` — `_escape_rule_field()` neutralizes XML payloads (Tier A)
  - `test_fork_403_no_dangerous_trigger_advice` — source code doesn't suggest `pull_request_target` (Tier A)
- **`_escape_rule_field()`:** Direct adversarial defense for rule findings entering the LLM prompt. Two-layer: navi_sanitize (Unicode normalization) + XML escape (Tier A).
- **Delegation-based defense:** review.py's primary adversarial resilience comes from delegating to agent (prompt sanitization) and github-review (output sanitization). The delegation is correct and complete (Tier B).
- Not 7: Only 4 direct adversarial tests for 806 LOC. Most adversarial defense is inherited from agent and github-review. No adversarial test for the graph persistence path (lines 704-782) — attacker-crafted finding.category or finding.title could contain adversarial content that reaches `navi_sanitize.clean()` at line 747 before graph storage, but this is defense-in-depth (graph is not externally visible). No test for crafted `GITHUB_OUTPUT` manipulation. The 523-LOC `main()` makes exhaustive adversarial trace difficult.
- Calibration: below codebase (8, 12 direct adversarial tests on LLM-facing tools) and agent (7, 18+ adversarial tests on sanitization pipeline). review.py's adversarial surface is primarily indirect (orchestration), which limits the depth of adversarial testing achievable. 6 is appropriate for a unit that defends through delegation rather than direct defense.

---

### 5. Auditability & Traceability

**Score:** 6/10
**Evidence:**
- **GitHub Actions annotations:** `::error::` for fatal failures, `::warning::` for non-fatal degradation. Each error type is distinct and actionable (Tier B: code trace of 7 error categories).
- **Distinct error types:** `_failure_comment()` produces distinct error comments (CONFIG ERROR, DIFF ERROR, etc.) with `_ERROR_HINTS` for CONFIG ERROR and TIMEOUT. Error comments include Actions log link (Tier B).
- **Step logging:** `print()` statements at each pipeline stage: "Fetching PR diff...", "Running rule engine...", "Running review...", "Posting review..." (Tier C).
- **Summary stats:** File count, char count, indexing stats, graph stats, rule finding count, gate status, score, verdict all printed (Tier B).
- Not 7: 523-LOC `main()` is the primary audit concern. Tracing a specific error path requires reading through 500+ lines of sequential code with nested try/except blocks. No structured logging (`print()` throughout, not `logging`). No correlation ID linking a review session across steps. Pipeline stages are identifiable by print statements but not machine-parseable. Graph persistence (lines 704-782) is ~80 LOC with no intermediate logging.
- Calibration: matches codebase (6, logger exists but no tool-call tracing). Below local-diff (7, structured command logging). The monolithic `main()` is the differentiator — other units have smaller, traceable functions.

---

### 6. Test Quality

**Score:** 8/10
**Evidence:**
- **Test count:** 78 tests across 22 test classes, 2103 LOC = 2.61:1 test-to-source ratio.
- **Test class breakdown (22 classes):**
  - TestLoadPrEvent (4): valid event, missing PR key, description fallback, encoding
  - TestFetchChangedSince (3): success, API error, empty result
  - TestFetchPrDiff (4): success, HTTP error, auth header, timeout
  - TestFetchPrDiffForkHandling (2): fork 403 hint, non-fork 403
  - TestPostComment (2): success, PyGithub call verification
  - TestFailureComment (3): error types, run ID, no run ID
  - TestMainWiringNewAPI (3): full pipeline wiring, output writing, post_review call verification
  - TestTruncateDiff (6): under limit, exact limit, over limit, file boundaries, preamble, multiple files
  - TestReviewTimeout (3): timeout fires, no timeout (0), timeout cleanup
  - TestMainOrchestration (5): full pipeline mock, verdict paths, output format
  - TestMainReviewIntegration (3): integration with mocked agent
  - TestMainPostReviewFailure (2): post failure non-fatal, fallback error comment
  - TestTransportErrorUX (3): invalid transport, missing API key, env fallback
  - TestMainRuleEngine (5): profile loading, rule execution, gate behavior, mode switch, non-security profile
  - TestFormatRuleFindings (4): basic format, severity levels, evidence, multi-finding
  - TestMainEarlyExits (4): no token, no event path, missing event file, bad JSON
  - TestMainDiffFetchErrors (3): HTTP error, 403 fork, network error
  - TestMainProfileError (2): invalid profile, error comment
  - TestMainTimeoutError (2): timeout, error comment
  - TestMainNestedErrorHandlers (2): error comment fails, double failure
  - TestCheckAlreadyReviewed (7): match, no verdict, wrong SHA, no summary, workflow_dispatch bypass, multiple reviews, malformed meta
  - TestMainSameCommitGuard (5): skip on match, no skip on mismatch, non-fatal failure, workflow_dispatch bypass, output writing
- **Fixture categories:** Positive (15), negative (18), error paths (25), edge cases (12), integration (8). Strong error-path coverage — the orchestrator's primary complexity is error handling.
- **Hostile environment:** 4 review-specific tests + 2 shared (`test_fork_403_no_dangerous_trigger_advice`, `test_annotation_injection_via_pr_title`).
- Not 9: No explicit RP-05 ordering test (rules-before-truncation verified by code trace only). No adversarial fixture matrix specifically for review.py (adversarial tests are in hostile env, not organized as a matrix). No integration test exercising the full `main()` with a real diff + rule engine (all integration tests mock at the agent/review boundary).
- Calibration: below codebase (9, 101 tests with adversarial matrices) and graph-store (9, 81 tests). Above agent (7, 41 tests). review.py's test suite is strongest on error path coverage but weaker on adversarial depth.

---

### 7. Convention Adherence

**Score:** 9/10
**Evidence:**
- SPDX header on source and test file (Tier A: `review.py:1`, `test_grippy_review.py:1`).
- ruff check passes with zero issues (Tier A).
- mypy strict passes with zero issues (Tier A).
- Test file follows mirror structure: `src/grippy/review.py` -> `tests/test_grippy_review.py` (Tier A).
- Test file exceeds 50 LOC minimum (2103 LOC) (Tier A).
- `nosec B110` annotations on `except: pass` blocks with inline rationale (Tier A).
- Calibration: matches agent (9), codebase (9), graph-store (9).

---

### 8. Documentation Accuracy

**Score:** 7/10
**Evidence:**
- Module-level docstring with complete env var listing (12 variables with descriptions) — accurate and comprehensive (Tier C).
- `load_pr_event()` docstring: documents return keys, raises conditions — accurate (Tier C).
- `truncate_diff()` docstring: accurately describes file-boundary splitting (Tier C).
- `fetch_pr_diff()` docstring: accurately describes raw diff endpoint (Tier C).
- `_check_already_reviewed()` docstring: accurately documents dual-marker completeness check (Tier C).
- `_with_timeout()` docstring: accurately documents SIGALRM behavior and Linux-only limitation (Tier C).
- Not 8: No inline comment explaining the RP-02 delegation strategy (why review.py doesn't sanitize posting output). No comment explaining the RP-05 ordering invariant (why `run_rules()` must precede `truncate_diff()`). The 523-LOC `main()` has step comments ("1. Parse event", "2. Validate transport") but no architectural overview explaining the pipeline stages or error handling strategy.
- Calibration: matches codebase (7) and graph-store (7). Below agent (8, which has security rationale comments). review.py has good function docs but lacks the security annotations that agent demonstrates.

---

### 9. Performance

**Score:** 7/10
**Evidence:**
- **File-boundary truncation:** `truncate_diff()` splits on `"diff --git"` markers, keeping complete files rather than cutting mid-file. `O(n)` on diff size (Tier B: code trace `review.py:97-124`).
- **Rules on full diff:** RP-05 ordering means rules get complete file context, while the LLM context is bounded by `MAX_DIFF_CHARS` (500K default) (Tier B).
- **Deferred imports:** `requests`, `github.Github`, `agno.vectordb`, `lancedb` all imported lazily — only when their code path is reached (Tier B).
- **Itertools cap:** `itertools.islice(ws.rglob("*.py"), 5000)` bounds graph file scanning at `review.py:434` (Tier B).
- Not 8: Two full iterations of `py_files` list at lines 434-454: once for file node upsert, once for import edge extraction. Could be combined but is bounded (5000 files). `_check_already_reviewed()` iterates all reviews AND all issue comments — O(reviews + comments) per PR, no caching. `fetch_changed_since()` makes an additional API call on re-reviews.
- Calibration: below codebase (8, monotonic timeouts + subprocess timeouts + bounded results). review.py has no hot paths but the two-pass graph iteration and unbounded review iteration are mild concerns.

---

### 10. Dead Code / Debt

**Score:** 8/10
**Evidence:**
- All public functions called: `load_pr_event()` by `main()`, `truncate_diff()` by `main()`, `fetch_pr_diff()` by `main()`, `post_comment()` by 6 error paths, `main()` by `__main__.py` (Tier A).
- `_ERROR_HINTS` dict used by `_failure_comment()` (Tier A: `TestFailureComment`).
- `_SEVERITY_MAP` dict used by `_format_rule_findings()` (Tier A: `TestFormatRuleFindings`).
- `_escape_rule_field()` used by `_format_rule_findings()` (Tier A).
- `_check_already_reviewed()` used by `main()` same-commit guard (Tier A: `TestCheckAlreadyReviewed` 7 tests).
- `fetch_changed_since()` used in re-review path only — legitimate narrow usage (Tier B).
- Zero `TODO` or `FIXME` comments (Tier A).
- ruff detects no unused imports (Tier A).
- Not 9: `MAX_DIFF_CHARS` is a module-level constant read from env var — always evaluated even when not needed (e.g., MCP mode doesn't use review.py). Minor.
- Calibration: matches agent (9 would be too high — agent has tighter usage). Below agent (9) and codebase (9). The narrow usage of `fetch_changed_since()` and always-evaluated `MAX_DIFF_CHARS` are minor but present.

---

### 11. Dependency Hygiene

**Score:** 6/10
**Evidence:**
- **Internal deps (12+ from grippy.*):** agent (format_pr_context, create_reviewer), codebase (CodebaseIndex, CodebaseToolkit, sanitize_tool_hook), embedder (create_embedder), github_review (post_review), graph_context (build_context_pack, format_context_for_llm), graph_store (SQLiteGraphStore), graph_types (EdgeType, MissingNodeError, NodeType, _record_id), ignore (filter_diff, load_grippyignore), imports (extract_imports), local_diff (get_repo_root), retry (ReviewParseError, run_review), rules (RuleResult, RuleSeverity, check_gate, load_profile, run_rules), rules.enrichment (enrich_results, persist_rule_findings) (Tier A).
- **External deps:** `navi_sanitize` (security-critical), `requests` (HTTP), `github` (PyGithub), `agno` (framework), `lancedb` (vector store) — all deferred except navi_sanitize (Tier A).
- **No circular imports** (Tier A: ruff check).
- Not 7: Heaviest dependency graph in the project — 12+ internal modules, 5+ external. This is expected for the top-level orchestrator but creates a wide blast radius for changes. Any breaking change in agent, codebase, github_review, retry, or rules affects review.py directly. The deferred imports mitigate startup cost but not coupling.
- Calibration: below agent (7, 2 internal deps) and codebase (7, 0 internal deps). Below github-review (very isolated). review.py's orchestration role justifies the fan-out, but the coupling is real.

---

## Calibration Assessment

review scores **7.2/10** against calibration peers:
- **agent (7.8):** Agent has narrower scope (prompt construction + sanitization), stronger direct security investment (4-layer pipeline, 18+ adversarial tests), and fewer dependencies. review.py is wider (orchestrates 12+ modules) but delegates most security to agent and github-review. The 0.6 gap reflects the orchestrator penalty: wider scope, more dependencies, lower auditability due to monolithic `main()`.
- **codebase (7.9):** Codebase has 5 independent defensive layers, 12 adversarial tests, and self-contained security. review.py's security is primarily through delegation. The 0.7 gap reflects the difference between "owns its defenses" (codebase) and "delegates its defenses" (review).
- **retry (7.9):** Retry has focused scope (JSON parsing + validation), strong RP-03/04/06 coverage, and targeted adversarial defense. review.py is broader and less focused. The 0.7 gap is appropriate.
- **local-diff (8.4):** Simplest peer — 3 public functions, stdlib only, 1 boundary. review.py at the opposite extreme — most complex unit, most dependencies, widest scope. The 1.2 gap is the largest in the project and reflects genuine architectural difference.

The framework discriminates between the top-level orchestrator (review at 7.2 with 2 TB anchors, 12+ deps) and focused units (agent at 7.8 with 4 TB anchors, 2 deps). review.py's Adequate status is appropriate — it correctly delegates security to stronger units but the monolithic `main()` and wide dependency graph limit its standalone quality.

---

## Findings

No findings generated. All 5 scoped RP checklist items PASS. No CRITICAL, HIGH, or MEDIUM gaps identified during audit.

**Key observations (not findings):**
- RP-05 ordering is verified by code trace (Tier B) not by an explicit test (Tier A). This is an acceptable evidence tier for a structural ordering invariant, but a targeted test would strengthen the evidence to Tier A.
- The 523-LOC `main()` is an architectural choice, not a defect. It makes auditing harder but the pipeline stages are clearly delineated by comments and print statements.
- RP-02 delegation is complete and correct but undocumented — no inline comment explains why review.py doesn't sanitize posting output.

### Hypotheses

None.
