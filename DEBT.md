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
