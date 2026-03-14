<!-- SPDX-License-Identifier: MIT -->

# Audit Scorecard: codebase

**Audit date:** 2026-03-14
**Commit:** aba44c3
**Auditor:** Claude Opus 4.6 (AI draft) / Nelson Spence (human reviewer)
**Unit type:** llm-facing-tool (primary)
**Subprofile:** N/A
**Methodology version:** 1.3

---

## Checklist: LT-01 through LT-08

| ID | Invariant | Status | Evidence |
|----|-----------|--------|----------|
| LT-01 | File read paths bounded to repo root | PASS | `Path.resolve()` + `is_relative_to(repo_root.resolve())` in `_make_read_file()` (line 739-741) and `_make_list_files()` (line 792-794). Tested: `../etc/passwd` blocked (Tier A: `test_path_traversal_blocked`), prefix collision `../repo-evil/secrets.py` blocked (Tier A: `test_read_file_rejects_prefix_bypass`), glob entries filtered against resolved root (Tier A: `test_path_traversal_blocked` in list_files). |
| LT-02 | No symlink following outside repo | PASS | grep uses `-rn` flag (not `-R`) on GNU grep. Comment documents BSD difference: `codebase.py:693-696` (Tier B: code trace + inline comment). Symlink escape test: `test_symlink_escape_blocked` in `test_hostile_environment.py` (Tier A). `read_file` resolves path via `Path.resolve()` which follows symlinks but then checks `is_relative_to()` — resolved target must be inside repo root (Tier B: trace of `codebase.py:739-741`). |
| LT-03 | All tool outputs sanitized before LLM | PASS | `sanitize_tool_hook()` middleware: `_sanitize_tool_output()` applies `navi_sanitize.clean()` (invisible chars, bidi, homoglyphs) + XML entity escape (`&amp;` `&lt;` `&gt;`), then `_limit_result()` truncates to 12K chars (Tier A: `test_sanitize_cleans_output`, `test_hook_sanitizes_and_limits` in test_grippy_codebase.py). Hostile env tests: `test_grep_results_injection_payload` verifies XML breakout neutralized, `test_off_diff_file_path_sanitized` verifies prompt context injection stripped (Tier A). All four tool functions return `str`, and `sanitize_tool_hook` catches all `str` returns (Tier B: code trace). |
| LT-04 | Result counts bounded | PASS | `_MAX_GLOB_RESULTS = 500` with lazy collection + truncation notice (Tier A: `test_truncation_message`). `grep --max-count=50` (Tier A: `test_max_matches`). `_MAX_INDEX_FILES = 5_000` (Tier B: code trace `codebase.py:57`). `_MAX_RESULT_CHARS = 12_000` (Tier A: `test_over_limit_truncated_with_message`). |
| LT-05 | Timeouts in operation loops | PASS | `list_files` glob: 5-second `time.monotonic()` deadline checked inside the `target.glob()` iteration loop (Tier A: `test_glob_has_timeout_protection` in hostile env). `grep_code`: 10-second `subprocess.timeout` (Tier A: `test_timeout_returns_message`). |
| LT-06 | Error messages don't reveal internal state | PARTIAL | See finding F-CB-001. Error messages include user-supplied relative paths (acceptable: LLM already knows what it asked for). `f"Error reading file: {e}"` (`codebase.py:752,759`) could expose absolute paths via OSError. `f"Search failed: {result.stderr.strip()}"` (`codebase.py:716`) could expose repo root via grep stderr. `f"Error listing files: {e}"` (`codebase.py:818`) could expose paths via OSError. Additionally, `grep_code` normal output (`result.stdout`) includes absolute repo root in match paths. |
| LT-07 | Regex validated before execution | PASS | `re.compile(pattern)` called before subprocess, invalid regex returns `f"Invalid regex: {e}"` (Tier A: `test_invalid_regex`). |
| LT-08 | Graceful degradation without optional infra | PASS | `CodebaseIndex.search()` returns empty list when `_vector_db.exists()` is False (Tier A: `test_search_empty_when_not_indexed`). `_hybrid_search` failure falls back to `_vector_search`, which falls back to empty list (Tier B: code trace `codebase.py:600-610`). Tool functions work without index (Tier A: multiple tests use repo root without index). |

