# SPDX-License-Identifier: MIT

"""Shared pytest configuration and fixtures.

e2e tests are skipped by default. Opt in:
  uv run pytest -m e2e -v          # LLM system contract
  uv run pytest -m e2e_fast -v     # deterministic (no LLM)
  uv run pytest -m e2e_stress -v   # LLM model characterization
  uv run pytest -m "e2e or e2e_fast or e2e_stress" -v  # all
"""

from __future__ import annotations

import pytest

_E2E_MARKERS = frozenset({"e2e", "e2e_fast", "e2e_stress"})


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Auto-skip e2e-marked tests unless their specific marker is selected."""
    marker_expr = config.getoption("-m") or ""
    if not marker_expr:
        _skip_all_e2e(items)
        return

    from _pytest.mark.expression import Expression

    try:
        expr = Expression.compile(marker_expr)
    except Exception:
        return

    skip = pytest.mark.skip(reason="e2e marker not selected by -m expression")
    for item in items:
        item_markers = item.keywords.keys() & _E2E_MARKERS
        if not item_markers:
            continue
        if not expr.evaluate(lambda name, _item=item: name in _item.keywords):
            item.add_marker(skip)


def _skip_all_e2e(items: list[pytest.Item]) -> None:
    skip = pytest.mark.skip(
        reason="e2e tests not selected (run with: pytest -m 'e2e or e2e_fast or e2e_stress')"
    )
    for item in items:
        if item.keywords.keys() & _E2E_MARKERS:
            item.add_marker(skip)
