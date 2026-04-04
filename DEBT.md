# Technical Debt

Tracked issues that need resolution but are not blocking current work.

## Open

### DEBT-001: GitHub diff API 406 on large PRs breaks Grippy self-review

**Filed:** 2026-03-31
**Module:** `review.py` — `fetch_pr_diff()`
**Severity:** Medium

GitHub's REST API returns `406 Not Acceptable` when a PR diff exceeds their size limit (~24K lines). Grippy's `fetch_pr_diff()` does not handle this gracefully — it crashes with an unhandled HTTP error, failing the CI workflow.

**Impact:** Grippy cannot self-review PRs that include large fixture files or generated content. Discovered on PR #83 when ~24K lines of golden message fixtures triggered the 406.

**Fix:** Handle 406 in `fetch_pr_diff()` by falling back to per-file diffs via `GET /repos/{owner}/{repo}/pulls/{pr}/files` and fetching individual file patches, or truncating gracefully with a warning.

**Workaround:** Split large fixture additions into separate PRs.

### DEBT-002: No migration path for serialized Finding objects missing `finding_type`

**Filed:** 2026-04-04
**Module:** `schema.py` — `Finding`, `FindingType`
**Severity:** Low

The `finding_type` field was added to `Finding` as required (no default) to avoid OpenAI structured output `$ref` + `default` keyword conflicts. Historical serialized `Finding` records (if any exist in databases or artifacts) will fail Pydantic validation on deserialization because they lack this field.

**Impact:** Low — no known production consumers persist `Finding` objects long-term. CI reviews are ephemeral.

**Fix:** If persistent Finding storage is added, include a migration to inject `finding_type: "issue"` into legacy records.

### DEBT-003: Cached LLM agents may not emit `finding_type` field

**Filed:** 2026-04-04
**Module:** `prompts_data/output-schema.md` — `finding_type` field
**Severity:** Low

Older orchestrators or LLM agents running on cached prompts without the `finding_type` field will produce `Finding` objects that fail Pydantic validation. The field is required, so missing it causes a parse error.

**Impact:** Low — grippy CI always runs from the current commit's prompts. Only affects external consumers using stale schema docs.

**Fix:** No action needed unless grippy is deployed as a service with cached prompt versions.
