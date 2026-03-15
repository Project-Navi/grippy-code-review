<!-- SPDX-License-Identifier: MIT -->

# Audit Scorecard: github-review

**Audit date:** 2026-03-14
**Commit:** c862022
**Auditor:** Claude Opus 4.6 (AI draft) / Nelson Spence (human reviewer)
**Unit type:** review-pipeline (primary)
**Subprofile:** N/A
**Methodology version:** 1.3

---

## Checklist: RP-01, RP-02, RP-07

Items RP-03, RP-04, RP-05, RP-06, RP-08, RP-09 are scoped to retry or review per the RP checklist.

| ID | Invariant | Status | Evidence |
|----|-----------|--------|----------|
| RP-01 | Error paths produce distinguishable error states, not values that look like success | PASS | Tier A: `TestFetchGrippyComments`, `TestFetchThreadStates`, `TestResolveThreads`, `TestPostReview422Fallback` all test error paths. Every error path returns an empty/zero result or degrades gracefully: `parse_diff_lines("")` → `{}`, `fetch_grippy_comments()` subprocess failure → `::warning::` + `{}`, `fetch_thread_states()` failure → `{}`, `resolve_threads()` failure → `0`, `post_review()` 422 → fallback to off-diff (findings preserved, not dropped). Verdict review failure → `::warning::` (non-fatal). No error path produces a value that looks like a successful posting. |
| RP-02 | All LLM-generated text is sanitized before posting to external APIs | PASS | Tier A: `TestCommentSanitization` (dedicated class) + `TestOutputSanitizationGaps` in hostile env (8 tests). `_sanitize_comment_text()` (`github_review.py:145-163`) implements a 5-stage pipeline: (1) `navi_sanitize.clean()` — invisible chars, bidi, homoglyphs, NFKC, (2) `nh3.clean(text, tags=set())` — HTML tag stripping, (3) markdown image removal — tracking pixel defense, (4) markdown link rewriting — phishing prevention, (5) `_DANGEROUS_SCHEME_RE.sub("", unquote(text))` — dangerous URI scheme filter with URL decoding. Called on all LLM-generated fields: `build_review_comment()` (`github_review.py:201-204`) sanitizes title, description, suggestion, grippy_note. `format_summary_comment()` (`github_review.py:398-401`) sanitizes off-diff finding fields. `_sanitize_path()` (`github_review.py:179-182`) provides separate path sanitization with allowlist regex. |
| RP-07 | Repeated reviews do not accumulate duplicate comments | PASS | Two distinct sub-behaviors verified separately: **Same-run duplicate suppression:** `post_review()` at `github_review.py:526-533` fetches existing comments by marker key `(file, category, line)`, skips findings that already have matching markers. Tested by `TestPostReview` (Tier A). **Repeated-run stale-thread resolution:** Lines 535-546 identify absent comments (existing markers not in current findings), then `fetch_thread_states()` checks GitHub's `isOutdated` flag. Only threads that are both absent AND GitHub-marked-outdated AND not-already-resolved get resolved. `resolve_threads()` uses batched GraphQL mutation with `$id{i}` variable binding. Tested by `TestResolveThreads`, `TestFetchThreadStates`, `TestResolveThreadsBatchSafety` (Tier A). **Conservative design:** resolution requires two independent signals (absent from current findings + GitHub marks outdated), preventing premature resolution of findings that moved in the diff but are still valid. |

---

## Gate Rules

### Override Gates (force a specific status)

| Override Gate | Condition | Fired? |
|---|---|---|
| Critical finding | Any unresolved CRITICAL finding | No |
| Multi-HIGH block | 2+ unresolved HIGH findings (including provisional) | No (0 HIGH findings) |
| Security collapse | Security Posture < 2 | No (score: 9) |
| Adversarial collapse | Adversarial Resilience < 2 | No (score: 8) |

### Ceiling Gates (cap the best allowed status)

| Ceiling Gate | Condition | Fired? |
|---|---|---|
| Severity cap | Any unresolved HIGH finding | No |
| Security hard floor | Security Posture < 4 | No (score: 9) |
| Adversarial hard floor | Adversarial Resilience < 4 | No (score: 8) |
| Security soft floor | Security Posture < 6 | No (score: 9) |
| Adversarial soft floor | Adversarial Resilience < 6 | No (score: 8) |
| Accepted critical risk | Any ACCEPTED_RISK at CRITICAL | No |
| Accepted high risk | Any ACCEPTED_RISK at HIGH | No |