---

## Gate Rules

### Override Gates (force a specific status)

| Override Gate | Condition | Fired? |
|---|---|---|
| Critical finding | Any unresolved CRITICAL finding | No |
| Multi-HIGH block | 2+ unresolved HIGH findings (including provisional) | No (0 HIGH findings) |
| Security collapse | Security Posture < 2 | No (score: 8) |
| Adversarial collapse | Adversarial Resilience < 2 | No (score: 8) |

### Ceiling Gates (cap the best allowed status)

| Ceiling Gate | Condition | Fired? |
|---|---|---|
| Severity cap | Any unresolved HIGH finding | No |
| Security hard floor | Security Posture < 4 | No (score: 8) |
| Adversarial hard floor | Adversarial Resilience < 4 | No (score: 8) |
| Security soft floor | Security Posture < 6 | No (score: 8) |
| Adversarial soft floor | Adversarial Resilience < 6 | No (score: 8) |
| Accepted critical risk | Any ACCEPTED_RISK at CRITICAL | No |
| Accepted high risk | Any ACCEPTED_RISK at HIGH | No |

---

## Summary

| Dimension | Score | Evidence Tier | Notes |
|-----------|------:|:---:|-------|
| 1. Contract Fidelity | 8/10 | A | Protocols for Embedder/BatchEmbedder. CodebaseToolkit Agno adapter. Typed throughout. mypy strict clean. |
| 2. Robustness | 8/10 | A | Timeouts (monotonic + subprocess), caps, graceful fallback (hybrid -> vector -> empty), cache invalidation, size limits. |
| 3. Security Posture | 8/10 | A | `is_relative_to()` traversal defense, `sanitize_tool_hook()` 3-layer pipeline, result caps, timeouts, subprocess timeout. F-CB-001 (LT-06 partial) is LOW. |
| 4. Adversarial Resilience | 8/10 | A | 7 adversarial tests in main suite + 5 in hostile env. Path traversal, prefix bypass, XML injection, symlink escape, null bytes, ReDoS timeout all tested. |
| 5. Auditability & Traceability | 6/10 | B | Cache manifest with repo SHA + config fingerprint. Structured logging (logger defined, used in build/cache). No tool-call-level logging. |
| 6. Test Quality | 9/10 | A | 101 tests, 23 classes, 4 categories. 1.61:1 test:source ratio. Strongest adversarial fixture coverage in the project. |
| 7. Convention Adherence | 9/10 | A | ruff, mypy strict, SPDX, naming, test mirror all clean. |
| 8. Documentation Accuracy | 7/10 | C | Security comments inline (symlink caveat, nosec annotation). BSD grep documented. Module docstring accurate. No formal API docs. |
| 9. Performance | 8/10 | A | Monotonic clock timeouts, subprocess timeouts, chunked processing, bounded results, cache-based rebuild avoidance. |
| 10. Dead Code / Debt | 9/10 | A | BatchEmbedder Protocol used in type union + isinstance check + tests. All functions called. Zero TODOs. |
| 11. Dependency Hygiene | 7/10 | A | navi_sanitize (external), lancedb (external, optional), agno (framework), subprocess. Most deps of any unit. |
| **Overall** | **7.9/10** | | **Average of 11 dimensions** |

**Health status:** Adequate

**Determination:**
1. Average-based status: 7.9/10 falls in 6.0-7.9 range = **Adequate**
2. Override gates: None fired.
3. Ceiling gates: None fired. All gate dimensions >= 6.
4. Suffixes: No `(provisional)` — Dim 3 (8/10) supported by Tier A (path traversal tests, sanitization tests, cap tests). Dim 4 (8/10) supported by Tier A (adversarial test suite).

**Override gates fired:** None
**Ceiling gates fired:** None

---

## Findings

### F-CB-001: grep output and error messages expose absolute repo root path (LOW)

**Severity:** LOW
**Status:** OPEN
**Evidence tier:** B (code trace + behavioral trace)

**Location:** `codebase.py:697-717` (grep_code), `codebase.py:752,759` (read_file errors), `codebase.py:818` (list_files errors)

