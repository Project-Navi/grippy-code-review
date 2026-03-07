# SPDX-License-Identifier: MIT

"""Shared pytest configuration and fixtures.

e2e marker handling:
  Tests marked with @pytest.mark.e2e are skipped by default because they are
  slow and require external services (LLM API keys, MCP server, etc.).
  Opt in with:  uv run pytest -m e2e -v
"""

from __future__ import annotations

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Auto-skip e2e tests unless explicitly selected with -m e2e."""
    if "e2e" not in (config.getoption("-m") or ""):
        skip_e2e = pytest.mark.skip(reason="e2e tests not selected (run with: pytest -m e2e)")
        for item in items:
            if "e2e" in item.keywords:
                item.add_marker(skip_e2e)