---

## Summary

| Dimension | Score | Evidence Tier | Notes |
|-----------|------:|:---:|-------|
| 1. Contract Fidelity | 8/10 | A | `ThreadRef` NamedTuple. All functions typed. `post_review()` 9 keyword-only params. mypy strict clean. |
| 2. Robustness | 8/10 | A | 422 fallback to off-diff. Non-fatal thread resolution. Subprocess timeouts. Paginated fetching with 20-page safety limit. Summary upsert. |
| 3. Security Posture | 9/10 | A | 5-stage `_sanitize_comment_text()` pipeline. `_sanitize_path()` with allowlist. GraphQL variable binding. `_DANGEROUS_SCHEME_RE` with `unquote()`. |
| 4. Adversarial Resilience | 8/10 | A | 8 hostile env tests. `TestCommentSanitization`. 5-stage pipeline tested per-stage and combined. Tracking pixel, phishing, URL-encoding bypass all defended. |
| 5. Auditability & Traceability | 7/10 | B | Well-separated functions. Marker-based thread tracking. `::warning::` for non-fatal failures. Step logging in `post_review()`. |
| 6. Test Quality | 9/10 | A | 87 tests, 17 classes, 1894 LOC (2.46:1 ratio). Highest test density for pipeline units. RP-07 sub-behaviors tested separately. |
| 7. Convention Adherence | 9/10 | A | SPDX, ruff clean, mypy strict clean, test mirror at 1894 LOC. |
| 8. Documentation Accuracy | 7/10 | C | Function docstrings on all public functions. Marker format documented inline. |
| 9. Performance | 7/10 | B | Batched inline comments (25). Batched thread resolution (single GraphQL mutation). Paginated fetching. Subprocess timeouts. |
| 10. Dead Code / Debt | 9/10 | A | All functions called. `ThreadRef` used throughout. Zero TODOs. |
| 11. Dependency Hygiene | 9/10 | A | Only imports `Finding` from grippy.schema internally. External: navi_sanitize, nh3, github (PyGithub). Very isolated. |
| **Overall** | **8.2/10** | | **Average of 11 dimensions** |

**Health status:** Healthy

**Determination:**
1. Average-based status: 8.2/10 falls in 8.0+ range = **Healthy**
2. Override gates: None fired.
3. Ceiling gates: None fired. All gate dimensions >= 6.
4. Suffixes: No `(provisional)` — Dim 3 (9/10) supported by Tier A (8 hostile env tests, `TestCommentSanitization`, `_sanitize_comment_text` pipeline tests). Dim 4 (8/10) supported by Tier A (hostile env output sanitization tests, build_review_comment sanitization tests).

**Override gates fired:** None
**Ceiling gates fired:** None

---

## Compound Chain Exposure

github-review participates in 1 of the 5 compound chains, as the **terminus**.

### CH-3: Output Injection -> GitHub Comment XSS/Phishing

**Role:** Terminus — all LLM-generated text passes through TB-6 sanitization before reaching GitHub API.

**Data flow (complete cross-unit CH-3 trace):**
```
LLM output → run_review() [retry.py] → GrippyReview (Pydantic-validated)
  → review.py:679 post_review(findings=review.findings, ...)
  → github_review.py:489 post_review() entry
    ├─ Inline path:
    │   → classify_findings() [line 557] → inline findings
    │   → build_review_comment(f) [line 567] for each inline finding
    │     → _sanitize_comment_text() [line 201-204] on title, description, suggestion, grippy_note
    │     → _sanitize_path() [line 218] on finding.file
    │   → pr.create_review(comments=batch) [line 571] → GitHub API
    │
    └─ Summary path:
        → format_summary_comment(off_diff_findings=off_diff) [line 630]
          → _sanitize_comment_text() [line 398-401] on off-diff finding fields
          → _sanitize_path() [line 402] on off-diff file paths
        → pr.create_issue_comment(summary) [line 649] → GitHub API
```