**Description:** The `grep_code` tool passes `str(repo_root)` as the search directory to `subprocess.run(["grep", ...])`. Grep's stdout includes absolute paths on every match line:

```
/home/user/repo/src/file.py:10:matched content
```

This exposes the absolute repo root to the LLM on every successful grep call. Additionally, error messages in three locations could expose absolute paths:
- `f"Error reading file: {e}"` — Python's OSError includes the resolved absolute path
- `f"Search failed: {result.stderr.strip()}"` — grep stderr includes the search directory
- `f"Error listing files: {e}"` — OSError includes absolute path

**Impact:** The LLM learns the server's filesystem structure (username, path hierarchy). In isolation this is low risk — the LLM is already bounded by `is_relative_to()` and can't escape the repo root. The absolute path cannot be directly exploited through tool calls. However:
1. Prompt injection could reference the absolute path to craft more convincing social engineering in review comments
2. The information leaks through to GitHub comments if output sanitization (`github_review.py`) doesn't strip filesystem paths

**Mitigating factors:**
- `sanitize_tool_hook()` handles Unicode evasion and XML injection (structural defense)
- `is_relative_to()` prevents path traversal regardless of what the LLM knows
- GitHub posting sanitization (`_sanitize_comment_text()`) provides a second defense layer

**Suggested improvement:** Strip the repo root prefix from grep stdout before returning:
```python
output = result.stdout.replace(str(repo_root) + os.sep, "")
```
And wrap OSError messages to use relative paths:
```python
return f"Error reading file: permission denied or I/O error"
```

### F-CB-002: KRC-01 instance — no property-based testing for path traversal (LOW)

**Severity:** LOW (known recurring class — see METHODOLOGY.md Section E.1)
**Status:** OPEN
**Evidence tier:** C

**Description:** Path traversal defense is tested with 4 specific patterns (relative `../`, absolute, prefix bypass, null bytes) plus symlink escape. These are the standard attack vectors. No property-based testing (e.g., hypothesis-generated path strings) validates that `is_relative_to()` holds for arbitrary inputs. Given that `Path.is_relative_to()` is a stdlib method with well-defined semantics, the fixed test vectors are sufficient for practical security. Property-based testing would be defense-in-depth for the test suite itself.

**Rationale for LOW:** The existing adversarial tests cover all known attack patterns. `is_relative_to()` is a stdlib method, not custom logic. The gap is in test methodology (property-based vs fixture-based), not in coverage of real attack vectors.

### Compound Chain Exposure

codebase participates in **CH-2 (Path Traversal -> Data Exfiltration -> Prompt Leakage)** as the **origin**.

**Data flow:**
```
LLM tool call → _make_read_file() / _make_grep_code() / _make_list_files()
  → filesystem access bounded by is_relative_to()
  → raw result → sanitize_tool_hook() → navi_sanitize + XML escape + 12K truncation
  → sanitized result → LLM context
```

**Circuit breakers:**
1. **LT-01 (path traversal):** `is_relative_to(repo_root.resolve())` on resolved paths. Covers `../`, absolute, prefix bypass.
2. **LT-02 (symlink):** `resolve()` follows symlinks, then `is_relative_to()` checks resolved target.
3. **LT-03 (output sanitization):** `sanitize_tool_hook()` strips invisible chars, XML-escapes output, truncates to 12K.
4. **LT-04 (result caps):** 500 glob, 50 grep, 12K chars prevent context flooding.
5. **LT-05 (timeouts):** 5s glob, 10s grep prevent denial of service.

**Residual risk:** F-CB-001 (absolute path exposure in grep output) is a low-severity information leak. It doesn't enable path traversal but provides the LLM with filesystem structure information.

codebase also participates in **CH-3 (Output Injection -> GitHub Comment XSS/Phishing)** as a **relay**.

**Data flow:**
```
Attacker-crafted file content → grep_code/read_file tool output
  → sanitize_tool_hook() (XML escape, 12K truncation)
  → LLM context → LLM may quote file content in findings
  → run_review() → github_review.py sanitization → GitHub API
```

