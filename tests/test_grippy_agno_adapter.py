# SPDX-License-Identifier: MIT
"""Tests for grippy.agno_adapter — transitional ReviewerPort shim."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from grippy.agno_adapter import AgnoAdapter, _AgnoResponse, create_agno_reviewer
from grippy.ports import SanitizedPRContext

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_agent() -> MagicMock:
    """Agno Agent stand-in with .run() and .model.id."""
    agent = MagicMock()
    agent.model.id = "test-model-v1"
    return agent


@pytest.fixture()
def sanitized_ctx() -> SanitizedPRContext:
    """Pre-sanitized context (plain ASCII, no XML chars)."""
    return SanitizedPRContext(content="test message")


# ---------------------------------------------------------------------------
# _AgnoResponse
# ---------------------------------------------------------------------------


class TestAgnoResponse:
    """Tests for _AgnoResponse protocol compliance."""

    def test_content_delegates_to_raw(self) -> None:
        raw = MagicMock()
        raw.content = "review output"
        resp = _AgnoResponse(raw)
        assert resp.content == "review output"

    def test_content_returns_none_when_raw_is_none(self) -> None:
        raw = MagicMock()
        raw.content = None
        resp = _AgnoResponse(raw)
        assert resp.content is None

    def test_content_returns_dict(self) -> None:
        raw = MagicMock()
        raw.content = {"findings": []}
        resp = _AgnoResponse(raw)
        assert resp.content == {"findings": []}

    def test_reasoning_content_returns_none_when_absent(self) -> None:
        raw = MagicMock(spec=[])  # no attributes at all
        raw.content = "x"
        resp = _AgnoResponse(raw)
        assert resp.reasoning_content is None

    def test_reasoning_content_returns_value_when_present(self) -> None:
        raw = MagicMock()
        raw.reasoning_content = "chain of thought"
        resp = _AgnoResponse(raw)
        assert resp.reasoning_content == "chain of thought"


# ---------------------------------------------------------------------------
# AgnoAdapter
# ---------------------------------------------------------------------------


class TestAgnoAdapter:
    """Tests for AgnoAdapter ReviewerPort compliance."""

    def test_run_delegates_to_agent_with_message_content(
        self, mock_agent: MagicMock, sanitized_ctx: SanitizedPRContext
    ) -> None:
        adapter = AgnoAdapter(mock_agent)
        adapter.run(sanitized_ctx)
        mock_agent.run.assert_called_once_with("test message")

    def test_run_returns_review_response(
        self, mock_agent: MagicMock, sanitized_ctx: SanitizedPRContext
    ) -> None:
        mock_agent.run.return_value.content = '{"findings": []}'
        adapter = AgnoAdapter(mock_agent)
        result = adapter.run(sanitized_ctx)
        assert result.content == '{"findings": []}'

    def test_model_id_reads_from_agent_model(self, mock_agent: MagicMock) -> None:
        adapter = AgnoAdapter(mock_agent)
        assert adapter.model_id == "test-model-v1"

    def test_model_id_returns_none_when_no_model(self) -> None:
        agent = MagicMock(spec=[])  # no model attribute
        adapter = AgnoAdapter(agent)
        assert adapter.model_id is None

    def test_model_id_returns_none_when_model_has_no_id(self) -> None:
        agent = MagicMock()
        agent.model = MagicMock(spec=[])  # model exists but no id
        adapter = AgnoAdapter(agent)
        assert adapter.model_id is None


# ---------------------------------------------------------------------------
# create_agno_reviewer factory
# ---------------------------------------------------------------------------


class TestCreateAgnoReviewer:
    """Tests for the factory function."""

    def test_returns_agno_adapter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_create = MagicMock(return_value=MagicMock())
        monkeypatch.setattr("grippy.agent.create_reviewer", mock_create)
        result = create_agno_reviewer(model_id="test-model")
        assert isinstance(result, AgnoAdapter)
        mock_create.assert_called_once_with(model_id="test-model")

    def test_passes_kwargs_through(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_create = MagicMock(return_value=MagicMock())
        monkeypatch.setattr("grippy.agent.create_reviewer", mock_create)
        create_agno_reviewer(model_id="m", mode="cli", transport="local")
        mock_create.assert_called_once_with(model_id="m", mode="cli", transport="local")