**5-stage sanitization pipeline (TB-6 defense):**
1. `navi_sanitize.clean()` — Unicode normalization: invisible chars (zero-width), bidi overrides, homoglyphs, tag characters, NFKC normalization
2. `nh3.clean(text, tags=set())` — HTML stripping: removes all HTML tags including `<script>`, `<img>`, `<iframe>`
3. `re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)` — Markdown image removal: blocks tracking pixels (`![](https://evil.com/tracker.png)`)
4. `re.sub(r"\[([^\]]*)\]\(https?://[^)]+\)", r"\1", text)` — Markdown link rewriting: strips external links, preserves link text (phishing defense)
5. `_DANGEROUS_SCHEME_RE.sub("", unquote(text))` — Dangerous URI scheme filter: `javascript:`, `data:`, `vbscript:` with URL-decoding to catch `javascript%3A` encoding bypass

**Circuit breakers:**
1. Each stage is independently useful — bypassing one stage doesn't bypass all 5.
2. `nh3` is an independent Rust-based HTML sanitizer (not custom regex).
3. `unquote()` before scheme check defeats URL-encoding evasion.
4. `_sanitize_path()` uses a separate allowlist (`[a-zA-Z0-9_./ -]`) — not the same pipeline as text sanitization.
5. All four text fields in `build_review_comment()` pass through `_sanitize_comment_text()` — no field is bypassed.

**Residual risk:** Stage 3 (markdown image regex) and stage 4 (markdown link regex) use patterns that could potentially be bypassed by deeply nested or malformed markdown. However, stages 1 (Unicode normalization) and 2 (HTML stripping) run first, limiting what reaches stages 3-4. The `_DANGEROUS_SCHEME_RE` provides a final catch for scheme-based attacks.

**Cross-unit verification:** review.py scorecard documents CH-3 relay role. The complete trace spans: retry (TB-5: parse) → review (relay: transport) → github-review (TB-6: sanitize + post).

github-review does **not** participate in:
- CH-1 (Prompt Injection) — no prompt construction
- CH-2 (Path Traversal) — no filesystem access
- CH-4 (Rule Bypass) — no rule execution
- CH-5 (History Poisoning) — no session management

---

## Dimension Details

### 1. Contract Fidelity

**Score:** 8/10
**Evidence:**
- mypy strict passes with zero issues (Tier A).
- `ThreadRef(NamedTuple)` with typed fields `node_id: str`, `body: str` (Tier A).
- `parse_diff_lines(str) -> dict[str, set[int]]` — clear contract (Tier A).
- `classify_findings(list[Finding], dict[str, set[int]]) -> tuple[list[Finding], list[Finding]]` — typed tuple return (Tier A).
- `_sanitize_comment_text(str) -> str` — pure function contract (Tier A).
- `_sanitize_path(str) -> str` — pure function contract (Tier A).
- `build_review_comment(Finding) -> dict[str, str | int]` — typed dict return (Tier A).
- `post_review()` — 9 keyword-only parameters, all typed (Tier A).
- `fetch_grippy_comments() -> dict[tuple[str, str, int], ThreadRef]` — complex but precise return type (Tier A).
- `resolve_threads() -> int` — simple return contract (Tier A).
- Not 9: `post_review()` internal flow uses `Any` for PyGithub objects (`pr: Any` in internal code). `build_review_comment()` returns `dict[str, str | int]` rather than a typed dataclass. `_dismiss_prior_verdicts(pr: Any, ...)` uses `Any` for PyGithub.
- Calibration: matches agent (8) and codebase (8). Both have typed throughout with `Any` for framework interop.

---

### 2. Robustness

**Score:** 8/10
**Evidence:**
- **422 fallback:** `post_review()` at `github_review.py:575-582`: inline comment 422 (line not addressable) falls back to off-diff summary — findings preserved, never dropped (Tier A: `TestPostReview422Fallback`).
- **Non-fatal thread resolution:** Lines 586-592: thread resolution wrapped in `try/except`, failure produces `::warning::` but review posting continues (Tier A: `TestResolveThreads`).
- **Non-fatal verdict posting:** Lines 613-615: verdict review failure produces `::warning::` but summary posting continues (Tier A: `TestVerdictReview`).
- **Subprocess timeouts:** 30-second timeout on all `gh api graphql` calls: `fetch_grippy_comments` (line 294), `fetch_thread_states` (line 688), `resolve_threads` (line 752) (Tier B: code trace).
- **Paginated fetching:** `fetch_grippy_comments` uses cursor pagination with 20-page safety limit (line 272) — prevents unbounded API calls (Tier B).
- **Summary upsert:** Lines 642-649: edit existing summary if marker found, create new otherwise. Prevents duplicate summaries (Tier A: `TestFormatSummary`).
- **Post-first verdict ordering:** Line 596 comment: "Post new verdict FIRST, then dismiss old ones." `_dismiss_prior_verdicts` runs after `pr.create_review()` succeeds. Prevents window where no verdict exists (Tier B: `TestPostReviewVerdictLifecycle`).
- Not 9: `subprocess.run()` with `check=False` — error handling via return code, but stderr parsing is basic (`print(f"::warning::...")`). No retry on transient GraphQL failures. `GithubException` catch at line 580 re-raises for non-422 codes — correct but could be more granular (e.g., 403 for fork PRs handled at a higher level).
- Calibration: matches codebase (8) and review (8). Strong graceful degradation across all external API interactions.

