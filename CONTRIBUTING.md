# Contributing

Thanks for your interest in contributing to Grippy!

## Quick Start

```bash
git clone https://github.com/Project-Navi/grippy-code-review.git
cd grippy-code-review
uv sync
uv run pre-commit install
uv run pytest tests/ -v
```

## Key Commands

| Command | Purpose |
|---------|---------|
| `uv run pytest tests/ -v` | Run all tests |
| `uv run ruff check src/grippy/ tests/` | Lint |
| `uv run ruff format src/grippy/ tests/` | Format |
| `uv run mypy src/grippy/` | Type check |
| `uv run pre-commit run --all-files` | Run all pre-commit hooks |

## Full Guide

See the [Contributing wiki page](https://github.com/Project-Navi/grippy-code-review/wiki/Contributing) for the complete guide, including:

- Test conventions (naming, coverage, e2e marks)
- Adding new security rules
- Code conventions (SPDX headers, ruff config, mypy strict)
- PR process and CI requirements
- Commit style and conventions

## Security Issues

Please report security vulnerabilities privately via [GitHub Security Advisories](https://github.com/Project-Navi/grippy-code-review/security/advisories/new) or see [SECURITY.md](SECURITY.md).