**Circuit breaker:** LT-03 (sanitize_tool_hook) neutralizes XML breakout and invisible chars at the tool output boundary. The downstream `github_review.py` sanitization provides a second independent layer.

codebase does **not** participate in CH-1 (Prompt Injection), CH-4 (Rule Bypass), or CH-5 (History Poisoning).

### Hypotheses

None.

---

## Dimension Details

### 1. Contract Fidelity

**Score:** 8/10
**Evidence:**
- mypy strict passes with zero issues (Tier A).
- `Embedder` and `BatchEmbedder` Protocol classes with `@runtime_checkable` (Tier A: `codebase.py:64-76`). Used for isinstance dispatch in `build()` (Tier A).
- `CodebaseIndex` class with typed `__init__` parameters: `repo_root: Path`, `vector_db: Any`, `embedder: Embedder | BatchEmbedder`, `data_dir: Path`, typed frozensets and optional list (Tier A).
- `CodebaseToolkit(Toolkit)` — proper Agno adapter with `Function.from_callable` registration (Tier A).
- Tool functions have typed inner closures with docstrings that serve as LLM-facing tool descriptions (Tier B).
- `_config_fingerprint()`, `_write_manifest()`, `_read_manifest()` — typed cache infrastructure (Tier A).
- Not 9: `vector_db: Any` in CodebaseIndex constructor (Agno's LanceDb type is complex). `_parse_results_static` uses `list[dict[str, Any]]` rather than typed result models. Some internal functions lack return type annotations where inferrable.
- Calibration: above graph-context (7) and local-diff (8). Protocol classes and typed cache infrastructure elevate this.

---

### 2. Robustness

**Score:** 8/10
**Evidence:**
- **Timeouts:** 5-second monotonic clock in glob loop (`codebase.py:809`), 10-second subprocess timeout on grep (`codebase.py:712`). Both tested (Tier A).
- **Result caps:** `_MAX_GLOB_RESULTS = 500`, `grep --max-count=50`, `_MAX_RESULT_CHARS = 12_000`, `_MAX_INDEX_FILES = 5_000`. All enforced (Tier A tests for glob, grep, result truncation).
- **Search fallback chain:** `search()` → `_hybrid_search()` → exception → `_vector_search()` → exception → empty list (Tier B: code trace `codebase.py:600-610`). Never crashes the review.
- **Cache invalidation:** Manifest tracks `repo_sha`, `repo_dirty`, `config_fingerprint`, `schema_version`. Any mismatch triggers rebuild (Tier A: `test_index_cache_invalidation`).
- **Atomic manifest writes:** `_write_manifest()` uses `tmp_path.write_text()` + `tmp_path.replace(path)` — atomic on POSIX (Tier B: code trace `codebase.py:215-217`).
- **File size limit:** `read_file` rejects files over 1 MB before reading (Tier A: `test_large_file_size_limit` in hostile env).
- **Overlap clamping:** `chunk_file()` clamps overlap to prevent infinite loop when `overlap >= max_chunk_chars` (Tier A: `test_overlap_exceeds_chunk_size_no_infinite_loop`).
- Not 9: Non-git fallback in `_get_repo_state()` silently catches `CalledProcessError` — no logging of why git failed. `_ensure_fts_index()` catches bare `Exception` with logging but no retry.
- Calibration: matches local-diff (8). Both have subprocess timeouts and cap enforcement. Above graph-context (6, no internal error handling).

---

### 3. Security Posture

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 8/10
**Evidence:**
- **Path traversal defense (LT-01):** `Path.resolve()` + `is_relative_to(repo_root.resolve())` in both `_make_read_file()` and `_make_list_files()`. Tested with `../`, prefix collision, glob escape (Tier A: 4 tests).
- **Symlink defense (LT-02):** `resolve()` follows symlinks then checks `is_relative_to()`. grep uses `-r` not `-R` (no follow). BSD caveat documented (Tier A + B).
- **Output sanitization (LT-03):** `sanitize_tool_hook()` → `_sanitize_tool_output()` → `navi_sanitize.clean()` + XML entity escape → `_limit_result()` 12K truncation. Three independent layers (Tier A: tested with injection payloads).
- **Result caps (LT-04):** Multiple enforced bounds prevent context flooding (Tier A).
- **Timeouts (LT-05):** Monotonic clock + subprocess timeout (Tier A).
- **Regex validation (LT-07):** Pre-validated before subprocess (Tier A).
- **Defense in depth:** 5 independent defensive layers: input validation (is_relative_to), symlink resolution, output sanitization, result caps, timeouts.
- Not 9: F-CB-001 (absolute path exposure in grep stdout) is an information leak. No file integrity verification for indexed content. `nosec B324` annotation on SHA-1 chunk ID is appropriate but could be documented more explicitly.
- Calibration: below local-diff (9, which has stronger subprocess argument safety and no path leak). Above graph-context (7) and graph-store (8). Strongest defense-in-depth of any unit except local-diff.

---

### 4. Adversarial Resilience

**GATE DIMENSION: floors at 2 (collapse), 4 (hard), 6 (soft)**

**Score:** 8/10
**Evidence:**
- **Adversarial test count:** 7 in `test_grippy_codebase.py` + 5 in `test_hostile_environment.py` = 12 adversarial tests. Strongest adversarial coverage in the project.
- **Attack vectors tested:**
  - Path traversal `../` (Tier A: `test_path_traversal_blocked` in read + list)
  - Prefix bypass `../repo-evil/` (Tier A: `test_read_file_rejects_prefix_bypass`)
  - Symlink escape (Tier A: `test_symlink_escape_blocked`)
  - Null bytes in path (Tier A: `test_null_bytes_in_path_handled`)
  - XML breakout in tool output (Tier A: `test_grep_results_injection_payload`)
  - Prompt context injection via tool output (Tier A: `test_off_diff_file_path_sanitized`)
  - ReDoS regex timeout (Tier A: `test_redos_regex_times_out`)
  - Natural language injection neutralized (Tier A: `test_natural_language_injection_neutralized`)
  - System update injection neutralized (Tier A: `test_system_update_injection_neutralized`)
- **LLM-facing exposure:** All 4 tool functions accept LLM-generated parameters (paths, patterns, globs). Every parameter type has at least one adversarial test.
- Not 9: No property-based testing (KRC-01 / F-CB-002). Glob pattern injection (e.g., `**/../../../` via `glob_pattern` parameter in `list_files`) not explicitly tested — though `is_relative_to()` on resolved entries provides defense. No adversarial test for the cache manifest (attacker-crafted manifest JSON).
- Calibration: above local-diff (8, 10 dedicated tests but for subprocess injection, not tool-level). Highest in the project for LLM-facing adversarial coverage.

---

### 5. Auditability & Traceability

**Score:** 6/10
**Evidence:**
- **Logger defined and used:** `log = logging.getLogger(__name__)` with structured messages in `build()`, `_is_cache_valid()`, `_ensure_fts_index()` (Tier A: `codebase.py:28` + 12 log calls).
- **Cache manifest:** `codebase_index_manifest.json` records `schema_version`, `repo_sha`, `repo_dirty`, `config_fingerprint`, `built_at`. Enables forensic reconstruction of index state (Tier B: code trace).
- **Deterministic chunk IDs:** `_chunk_id()` produces SHA-1 from `file_path:start_line:end_line` (Tier B).
- Not 7: No tool-call-level logging. When the LLM calls `grep_code("secret_key")`, no log records the call, parameters, or result size. Tool call tracing requires Agno framework logging (external to this unit). Cache manifest logs existence/miss but not the specific queries.
- Calibration: above graph-context (5, no logger), imports (5, unused logger). Below local-diff (7, structured command logging). The gap between "logger exists and is used" (6) and "structured tool-call tracing" (7+) is the difference.

---

### 6. Test Quality

**Score:** 9/10
**Evidence:**
- **Test count:** 101 tests across 23 test classes + 5 additional in hostile env = 106 total.
- **Source:test ratio:** 864 LOC source / 1,397 LOC tests = 1.62:1 test-to-source ratio.
- **Test class breakdown (23 classes):**
  - TestLimitResult (4): short/exact/over/boundary truncation
  - TestSanitizeToolOutput (4): clean text, XML chars, navi_sanitize integration, combined
  - TestSanitizeToolHook (3): string sanitization, non-string passthrough, combined pipeline
  - TestWalkSourceFiles (5): default extensions, ignores, gitignore integration, fallback, empty repo
  - TestChunkFile (7): single chunk, multi-chunk, overlap, empty file, binary handling, relative paths, edge cases
  - TestCodebaseIndex (6): build, cache hit, cache invalidation, forced rebuild, empty repo, file cap
  - TestParseResults (5): normal, string payload, missing payload, malformed JSON, empty
  - TestHybridSearch (4): hybrid, vector fallback, both fail, FTS unavailable
  - TestSearchCode (4): results, empty, no index, formatting
  - TestGrepCode (7): match, no match, context, max matches, timeout, invalid regex, error handling
  - TestReadFile (5): content, line numbers, range, not found, traversal
  - TestListFiles (8): root, subdir, glob, traversal, truncation, empty, timeout, no files
  - TestCodebaseToolkit (4): registration, tool count, function types, hook integration
  - TestFakeBatchEmbedder (2): protocol compliance, batch embedding
  - TestIndexCacheInfra (6): manifest write/read, fingerprint, repo state, dirty detection, non-git
  - Plus 8 more specialized classes covering FTS, search integration, overlap edge cases
- **Fixture matrix:** Positive (32), negative (12), adversarial (12), edge case (15), integration (6), error handling (9). Four-category coverage — strongest in project.
- **Hostile environment suite:** 5 codebase-specific tests (symlink, ReDoS, null bytes, glob timeout, file size limit).
- Not 10: No property-based testing (F-CB-002). No benchmark/performance tests. Cache manifest corruption not tested. FTS index creation failure test relies on exception logging, not behavior verification.
- Calibration: above graph-store (9, 81 tests), local-diff (8, 30 tests). Strongest in the project by count and adversarial depth.

---

### 7. Convention Adherence

**Score:** 9/10
**Evidence:**
- SPDX header on source and test file (Tier A).
- ruff check passes with zero issues (Tier A).
- mypy strict passes with zero issues (Tier A).
- Test file follows mirror structure: `src/grippy/codebase.py` -> `tests/test_grippy_codebase.py` (Tier A).
- Test file exceeds 50 LOC minimum (1,397 LOC) (Tier A).
- `nosec B324` annotation on SHA-1 usage with `usedforsecurity=False` — follows bandit convention (Tier A).
- Calibration: matches graph-store (9), local-diff (9), prompts (9).

---

### 8. Documentation Accuracy

**Score:** 7/10
**Evidence:**
- File-level docstring: "Codebase indexing and search tools for Grippy reviews" — accurate (Tier C).
- `sanitize_tool_hook()` docstring: accurately describes middleware role and behavior (Tier C).
- `CodebaseIndex.build()` docstring: accurately describes cache logic and return values (Tier C).
- `_make_grep_code()` inner function: BSD grep caveat documented inline (`codebase.py:693-696`) — important security comment (Tier C).
- Tool function docstrings serve dual purpose: Python docstrings AND LLM-facing tool descriptions. Parameter descriptions use `:param:` format for Agno's tool extraction (Tier B).
- Not 8: No formal API documentation for `CodebaseIndex` (constructor parameters, search behavior). `_sanitize_tool_output()` doesn't document why XML escape is sufficient (no mention of the downstream `_escape_xml()` layer in agent.py). The relationship between `sanitize_tool_hook` (middleware) and `_sanitize_tool_output` (implementation) could be clearer.
- Calibration: matches graph-store (7), local-diff (8 would be too high). Above graph-context (6).

---

### 9. Performance

**Score:** 8/10
**Evidence:**
- **Monotonic clock timeouts:** `time.monotonic()` in glob loop (Tier A: tested). No wall-clock dependency.
- **Subprocess timeouts:** 10-second timeout on grep (Tier A: tested).
- **Bounded results:** 500 glob + 50 grep + 12K chars + 5K index files. All enforced at the point of collection (Tier A).
- **Cache-based rebuild avoidance:** Manifest check avoids re-embedding when repo state + config unchanged. Returns 0 chunks on cache hit (Tier A: tested).
- **Batch embedding:** `BatchEmbedder` Protocol enables batch embedding when available, falling back to per-chunk embedding (Tier B: code trace).
- **Chunked processing:** `chunk_file()` with overlapping windows — predictable memory per file (Tier B).
- **Lazy glob collection:** `target.glob()` iterator consumed lazily with early termination at cap (Tier B).
- Not 9: No profiling data. Chunk size (4000 chars) and overlap (200) are hardcoded. Index build does not parallelize file reading or embedding. Search does not cache results within a review session.
- Calibration: matches local-diff (8), graph-store (8). All have bounded operations and timeouts.

---

### 10. Dead Code / Debt

**Score:** 9/10
**Evidence:**
- Zero `TODO` or `FIXME` comments (Tier A: grep search).
- `BatchEmbedder` Protocol is used: type union in `CodebaseIndex.__init__` (`codebase.py:378`), isinstance dispatch in `build()` (`codebase.py:487`), `FakeBatchEmbedder` in 11 test locations (Tier A).
- `Embedder` Protocol is used in the same type union (Tier A).
- `_parse_results_static` and `_parse_results` both used — static for testability, instance for internal dispatch (Tier B).
- All tool factory functions (`_make_search_code`, `_make_grep_code`, `_make_read_file`, `_make_list_files`) registered in `CodebaseToolkit.__init__` (Tier A).
- ruff detects no unused imports (Tier A).
- Not 10: `_DATASET_ID = "grippy-codebase-v1"` is a constant passed to `insert(content_hash=...)`. It's used but the name `content_hash` is misleading — it's a dataset label, not a hash. Cosmetic only.

---

### 11. Dependency Hygiene

**Score:** 7/10
**Evidence:**
- **Internal deps:** None from grippy.* (Tier A: import check). Self-contained module.
- **External deps:**
  - `navi_sanitize` — security-critical external dependency. Output sanitization relies on it (Tier A).
  - `agno` — framework dependency. `Document`, `Function`, `Toolkit` classes. Required for integration (Tier A).
  - `lancedb` — optional, imported lazily in `_hybrid_search()` via `from lancedb.rerankers import RRFReranker` (Tier B).
  - `subprocess` — stdlib, used for git and grep operations (Tier A).
- **No circular imports** (Tier A: ruff check).
- Not 8: Most external deps of any unit (navi_sanitize, agno, lancedb). `navi_sanitize.clean()` contract is relied upon for security properties — changes to that library could silently weaken sanitization. `agno` framework dependency means codebase.py is tightly coupled to Agno's Toolkit/Function API.
- Calibration: below graph-context (8, fewer external deps), graph-store (8, SQLAlchemy only). Above embedder (6) which also has external model deps. Most deps reflect the unit's integration role at the tool-call boundary.

---

## Calibration Assessment

codebase scores **7.9/10** against calibration peers:
- **local-diff (8.4):** local-diff has stronger subprocess safety (explicit argument lists, no grep stdout path leak), simpler API (3 public functions vs 12+ in codebase). codebase has broader attack surface (4 LLM-facing tools vs 1 diff function) and more external deps. The 0.5 gap reflects the wider attack surface and F-CB-001 path leak. codebase's stronger adversarial test suite (12 vs 10) partially compensates but doesn't close the gap.
- **graph-store (8.0):** graph-store has SQLite state management complexity but no LLM-facing exposure. codebase has stronger adversarial coverage but more external deps and F-CB-001. The 0.1 gap is appropriate — both are strong units with different risk profiles.
- **graph-context (7.0):** codebase is significantly stronger across security posture (+1), adversarial resilience (+2), test quality (+2), robustness (+2). The 0.9 gap is the largest in Phase 2 and reflects genuine quality difference — codebase has defense-in-depth and comprehensive adversarial testing.

The framework discriminates between trust-boundary units (codebase at 7.9 with TB-4 exposure) and infrastructure units (graph-context at 7.0 with indirect exposure). The LT checklist added value: LT-06 revealed the grep path leak that a generic checklist would miss. The score range in Phase 2 (7.0-8.0) is consistent with Phase 1 (7.1-8.4).