---

### 3. Security Posture

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 9/10
**Evidence:**
- **5-stage sanitization pipeline (TB-6 anchor, RP-02):** `_sanitize_comment_text()` at `github_review.py:145-163`. Each stage documented in CH-3 section above. Tested by `TestCommentSanitization` and `TestOutputSanitizationGaps` in hostile env (Tier A: 8+ tests covering HTML scripts, javascript: URLs, data: URLs, vbscript: URLs, tracking pixels, phishing links, bidi in paths, percent-encoded schemes).
- **Path sanitization:** `_sanitize_path()` at `github_review.py:179-182`: `navi_sanitize.clean(path, escaper=navi_sanitize.path_escaper)` + allowlist regex `[a-zA-Z0-9_./ -]`. Used in `_finding_marker()` and `build_review_comment()` (Tier A: `test_off_diff_file_path_sanitized`, `test_finding_file_newlines_stripped`).
- **GraphQL injection defense:** `resolve_threads()` at `github_review.py:737-748`: uses `$id{i}` GraphQL variable declarations, not string interpolation. Thread IDs passed as `-f id{i}={tid}` arguments to `gh api graphql`. Same pattern in `fetch_grippy_comments()` and `fetch_thread_states()` (Tier B: code trace of all 3 GraphQL callers).
- **Marker-based dedup:** `_finding_marker()` uses sanitized path — attacker cannot craft a marker to shadow/suppress another finding's marker (Tier B: `_sanitize_path()` runs before marker construction).
- **Independent defense layers:** navi_sanitize (Unicode), nh3 (HTML), regex (markdown), regex (URI) — four independent libraries/mechanisms (Tier B).
- Not 10: Stages 3-4 use regex for markdown parsing — deeply nested or malformed markdown could theoretically bypass. No content-security-policy-style declaration of what output should look like (defense is removal-based, not allowlist-based). `nh3` trusts upstream for HTML parsing correctness. `_DANGEROUS_SCHEME_RE` covers 3 schemes — other schemes (e.g., `blob:`) not explicitly blocked (low risk: GitHub renders markdown, not executes it).
- Calibration: matches local-diff (9). Strongest sanitization pipeline in the project — more stages and more independent than agent's 4-layer prompt pipeline. The 5-stage pipeline is defense-in-depth with independent mechanisms at each stage.

---

### 4. Adversarial Resilience

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 8/10
**Evidence:**
- **Hostile environment tests (github-review-relevant):** 8 tests in `TestOutputSanitizationGaps`:
  - `test_html_script_stripped` — `<script>` tag removal (Tier A)
  - `test_javascript_url_stripped` — `javascript:` scheme blocked (Tier A)
  - `test_data_url_stripped` — `data:` scheme blocked (Tier A)
  - `test_vbscript_url_stripped` — `vbscript:` scheme blocked (Tier A)
  - `test_markdown_image_tracker_stripped` — tracking pixel removal (Tier A)
  - `test_markdown_link_tracker_stripped` — phishing link removal (Tier A)
  - `test_off_diff_file_path_sanitized` — bidi chars in paths stripped (Tier A)
  - `test_percent_encoded_javascript_decoded` — URL-encoding bypass caught (Tier A)
