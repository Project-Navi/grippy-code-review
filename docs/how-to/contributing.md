# Contributing

## Development Setup

1. **Clone the repo:**

   ```bash
   git clone https://github.com/YOUR_USERNAME/grippy-code-review.git
   cd grippy-code-review
   ```

2. **Install [uv](https://docs.astral.sh/uv/)** (Python package manager):

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. **Install all dependencies** (runtime + dev):

   ```bash
   uv sync
   ```

4. **Set up git hooks:**

   ```bash
   uv run pre-commit install
   ```

   This ensures every commit is automatically checked for formatting, lint, secrets, and license headers before it lands.

## Running Tests

```bash
# All tests
uv run pytest tests/ -v

# Single file
uv run pytest tests/test_grippy_codebase.py -v

# Single test
uv run pytest tests/test_grippy_codebase.py::TestCodebaseToolkit::test_read_file_traversal -v

# Rule engine tests only
uv run pytest tests/test_grippy_rules_engine.py tests/test_grippy_rules_config.py tests/test_grippy_rules_context.py -v

# Single rule's tests
uv run pytest tests/test_grippy_rule_secrets.py -v

# With coverage report
uv run pytest tests/ -v --cov=src/grippy --cov-report=term-missing

# End-to-end tests (auto-skipped in normal CI)
uv run pytest tests/ -m e2e -v
```

CI enforces a quality gate that auto-bumps on main push. Current thresholds: **845+ tests**, **97%+ coverage**, **0 parity violations** (`.github/quality-gate.json`). E2E tests are marked with `@pytest.mark.e2e` and require `-m e2e` to run.

## Linting and Type Checking

```bash
# Lint (reports issues)
uv run ruff check src/grippy/ tests/

# Lint (auto-fix what it can)
uv run ruff check --fix src/grippy/ tests/

# Format check (reports issues)
uv run ruff format --check src/grippy/ tests/

# Format (applies formatting)
uv run ruff format src/grippy/ tests/

# Type check (strict mode)
uv run mypy src/grippy/
```

Ruff rules enabled: `E`, `F`, `I`, `N`, `W`, `UP`, `B`, `RUF`, `C4` (with `E501` ignored --- line length is handled by the formatter at 100 chars). MyPy runs with `disallow_untyped_defs` and `check_untyped_defs` enabled.

## Security Scanning

```bash
uv run bandit -c pyproject.toml -r src/grippy/
```

The following Bandit rules are skipped in `pyproject.toml`, with justification:

| Rule | What it flags | Why it's skipped |
|------|--------------|-----------------|
| **B101** | `assert` statements | Asserts are used for invariant checks in production code; acceptable here. |
| **B404** | `import subprocess` | Needed for calling `git` and `gh` CLI tools. |
| **B603** | `subprocess` without `shell=True` | This is the **secure** pattern --- avoiding `shell=True` is intentional. |
| **B607** | Partial executable path | `git` and `gh` are standard CLI tools available on `$PATH`. |

## Pre-commit Hooks

When you run `git commit`, pre-commit automatically runs these checks:

| Hook | What it does |
|------|-------------|
| `trailing-whitespace` | Strips trailing whitespace from lines |
| `end-of-file-fixer` | Ensures files end with a single newline |
| `check-yaml` / `check-toml` / `check-ast` | Validates YAML, TOML, and Python syntax |
| `check-added-large-files` | Blocks files larger than 1 MB |
| `check-merge-conflict` | Catches leftover merge conflict markers |
| `check-symlinks` | Detects broken symlinks |
| `debug-statements` | Catches stray `breakpoint()` / `pdb` calls |
| `no-commit-to-branch` | Prevents direct commits to `main` |
| `insert-license` (SPDX) | Ensures every `.py` file has the `# SPDX-License-Identifier: MIT` header in the first 3 lines |
| `ruff` | Lint check with auto-fix |
| `ruff-format` | Code formatting |
| `bandit` | Security lint (uses `pyproject.toml` config) |
| `detect-secrets` | Scans for accidentally committed secrets (API keys, tokens, etc.) |

To run all hooks manually against the entire repo:

```bash
uv run pre-commit run --all-files
```

## Code Conventions

- **Python 3.12+** --- the minimum supported version.
- **SPDX license header** on all `.py` files --- must appear in the first 3 lines:
  ```python
  # SPDX-License-Identifier: MIT
  ```
- **Ruff formatting** --- line length 100, target Python 3.12.
- **MyPy strict mode** --- all functions must have type annotations (`disallow_untyped_defs`).
- **GitHub Actions SHA-pinned** --- all action references use full commit SHAs, not tags, for supply chain security.
- **Sanitized error messages** --- PR comments must never leak internal paths, stack traces, or secrets.

## Test Conventions

- **Naming:** `src/grippy/foo.py` → `tests/test_grippy_foo.py`
- **Minimum size:** 50 LOC per test file (enforced by `test-file-parity` CI job)
- **E2E tests:** Marked with `@pytest.mark.e2e`, auto-skipped unless `-m e2e` is passed
- **Fake credentials:** Test diffs with fake secrets need `# pragma: allowlist secret` comment and `.secrets.baseline` regeneration

## Adding a New Security Rule

The rule engine lives in `src/grippy/rules/`. To add a new rule:

1. **Create the rule module** --- `src/grippy/rules/<name>.py`. Implement the `Rule` protocol:
   ```python
   class MyRule:
       id = "my-rule-id"
       description = "What this rule detects"
       default_severity = RuleSeverity.ERROR

       def run(self, ctx: RuleContext) -> list[RuleResult]: ...
   ```

2. **Register it** --- Add the class to `RULE_REGISTRY` in `src/grippy/rules/registry.py`.

3. **Add tests** --- Create `tests/test_grippy_rule_<name>.py` with test cases for both positive matches and false-positive avoidance.

Test naming conventions:
- `tests/test_grippy_rule_*.py` --- individual rule implementations
- `tests/test_grippy_rules_*.py` --- rule subsystem (engine, config, context)

## PR Process

1. Branch off `main` (never commit directly to `main` --- pre-commit blocks it).
2. Keep PRs focused: one feature or fix per PR.
3. CI must pass before merge. The CI matrix runs:
   - **Tests** on Python 3.12 and 3.13
   - **Ruff** lint and format check
   - **MyPy** type check
   - **Bandit** security scan
   - **Semgrep** SAST scan
   - **pip-audit** dependency vulnerability check
   - **Pre-commit** hook validation
   - **CodeQL** static analysis
   - **Test file parity** check (naming + 50 LOC minimum)
   - **Quality gate** enforcement

## Commit Style

Use imperative mood, lowercase, with a category prefix:

| Prefix | Use for |
|--------|---------|
| `fix:` | Bug fixes |
| `feat:` | New features |
| `refactor:` | Code restructuring without behavior change |
| `chore:` | Maintenance, dependency updates |
| `docs:` | Documentation changes |
| `test:` | Test additions or changes |
| `ci:` | CI/CD pipeline changes |
| `style:` | Formatting, whitespace, import ordering |

Examples:

```
fix: guard v1 migration to preserve v2 nodes
feat: add vector refresh for stale record detection
docs: ground-up README rewrite
test: add vector refresh test for stale record detection
ci: pin actions to commit SHAs
```

When commits include AI-assisted code, add the co-author trailer:

```
Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```
