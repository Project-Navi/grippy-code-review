# Suppression

Grippy provides two layered suppression mechanisms for controlling what gets reviewed.

| Mechanism | Scope | Rules | LLM | Syntax |
|-----------|-------|-------|-----|--------|
| `.grippyignore` | File/path | Suppressed | Suppressed | gitignore semantics |
| `# nogrip` | Line | Suppressed | Still sees the line | Inline pragma |

---

## `.grippyignore` --- file-level suppression

Create a `.grippyignore` file in your repo root to exclude files from review. Uses standard gitignore syntax --- comments, negation, directory patterns, and globs all work.

```text
# Generated code
vendor/
*.generated.py

# Test fixtures with intentional anti-patterns
tests/test_rule_*.py

# But keep critical tests
!tests/test_critical.py
```

Excluded files are stripped from the diff **before** either the deterministic rule engine or the LLM sees them. They won't appear in findings, the review summary, or diff stats.

### How it works

1. Grippy discovers the repo root via `git rev-parse --show-toplevel`
2. Loads `.grippyignore` from the repo root (if it exists)
3. Each file in the diff is checked against the pathspec
4. Matching files are removed from the diff entirely
5. The remaining diff proceeds through the normal pipeline

If `.grippyignore` doesn't exist or can't be parsed, the feature degrades gracefully --- no files are excluded, no errors are raised.

---

## `# nogrip` --- line-level pragma

Suppress deterministic rule findings on specific lines by adding a `# nogrip` comment.

```python
password = os.environ["DB_PASS"]  # nogrip
conn = f"postgres://{user}:{password}@host/db"  # nogrip: hardcoded-credentials
h = hashlib.md5(data)  # nogrip: weak-crypto, hardcoded-credentials
```

### Syntax

| Form | Effect |
|------|--------|
| `# nogrip` | Suppress **all** rules on this line |
| `# nogrip: rule-id` | Suppress only the named rule |
| `# nogrip: id1, id2` | Suppress multiple specific rules |

### Rule IDs

Use the rule ID from the finding output. Current rule IDs:

`secrets`, `dangerous-sinks`, `workflow-permissions`, `path-traversal`, `llm-output-sinks`, `ci-script-risks`, `sql-injection`, `weak-crypto`, `hardcoded-credentials`, `insecure-deserialization`

### Important: rules only

`# nogrip` suppresses **deterministic rule findings only**. The LLM reviewer still sees the line with the pragma visible and may comment on it independently. To fully suppress a file from both engines, use `.grippyignore`.

### Safety: malformed pragmas are rejected

A bare colon with no rule ID (`# nogrip:`) is treated as **no pragma** --- it does not suppress anything. This prevents a typo from accidentally widening suppression scope.

---

## Precedence

Suppression layers are applied in order:

1. **`.grippyignore`** runs first --- matching files are removed from the diff entirely
2. **`# nogrip`** runs second --- matching lines in the remaining diff have their rule findings suppressed
3. **LLM review** runs last --- sees the filtered diff with `# nogrip` pragmas visible as context

---

## Examples

### Suppressing a known false positive

```python
# This is a hash for content addressing, not cryptographic use
chunk_id = hashlib.sha1(data).hexdigest()  # nogrip: weak-crypto
```

### Excluding generated files from review

```text
# .grippyignore
dist/
*.min.js
coverage/
```

### Excluding test fixtures that intentionally trigger rules

```text
# .grippyignore
tests/test_rule_*.py
tests/fixtures/
```