- **Dedicated sanitization tests:** `TestCommentSanitization` in `test_grippy_github_review.py` — covers `_sanitize_comment_text()` and `build_review_comment()` sanitization flow (Tier A).
- **Schema validation attacks:** `test_finding_file_newlines_stripped` and `test_finding_file_backticks_stripped` in hostile env — verifies path sanitization in summary output (Tier A).
- **GraphQL variable binding:** All 3 GraphQL callers use parameterized variables, not string interpolation (Tier B: code trace).
- Not 9: No property-based testing on `_sanitize_comment_text()` with arbitrary Unicode/markdown input. No adversarial test for deeply nested markdown constructs (e.g., `[text](javascript:[text](javascript:...)`). No adversarial test for GraphQL-specific injection (though variable binding prevents it). Adversarial tests focus on individual sanitization stages — no combined multi-stage bypass test.
- Calibration: matches codebase (8, 12 direct adversarial tests). Above agent (7, wider but more indirect attack surface). The 5-stage pipeline with 8 hostile env tests is strong focused defense at the final output boundary.

---

### 5. Auditability & Traceability

**Score:** 7/10
**Evidence:**
- **Well-separated functions:** Unlike review.py's monolithic `main()`, github_review has 12 focused functions. Each is independently testable and traceable (Tier B).
- **Marker-based thread tracking:** `_finding_marker()` creates `<!-- grippy:{file}:{category}:{line} -->` markers that enable forensic reconstruction of which findings were posted and when (Tier B).
- **`::warning::` annotations:** Subprocess failures, thread resolution failures, verdict posting failures all produce `::warning::` with context (Tier B: code trace of 7 warning sites).
- **Step logging in `post_review()`:** `print(f"  Resolved {actual_resolved}/{len(thread_ids)} threads")` and `print(f"  Dismissed {dismissed} prior verdict(s)")` (Tier C).
- **Verdict body markers:** `<!-- grippy-verdict {sha} -->` and `<!-- grippy-meta {...} -->` enable machine-readable extraction of prior review state (Tier A: `TestVerdictMarkers`).
- Not 8: No structured logging (`print()` throughout). No correlation ID linking posting to the originating review. Subprocess command construction is inline — not logged before execution. GraphQL query strings are inline constants — readable but not externally documented.
- Calibration: above codebase (6, no tool-call logging) and review (6, monolithic main). Matches local-diff (7, structured command logging). github_review's function separation and marker system provide better traceability than review.py.

---

### 6. Test Quality

**Score:** 9/10
**Evidence:**
- **Test count:** 87 tests across 17 test classes, 1894 LOC = 2.46:1 test-to-source ratio.
- **Test class breakdown (17 classes):**
  - TestParseDiffLines (6): simple addition, context lines, multi-file, empty, metadata skip, hunk boundaries
  - TestClassifyFindings (4): inline, off-diff, mixed, empty
  - TestBuildReviewComment (4): structure, sanitization, emoji mapping, marker format
  - TestFormatSummary (6): full, delta, off-diff, truncation warning, marker, empty
  - TestFetchGrippyComments (5): success, pagination, subprocess failure, empty, no marker
  - TestPostReview (8): full lifecycle, new-only, all-existing skip, fork fallback, batching, dedup
  - TestVerdictReview (4): PASS/APPROVE, FAIL/REQUEST_CHANGES, non-fatal failure, body format
  - TestFetchThreadStates (4): success, empty input, subprocess failure, malformed response
  - TestResolveThreads (4): success, empty input, subprocess failure, partial success
  - TestParseDiffLinesEdgeCases (6): binary files, renames, no-newline marker, empty hunks, mode changes
  - TestPostReview422Fallback (3): single batch, multi-batch, all batches fail
  - TestResolveThreadsBatchSafety (3): variable binding, alias format, large batch
  - TestCommentSanitization (5): text sanitization, path sanitization, combined, edge cases, empty
  - TestVerdictMarkers (3): format, parse, malformed
  - TestDismissPriorVerdicts (5): same SHA skip, different SHA dismiss, workflow_dispatch force, exclude ID, no verdicts
  - TestPostReviewVerdictLifecycle (4): post-first ordering, dismiss after post, fork no verdict, partial failure
  - TestFetchThreadStatesFix (3): node ID mapping, missing nodes, batch boundary
- **Fixture categories:** Positive (20), negative (15), error handling (18), edge cases (14), adversarial (8 hostile env + 5 sanitization), integration (7). Strong across all categories.
- **RP-07 sub-behaviors tested separately:** `TestPostReview` covers same-run dedup; `TestResolveThreads` + `TestFetchThreadStates` cover repeated-run resolution; `TestResolveThreadsBatchSafety` covers injection safety in resolution.
- Not 10: No property-based testing. No mutation testing. No load testing for large PR scenarios (1000+ findings, 100+ threads). `TestParseDiffLines` covers standard cases but not adversarially crafted diffs designed to confuse line mapping.
- Calibration: matches codebase (9, 101 tests). Highest test density for pipeline units. Above agent (7, 41 tests) and review (8, 78 tests). The RP-07 sub-behavior separation and 17 focused test classes demonstrate mature test architecture.

---

### 7. Convention Adherence

**Score:** 9/10
**Evidence:**
- SPDX header on source and test file (Tier A: `github_review.py:1`, `test_grippy_github_review.py:1`).
- ruff check passes with zero issues (Tier A).
- mypy strict passes with zero issues (Tier A).
- Test file follows mirror structure: `src/grippy/github_review.py` -> `tests/test_grippy_github_review.py` (Tier A).
- Test file exceeds 50 LOC minimum (1894 LOC) (Tier A).
- `nosec B105` annotation on `"PASS"` string (security keyword false positive) with Bandit convention (Tier A).
- Calibration: matches agent (9), codebase (9), review (9).

---

### 8. Documentation Accuracy

**Score:** 7/10
**Evidence:**
- Module-level docstring: "GitHub PR Review API integration — inline comments, resolution, summaries" — accurate, includes finding lifecycle note (Tier C).
- `parse_diff_lines()` docstring: accurately describes RIGHT-side line extraction and GitHub API constraint (Tier C).
- `classify_findings()` docstring: accurately describes inline vs off-diff classification (Tier C).
- `_sanitize_comment_text()` docstring: accurately describes 3 of 5 stages (navi-sanitize, nh3, URL scheme). Missing: markdown image removal and link rewriting not documented in docstring (Tier C).
- `post_review()` docstring: accurately describes 5-step lifecycle with numbered steps matching code (Tier C).
- `fetch_grippy_comments()` docstring: accurately describes GraphQL pagination and limits (Tier C).
- `resolve_threads()` docstring: accurately describes batched mutation approach (Tier C).
- `build_verdict_body()` docstring: accurately describes marker format (Tier C).
- Inline comments: marker format `<!-- grippy:file:category:line -->` documented, `_REVIEW_BATCH_SIZE` documented, post-first verdict ordering rationale documented (Tier C).
- Not 8: `_sanitize_comment_text()` docstring omits stages 3-4 (markdown image/link). No formal API docs. No architectural comment explaining why 5 stages are needed or what each defends against (code is clear but rationale is implicit). The conservative thread resolution design (requires both absent + outdated) is not documented with a rationale comment.
- Calibration: matches codebase (7) and review (7). Below agent (8, which has explicit security rationale comments).

---

### 9. Performance

**Score:** 7/10
**Evidence:**
- **Batched inline comments:** `_REVIEW_BATCH_SIZE = 25` at `github_review.py:421`. Comments posted in batches via `pr.create_review()` — reduces API calls (Tier B).
- **Batched thread resolution:** `resolve_threads()` uses a single GraphQL mutation with aliased operations (`t0`, `t1`, ...) — one API call for all threads (Tier B: code trace `github_review.py:737-744`).
- **Paginated fetching:** `fetch_grippy_comments()` fetches 100 threads per page, max 20 pages (Tier B).
- **Subprocess timeouts:** 30 seconds on all `gh api graphql` calls (Tier B).
- **Summary upsert:** Single iteration of issue comments to find existing summary (Tier B).
- Not 8: `re.sub()` patterns in `_sanitize_comment_text()` are not pre-compiled (inline patterns). Called once per finding field (not hot path) but compiled regex would be marginal improvement. `unquote()` called on every text field. `parse_diff_lines()` is `O(lines)` on the diff — correct algorithm. `classify_findings()` is `O(findings × 1)` using set lookup — efficient.
- Calibration: below codebase (8, monotonic clock timeouts) and local-diff (8). Matches review (7). No hot paths, efficient batching, but no monotonic clock usage.

---

### 10. Dead Code / Debt

**Score:** 9/10
**Evidence:**
- `ThreadRef` NamedTuple used in `fetch_grippy_comments()`, `post_review()`, and `resolve_threads()` (Tier A).
- `_SEVERITY_EMOJI` dict used in `build_review_comment()` and `format_summary_comment()` (Tier A).
- `_GRIPPY_MARKER_RE` used in `_parse_marker()`, called by `fetch_grippy_comments()` (Tier A).
- `GRIPPY_VERDICT_MARKER` used in `_dismiss_prior_verdicts()` and exported to review.py (Tier A).
- `_GRIPPY_META_RE` used in `parse_grippy_meta()` (Tier A).
- `_DANGEROUS_SCHEME_RE` used in `_sanitize_comment_text()` (Tier A).
- `_REVIEW_BATCH_SIZE` used in `post_review()` batching loop (Tier A).
- All functions called — verified by test coverage and caller traces (Tier A).
- Zero `TODO` or `FIXME` comments (Tier A).
- ruff detects no unused imports (Tier A).
- Not 10: `json` imported twice (top-level at line 10, re-imported at line 255 inside `fetch_grippy_comments` and line 735 inside `resolve_threads`). The re-imports are redundant — the top-level import suffices. Cosmetic only, no functional impact.
- Calibration: matches agent (9) and codebase (9). Very clean — no debt, no orphans.

---

### 11. Dependency Hygiene

**Score:** 9/10
**Evidence:**
- **Internal deps:** Only `grippy.schema.Finding` imported (line 21). Most isolated unit in the project for internal dependencies (Tier A).
- **External deps:**
  - `navi_sanitize` — security-critical, used in `_sanitize_comment_text()` and `_sanitize_path()` (Tier A)
  - `nh3` — Rust-based HTML sanitizer, used in `_sanitize_comment_text()` stage 2 (Tier A)
  - `github` (PyGithub) — GitHub API library, used for PR operations (Tier A)
  - `subprocess` — stdlib, used for `gh api graphql` calls (Tier A)
  - `re`, `json`, `os` — stdlib (Tier A)
  - `urllib.parse.unquote` — stdlib, URL decoding in sanitization (Tier A)
- **No circular imports** (Tier A: ruff check).
- Not 10: `nh3` is an additional external security dependency beyond `navi_sanitize`. Both are trusted but add two external security contracts. `github` (PyGithub) is a large dependency used for PR API access. These are all justified by the unit's role at the GitHub posting boundary.
- Calibration: above codebase (7, depends on navi_sanitize + agno + lancedb). Above agent (7, navi_sanitize + agno + importlib). github_review's single internal import (`Finding`) is the cleanest dependency graph of any pipeline unit.

---

## Calibration Assessment

github-review scores **8.2/10** against calibration peers:
- **local-diff (8.4):** local-diff has simpler scope (3 functions, 1 boundary, stdlib only). github-review has more external deps (navi_sanitize, nh3, PyGithub) but the strongest sanitization pipeline in the project. The 0.2 gap reflects the external dependency cost. github-review compensates with higher test density (87 vs 30 tests) and stronger adversarial coverage.
- **graph-store (8.0):** graph-store has SQLite state management complexity but no external-facing attack surface. github-review faces attacker-controlled LLM output at TB-6 — a higher-risk boundary. github-review's 8.2 vs graph-store's 8.0 reflects the stronger security investment required (and delivered) for the output boundary.
- **codebase (7.9):** Both are trust-boundary units with adversarial exposure. github-review has fewer internal deps (1 vs 0), higher test density (2.46:1 vs 1.62:1), and a more focused security pipeline (5-stage vs 3-layer). The 0.3 gap reflects github-review's architectural cleanliness and isolation.
- **review (7.2):** These two units are tightly coupled via CH-3. review.py delegates all posting sanitization to github-review. The 1.0 gap between them reflects the difference between "orchestrates everything" (review, wide scope, heavy deps) and "owns one boundary excellently" (github-review, narrow scope, deep defense). This is the expected pattern for orchestrator vs. boundary unit.

github-review achieves **Healthy** status — the first pipeline unit to do so. The 5-stage `_sanitize_comment_text()` pipeline, combined with the highest test density in the project for pipeline units (87 tests, 17 classes), places this unit among the project's strongest. The single internal import and architectural isolation make it easy to audit and maintain.

---

## Findings

No findings generated. All 3 scoped RP checklist items PASS with Tier A evidence. No CRITICAL, HIGH, or MEDIUM gaps identified during audit.

**Key observations (not findings):**
- The redundant `json` re-imports at lines 255 and 735 are cosmetic — no functional impact.
- `_sanitize_comment_text()` docstring omits stages 3-4. Accurate but incomplete documentation.
- The conservative thread resolution design (requires absent + outdated) is well-engineered but the rationale is not documented inline.

### Hypotheses

None.
